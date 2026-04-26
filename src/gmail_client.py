from __future__ import annotations

import base64
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _refresh_with_retry(creds: Credentials, *, max_attempts: int = 5) -> None:
    """
    Token refresh는 가끔 DNS/네트워크 문제로 실패할 수 있어 짧게 재시도한다.
    영구 실패(invalid_grant 등)는 즉시 상위로 전달한다.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            creds.refresh(Request())
            return
        except RefreshError:
            # invalid_grant 등은 재시도해도 의미가 거의 없음
            raise
        except Exception as e:
            msg = str(e)
            transient = any(
                s in msg
                for s in (
                    "NameResolutionError",
                    "Failed to resolve",
                    "getaddrinfo failed",
                    "[Errno 11001]",
                    "Temporary failure in name resolution",
                )
            )
            if not transient or attempt == max_attempts:
                raise
            time.sleep(2**attempt)


def get_credentials() -> Credentials:
    cred_path = config.gmail_credentials_path()
    token_path = config.gmail_token_path()
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                _refresh_with_retry(creds)
            except RefreshError as e:
                # token.json refresh_token이 만료/철회된 케이스: 자동화(스케줄)에서는 브라우저 로그인이 불가하므로
                # token을 백업해두고, 사용자가 --auth-smoke로 재인증하도록 안내한다.
                msg = str(e)
                if "invalid_grant" in msg:
                    backup = token_path.with_name(f"{token_path.stem}.revoked_{_now_stamp()}{token_path.suffix}")
                    try:
                        token_path.replace(backup)
                    except Exception:
                        # 백업 실패는 치명적이 아니므로 무시하고 원래 예외를 던진다.
                        pass
                    raise RefreshError(
                        "invalid_grant: token.json이 만료/철회되었습니다. "
                        "대화형 재인증이 필요합니다. "
                        "로컬에서 `python scripts/gmail_digest.py --auth-smoke` 실행 후 다시 스케줄러를 확인하세요."
                    ) from e
                raise
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def list_message_ids(service, query: str, max_results: int) -> list[str]:
    ids: list[str] = []
    page_token: str | None = None
    while len(ids) < max_results:
        remaining = max_results - len(ids)
        batch = min(remaining, 100)
        req = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=batch, pageToken=page_token)
        )
        resp = req.execute()
        for m in resp.get("messages", []):
            ids.append(m["id"])
            if len(ids) >= max_results:
                break
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def get_message_meta(service, msg_id: str) -> dict:
    return (
        service.users()
        .messages()
        .get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        )
        .execute()
    )


def _header_map(meta: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in meta.get("payload", {}).get("headers", []):
        name = (h.get("name") or "").lower()
        if name in ("subject", "from", "date"):
            out[h.get("name", "")] = h.get("value", "")
    return out


def get_snippet(service, msg_id: str) -> tuple[dict[str, str], str]:
    meta = get_message_meta(service, msg_id)
    headers = _header_map(meta)
    snippet = meta.get("snippet") or ""
    return headers, snippet


def gmail_web_url(message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"


def _mime_raw(to_addr: str, subject: str, body_text: str) -> str:
    msg = MIMEMultipart("alternative")
    msg["to"] = to_addr
    msg["subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


def create_draft(service, to_addr: str, subject: str, body_text: str) -> str:
    raw = _mime_raw(to_addr, subject, body_text)
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft.get("id", "")


def send_message(service, to_addr: str, subject: str, body_text: str) -> str:
    raw = _mime_raw(to_addr, subject, body_text)
    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    return sent.get("id", "")


def http_error_message(err: HttpError) -> str:
    status = err.resp.status if err.resp else 0
    if status == 401:
        return "인증 실패(401): token.json을 삭제 후 다시 로그인하거나 OAuth 클라이언트를 확인하세요."
    if status == 403:
        return "권한 거부(403): Gmail API 활성화 및 OAuth 동의 화면·스코프를 확인하세요."
    if status == 429:
        return "API 한도 초과(429): 잠시 후 재시도하세요."
    return f"Gmail API 오류 (HTTP {status}): {err}"
