from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

import httpx

from . import config

logger = logging.getLogger(__name__)


def _tz_name() -> str:
    return datetime.now(timezone.utc).astimezone().tzname() or "local"


def rule_based_digest(sections: list[dict]) -> str:
    """프리셋별로 이미 포맷된 블록을 묶은 마크다운."""
    lines = [
        f"# 일일 메일 요약 ({datetime.now().strftime('%Y-%m-%d %H:%M')} {_tz_name()})",
        "",
    ]
    for sec in sections:
        title = sec.get("title", "")
        lines.append(f"## {title}")
        lines.append("")
        blocks = sec.get("blocks", [])
        if not blocks:
            lines.append("*검색 결과 없음*")
        else:
            lines.extend(blocks)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_SYSTEM = (
    "당신은 메일 다이제스트를 한국어로 '보기 좋게' 편집하는 편집자입니다.\n"
    "\n"
    "규칙:\n"
    "- 입력은 이미 마크다운이며, 섹션(##)과 메일 블록(###) 구조가 있습니다.\n"
    "- 각 메일 블록에서 아래 항목 라벨은 유지하세요: 발신, 수신, 요약, 열기.\n"
    "- 요약은 2~4줄로 다듬고, 불필요한 반복/광고문/푸터 문구는 제거하세요.\n"
    "- '해야 할 일/마감/요청'이 있으면 요약 첫 줄에 **[액션]** 으로 한 문장으로 드러내세요.\n"
    "- 섹션 의도는 유지하세요(예: 필독/참고/홍보).\n"
    "- 출력은 마크다운만 반환하세요(설명 금지)."
)


def _chat_completions_refine(
    markdown_input: str,
    *,
    label: str,
    api_key: str | None,
    base_url: str,
    model: str,
) -> str:
    """OpenAI 스타일 POST {base}/chat/completions + Bearer (Genspark 등 호환)."""
    if not api_key:
        return markdown_input

    base_url = base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"다음 다이제스트를 다듬어 주세요.\n\n{markdown_input}",
            },
        ],
        "temperature": 0.3,
    }
    backoff = 2.0
    for attempt in range(4):
        if attempt:
            time.sleep(min(backoff, 45.0))
            backoff *= 2
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            logger.warning("%s 네트워크 오류 (%s/4): %s", label, attempt + 1, e)
            continue
        if r.status_code == 429:
            logger.warning("%s 429 한도/속도 제한 (%s/4), 잠시 후 재시도", label, attempt + 1)
            continue
        if r.status_code >= 500:
            logger.warning("%s 서버 오류 HTTP %s (%s/4)", label, r.status_code, attempt + 1)
            continue
        if r.is_error:
            body = ""
            try:
                body = r.text[:500]
            except Exception:
                pass
            logger.warning(
                "%s 다듬기 실패 HTTP %s, 규칙 기반 유지. 응답 일부: %s",
                label,
                r.status_code,
                body,
            )
            return markdown_input
        try:
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as e:
            logger.warning("%s 응답 파싱 실패(%s), 규칙 기반 유지", label, e)
            return markdown_input
    logger.warning("%s 재시도 소진, 규칙 기반 요약 유지", label)
    return markdown_input


def _openai_refine(markdown_input: str) -> str:
    api_key, base, model = config.openai_config()
    if not api_key:
        logger.info("LLM refine skipped (OpenAI): missing OPENAI_API_KEY")
    return _chat_completions_refine(
        markdown_input, label="OpenAI", api_key=api_key, base_url=base, model=model
    )


def _genspark_parse_agent_ndjson(text: str) -> dict | None:
    """CLI agent_ask 응답: 줄 단위 NDJSON 중 마지막 status 객체."""
    final: dict | None = None
    for raw_line in text.strip().split("\n"):
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("debug") is True:
            continue
        if "status" in obj:
            final = obj
    return final


def _genspark_extract_reply(data: dict | None, fallback: str) -> str:
    if not data:
        logger.warning("Genspark 응답을 NDJSON으로 해석하지 못함, 규칙 기반 유지")
        return fallback
    if data.get("status") != "ok":
        msg = (data.get("message") or json.dumps(data, ensure_ascii=False))[:800]
        logger.warning("Genspark agent_ask 실패: %s", msg)
        return fallback
    inner = data.get("data") or {}
    rc = inner.get("result_content") or {}
    parts = rc.get("last_message")
    if isinstance(parts, list) and parts:
        return "\n".join(str(p) for p in parts).strip()
    logger.warning("Genspark 응답에 last_message 없음, 규칙 기반 유지")
    return fallback


