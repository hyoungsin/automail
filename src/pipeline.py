from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from googleapiclient.errors import HttpError

from . import compose, config, gmail_client, history, summarize
from .search import enabled_presets, load_presets

logger = logging.getLogger(__name__)


def _write_error_artifact(name: str, payload: dict) -> Path:
    out = config.root_dir() / "output" / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_search_only() -> dict:
    """2단계 권장: 메일 검색만."""
    service = gmail_client.build_service()
    presets = enabled_presets(load_presets())
    report: dict[str, object] = {}
    for preset in presets:
        try:
            ids = gmail_client.list_message_ids(service, preset.query, preset.max_messages)
            report[preset.id] = {"name": preset.name, "count": len(ids), "query": preset.query}
        except HttpError as e:
            report[preset.id] = {
                "name": preset.name,
                "error": gmail_client.http_error_message(e),
                "query": preset.query,
            }
    return report


def run_digest(*, use_llm: bool = True, create_draft: bool | None = None) -> Path:
    """
    전체 파이프라인: 검색 → 4단계 포맷 요약 → output 저장 → (선택) 드래프트.
    9단계: 예외 시 로그 + output/*.json 기록.
    """
    root = config.root_dir()
    out_dir = root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    create_draft = config.create_gmail_draft() if create_draft is None else create_draft
    dry = config.dry_run()
    recipient = config.digest_recipient()

    status = "ok"
    err_detail: str | None = None
    draft_id: str | None = None
    total_messages = 0
    sections_out: list[dict] = []
    preset_counts: dict[str, int] = {}

    try:
        service = gmail_client.build_service()
    except FileNotFoundError as e:
        logger.error("OAuth 클라이언트 JSON 없음: %s", e)
        _write_error_artifact("error_credentials", {"message": str(e)})
        history.append_history(
            {
                "status": "error",
                "error": str(e),
                "draft_id": None,
                "recipient": recipient,
                "preset_counts": {},
                "total_messages": 0,
            }
        )
        raise
    except Exception as e:
        logger.exception("초기화 실패")
        _write_error_artifact("error_init", {"message": str(e)})
        history.append_history(
            {
                "status": "error",
                "error": str(e),
                "draft_id": None,
                "recipient": recipient,
                "preset_counts": {},
                "total_messages": 0,
            }
        )
        raise

    presets = enabled_presets(load_presets())

    for preset in presets:
        try:
            ids = gmail_client.list_message_ids(service, preset.query, preset.max_messages)
        except HttpError as e:
            msg = gmail_client.http_error_message(e)
            logger.error("검색 실패 [%s]: %s", preset.id, msg)
            _write_error_artifact(
                f"error_search_{preset.id}",
                {"preset": preset.id, "query": preset.query, "message": msg},
            )
            status = "partial_error"
            err_detail = msg
            continue

        preset_counts[preset.id] = len(ids)
        total_messages += len(ids)
        blocks: list[str] = []
        for mid in ids:
            try:
                headers, snippet = gmail_client.get_snippet(service, mid)
                blocks.append(compose.format_message_block(mid, headers, snippet))
            except HttpError as e:
                msg = gmail_client.http_error_message(e)
                logger.warning("메일 메타 조회 실패 %s: %s", mid, msg)
                blocks.append(f"(메일 {mid} 조회 실패: {msg})\n")

        sections_out.append(
            {
                "title": f"{preset.name} (`{preset.query}`)",
                "blocks": blocks,
            }
        )

    raw_md = summarize.rule_based_digest(sections_out)
    if use_llm:
        final_text = summarize.llm_refine_sync(raw_md)
    else:
        final_text = raw_md

    md_path = out_dir / f"summary_{stamp}.md"
    md_path.write_text(final_text, encoding="utf-8")

    json_path = out_dir / f"run_{stamp}.json"
    json_path.write_text(
        json.dumps(
            {
                "timestamp": stamp,
                "presets": [p.__dict__ for p in presets],
                "preset_counts": preset_counts,
                "total_messages": total_messages,
                "sections": [
                    {"title": s["title"], "message_count": len(s["blocks"])} for s in sections_out
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if total_messages == 0:
        logger.warning("검색 결과가 없습니다. 드래프트는 생성하지 않습니다(수신자 혼선 방지).")
        history.append_history(
            {
                "status": "no_results",
                "error": None,
                "draft_id": None,
                "recipient": recipient,
                "preset_counts": preset_counts,
                "total_messages": 0,
                "summary_path": str(md_path.relative_to(root)),
            }
        )
        return md_path

    if dry:
        logger.info("DRY_RUN=1: 드래프트 생략")
        history.append_history(
            {
                "status": "dry_run",
                "error": err_detail,
                "draft_id": None,
                "recipient": recipient,
                "preset_counts": preset_counts,
                "total_messages": total_messages,
                "summary_path": str(md_path.relative_to(root)),
            }
        )
        return md_path

    auto_send = config.auto_send_gmail()
    if not create_draft and not auto_send:
        history.append_history(
            {
                "status": "file_only",
                "error": err_detail,
                "draft_id": None,
                "sent_message_id": None,
                "recipient": recipient,
                "preset_counts": preset_counts,
                "total_messages": total_messages,
                "summary_path": str(md_path.relative_to(root)),
            }
        )
        return md_path

    if not recipient:
        logger.warning("DIGEST_RECIPIENT(또는 운영 수신자)가 비어 있어 드래프트를 만들지 않습니다.")
        history.append_history(
            {
                "status": "skipped_no_recipient",
                "error": err_detail,
                "draft_id": None,
                "recipient": None,
                "preset_counts": preset_counts,
                "total_messages": total_messages,
                "summary_path": str(md_path.relative_to(root)),
            }
        )
        return md_path

    body = compose.digest_full_markdown(compose.plain_intro(), final_text)
    subj = compose.draft_subject()
    sent_message_id: str | None = None

    try:
        if auto_send:
            sent_message_id = gmail_client.send_message(service, recipient, subj, body)
            (out_dir / f"sent_message_id_{stamp}.txt").write_text(
                sent_message_id or "", encoding="utf-8"
            )
            logger.info("Gmail 발송 완료 message_id=%s → %s", sent_message_id, recipient)
            status = "sent"
        else:
            draft_id = gmail_client.create_draft(service, recipient, subj, body)
            (out_dir / f"draft_id_{stamp}.txt").write_text(draft_id or "", encoding="utf-8")
    except HttpError as e:
        msg = gmail_client.http_error_message(e)
        if auto_send:
            logger.error("Gmail 발송 실패: %s", msg)
            _write_error_artifact("error_send", {"message": msg, "recipient": recipient})
            status = "send_failed"
        else:
            logger.error("드래프트 생성 실패: %s", msg)
            _write_error_artifact("error_draft", {"message": msg, "recipient": recipient})
            status = "draft_failed"
        err_detail = msg

    history.append_history(
        {
            "status": status,
            "error": err_detail,
            "draft_id": draft_id,
            "sent_message_id": sent_message_id,
            "recipient": recipient,
            "preset_counts": preset_counts,
            "total_messages": total_messages,
            "summary_path": str(md_path.relative_to(root)),
        }
    )

    return md_path
