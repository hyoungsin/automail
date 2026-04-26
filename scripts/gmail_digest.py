#!/usr/bin/env python3
"""
2단계: 저장소 자동화 스크립트 — 검색 · 요약 · 발송 설계(드래프트).
Cursor Automation(7단계)에서 매일 오전 8시 이 파일을 실행하면 됩니다.

권장 디버깅 순서(문서 2절):
  python scripts/gmail_digest.py --auth-smoke
  python scripts/gmail_digest.py --search-only
  python scripts/gmail_digest.py --no-llm --dry-run
  python scripts/gmail_digest.py --no-llm
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    p = argparse.ArgumentParser(description="Gmail digest: 검색 → 요약 → 드래프트")
    p.add_argument(
        "--auth-smoke",
        action="store_true",
        help="Gmail API 연결만 확인(1단계 검증)",
    )
    p.add_argument(
        "--search-only",
        action="store_true",
        help="검색 건수만 출력(2단계 권장)",
    )
    p.add_argument("--no-llm", action="store_true", help="LLM 없이 규칙 기반만")
    p.add_argument("--dry-run", action="store_true", help="파일만 저장, 드래프트 생략")
    p.add_argument("--no-draft", action="store_true", help="드래프트 생성 안 함")
    args = p.parse_args(argv)

    if args.auth_smoke:
        from src import gmail_client

        try:
            gmail_client.build_service()
        except FileNotFoundError as e:
            logging.error("자격 증명 파일 없음: %s", e)
            return 1
        except Exception as e:
            logging.exception("연결 실패: %s", e)
            return 1
        logging.info("Gmail API 연결 성공")
        return 0

    if args.search_only:
        try:
            report = pipeline.run_search_only()
        except FileNotFoundError as e:
            logging.error("자격 증명 파일 없음: %s", e)
            return 1
        except Exception as e:
            logging.exception("검색 실패: %s", e)
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    import os

    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    create_draft = None
    if args.no_draft:
        create_draft = False

    try:
        path = pipeline.run_digest(use_llm=not args.no_llm, create_draft=create_draft)
    except FileNotFoundError as e:
        logging.error("자격 증명 파일 없음: %s", e)
        return 1
    except Exception as e:
        logging.exception("실행 실패: %s", e)
        return 1

    logging.info("요약 저장: %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