def _genspark_refine(markdown_input: str) -> str:
    """
    공식 웹 호스트 + tool_cli/agent_ask (genspark/chat.py 와 동일).
    api.genspark.ai 는 DNS 미존재로 getaddrinfo 실패하는 환경이 있음.
    """
    api_key, base, task_type, project_id = config.genspark_config()
    if not api_key:
        logger.info("LLM refine skipped (Genspark): missing GENSPARK_API_KEY")
        return markdown_input

    url = f"{base.rstrip('/')}/api/tool_cli/agent_ask"
    user_msg = (
        f"{_SYSTEM}\n\n"
        "아래 메일 다이제스트를 한국어 마크다운만으로 다듬어 주세요.\n\n"
        f"{markdown_input}"
    )
    payload: dict = dict(message=user_msg, task_type=task_type)
    if project_id:
        payload["project_id"] = project_id

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "X-Api-Key": api_key,
    }
    if project_id:
        headers["X-Project-ID"] = project_id

    backoff = 2.0
    for attempt in range(4):
        if attempt:
            time.sleep(min(backoff, 60.0))
            backoff *= 2
        try:
            with httpx.Client(timeout=300.0) as client:
                r = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            logger.warning("Genspark 네트워크 오류 (%s/4): %s", attempt + 1, e)
            continue
        if r.status_code == 429:
            logger.warning("Genspark 429 (%s/4), 잠시 후 재시도", attempt + 1)
            continue
        if r.status_code >= 500:
            logger.warning("Genspark 서버 오류 HTTP %s (%s/4)", r.status_code, attempt + 1)
            continue
        if r.is_error:
            snippet = (r.text or "")[:600]
            logger.warning(
                "Genspark HTTP %s, 규칙 기반 유지. 응답 일부: %s",
                r.status_code,
                snippet,
            )
            return markdown_input
        parsed = _genspark_parse_agent_ndjson(r.text)
        return _genspark_extract_reply(parsed, markdown_input)
    logger.warning("Genspark 재시도 소진, 규칙 기반 요약 유지")
    return markdown_input


def _gemini_refine(markdown_input: str) -> str:
    api_key, model = config.gemini_config()
    if not api_key:
        logger.info("LLM refine skipped (Gemini): missing GEMINI_API_KEY")
        return markdown_input

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "systemInstruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"다음 다이제스트를 다듬어 주세요.\n\n{markdown_input}"}
                ],
            }
        ],
        "generationConfig": {"temperature": 0.3},
    }
    backoff = 2.0
    for attempt in range(4):
        if attempt:
            time.sleep(min(backoff, 60.0))
            backoff *= 2
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as e:
            logger.warning("Gemini 네트워크 오류 (%s/4): %s", attempt + 1, e)
            continue
        if r.status_code == 429:
            logger.warning(
                "Gemini 429(분당/일일 할당량 또는 속도 제한) (%s/4), 잠시 후 재시도",
                attempt + 1,
            )
            continue
        if r.status_code >= 500:
            logger.warning("Gemini 서버 오류 HTTP %s (%s/4)", r.status_code, attempt + 1)
            continue
        if r.is_error:
            logger.warning("Gemini 다듬기 실패 HTTP %s, 규칙 기반 유지", r.status_code)
            return markdown_input
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            logger.warning("Gemini 응답에 후보 없음, 규칙 기반 유지")
            return markdown_input
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            return markdown_input
        return parts[0].get("text", markdown_input).strip()
    logger.warning("Gemini 재시도 소진(429 등), 규칙 기반 요약 유지")
    return markdown_input


def llm_refine_sync(markdown_input: str) -> str:
    provider = config.llm_provider()
    logger.info("LLM provider: %s", provider)
    if provider == "genspark":
        return _genspark_refine(markdown_input)
    if provider == "gemini":
        return _gemini_refine(markdown_input)
    if provider == "openai":
        return _openai_refine(markdown_input)
    return markdown_input
