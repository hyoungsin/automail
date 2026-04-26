from __future__ import annotations

import re
from datetime import datetime

from . import gmail_client


def draft_subject() -> str:
    return f"[Gmail digest] 일일 요약 {datetime.now().strftime('%Y-%m-%d')}"


def _snippet_to_summary_lines(snippet: str, max_lines: int = 3, max_chars: int = 120) -> str:
    text = re.sub(r"\s+", " ", snippet.strip())
    if not text:
        return "(본문 스니펫 없음)"
    lines: list[str] = []
    remaining = text
    while len(lines) < max_lines and remaining:
        if len(remaining) <= max_chars:
            lines.append(remaining)
            break
        cut = remaining[:max_chars]
        sp = cut.rfind(" ")
        if sp > 40:
            cut = remaining[:sp]
        lines.append(cut.strip())
        remaining = remaining[len(cut) :].strip()
    return "\n".join(lines)


def format_message_block(
    msg_id: str,
    headers: dict[str, str],
    snippet: str,
) -> str:
    """4단계: 제목, 발신자, 수신 시각, 2~3줄 요약, 원문 링크(식별자)."""
    subj = headers.get("Subject", "(제목 없음)")
    from_ = headers.get("From", "")
    date_ = headers.get("Date", "")
    summary = _snippet_to_summary_lines(snippet)
    link = gmail_client.gmail_web_url(msg_id)
    return (
        f"### {subj}\n"
        f"- 발신: {from_}\n"
        f"- 수신: {date_}\n"
        f"- 요약:\n{summary}\n"
        f"- 열기: {link}\n"
    )


def digest_body_from_blocks(intro: str, blocks: list[str]) -> str:
    body = (
        intro
        + "\n\n---\n\n"
        + "아래는 검색 조건에 맞는 메일입니다. (드래프트 확인 후 발송하세요.)\n\n"
        + "\n".join(blocks)
    )
    return body


def digest_full_markdown(intro: str, markdown: str) -> str:
    return intro + "\n\n---\n\n" + markdown.strip() + "\n"


def plain_intro() -> str:
    return (
        "이 메일은 저장소 스크립트(scripts/gmail_digest.py)가 생성한 초안입니다.\n"
        "워크플로: gmail_automation_workflow_hyungsin.md"
    )
