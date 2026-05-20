from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


def root_dir() -> Path:
    return _ROOT


def gmail_credentials_path() -> Path:
    p = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/client_secret.json")
    return _ROOT / p if not Path(p).is_absolute() else Path(p)


def gmail_token_path() -> Path:
    p = os.getenv("GMAIL_TOKEN_PATH", "token.json")
    return _ROOT / p if not Path(p).is_absolute() else Path(p)


def gmail_from_display_name() -> str | None:
    """
    비어 있지 않으면 발송/초안 MIME의 From 표시 이름으로 사용합니다.
    주소는 Gmail API users.getProfile 로 OAuth 계정과 동일한 값만 씁니다.
    """
    n = os.getenv("GMAIL_FROM_DISPLAY_NAME", "").strip()
    return n or None


def digest_exclude_senders() -> frozenset[str]:
    """다이제스트에서 제외할 발신자(쉼표 구분). 기본: aimhyoungsin@gmail.com"""
    raw = os.getenv(
        "DIGEST_EXCLUDE_SENDERS",
        "aimhyoungsin@gmail.com",
    ).strip()
    if not raw:
        return frozenset()
    return frozenset(s.strip().lower() for s in raw.split(",") if s.strip())


def digest_recipient() -> str | None:
    if os.getenv("USE_PRODUCTION_RECIPIENT", "0").strip() in ("1", "true", "yes"):
        prod = os.getenv("DIGEST_PRODUCTION_RECIPIENT", "").strip()
        if prod:
            return prod
    to = os.getenv("DIGEST_RECIPIENT", "").strip()
    return to or None


def create_gmail_draft() -> bool:
    return os.getenv("CREATE_GMAIL_DRAFT", "1").strip() in ("1", "true", "yes")


def dry_run() -> bool:
    return os.getenv("DRY_RUN", "0").strip() in ("1", "true", "yes")


def auto_send_gmail() -> bool:
    """1이면 초안 대신 즉시 발송(gmail.compose 스코프로 messages.send)."""
    return os.getenv("AUTO_SEND", "0").strip() in ("1", "true", "yes")


def openai_config() -> tuple[str | None, str, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip() or None
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return key, base, model


def llm_provider() -> str:
    """openai | gemini | genspark | none (키 없으면 규칙 기반만)."""
    p = os.getenv("LLM_PROVIDER", "").strip().lower()
    if p in ("openai", "gemini", "genspark"):
        return p
    if (
        os.getenv("GENSPARK_API_KEY", "").strip()
        or os.getenv("GSK_API_KEY", "").strip()
        or os.getenv("GSK_KEY", "").strip()
    ):
        return "genspark"
    if os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_AI_API_KEY", "").strip():
        return "gemini"
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    return "none"


def gemini_config() -> tuple[str | None, str]:
    """Google AI Studio API 키 + 모델 id (예: gemini-2.0-flash)."""
    key = (
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_AI_API_KEY", "").strip()
        or None
    )
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    return key, model


def genspark_config() -> tuple[str | None, str, str, str | None]:
    """
    Genspark Tool API (CLI와 동일): POST {base}/api/tool_cli/agent_ask
    api.genspark.ai 는 DNS에 없을 수 있어 기본 호스트는 www.genspark.ai.
    """
    key = (
        os.getenv("GENSPARK_API_KEY", "").strip()
        or os.getenv("GSK_API_KEY", "").strip()
        or os.getenv("GSK_KEY", "").strip()
        or None
    )
    base = os.getenv("GENSPARK_BASE_URL", "https://www.genspark.ai").strip().rstrip("/")
    task_type = (
        os.getenv("GENSPARK_TASK_TYPE", "").strip()
        or os.getenv("GSK_TASK_TYPE", "").strip()
        or os.getenv("GENSPARK_MODEL", "").strip()
        or "super_agent"
    )
    project_id = (
        os.getenv("GENSPARK_PROJECT_ID", "").strip()
        or os.getenv("GSK_PROJECT_ID", "").strip()
        or None
    )
    return key, base, task_type, project_id
