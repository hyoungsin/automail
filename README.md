# automail

매일(또는 수동) **Gmail 검색 → 요약 → 발송** 자동화 프로젝트입니다.

> 프로젝트 폴더: `D:\BIG\coding\automail`

---

## 0. 이게 뭐 하는 건가요?

- 매일 아침 내 Gmail에서 정해 둔 조건(예: 안 읽은 메일, 최근 24시간 등)으로 메일을 모아
- LLM으로 요약하고
- 정해 둔 수신자에게 자동으로 **요약 메일을 보내거나** Gmail **초안**을 만들어 둡니다.

발송 방식은 두 가지 중 골라 쓸 수 있어요.

| 방식 | PC 꺼져도 동작? | 추천 |
|---|---|---|
| **GitHub Actions** (이 저장소에 포함된 워크플로우) | ✅ 예 | **★ 추천** |
| **Windows 작업 스케줄러** (로컬 PC) | ❌ 아니오 (PC 켜져 있어야) | 보조 |

---

## 1. 빠른 시작 (처음 한 번만)

### 1.1 가상환경·패키지 설치

PowerShell 열고:

```powershell
cd D:\BIG\coding\automail
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

### 1.2 환경 변수 파일 만들기

```powershell
copy .env.example .env
```

`.env`를 메모장으로 열어서 필요한 값(특히 `DIGEST_RECIPIENT`, LLM 키)을 채웁니다. 자세한 항목은 [§7 환경 변수](#7-환경-변수) 참고.

### 1.3 Google Cloud OAuth 설정 (Gmail API 사용)

처음 한 번만:

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트 만들기
2. **APIs & Services → Library** → **Gmail API** 검색 → **사용 설정**
3. **APIs & Services → Credentials** → **OAuth client ID 만들기** → 유형은 **데스크톱 앱**
4. 다운로드한 JSON을 **`credentials/client_secret.json`** 으로 저장
5. **APIs & Services → OAuth consent screen (새 UI에선 `대상`)** → **테스트 사용자**에 본인 Gmail 추가

### 1.4 최초 로그인 (token.json 만들기)

```powershell
cd D:\BIG\coding\automail
.\.venv\Scripts\python.exe scripts\gmail_digest.py --auth-smoke
```

브라우저가 열리면:
1. 본인 Gmail 로그인
2. "Google에서 확인하지 않은 앱" 화면 → **왼쪽의 `계속`** 클릭 (오른쪽 큰 버튼은 취소)
3. 권한 동의 화면 → **`모두 선택`** 체크박스 클릭 → **오른쪽 아래 `계속`**
4. "The authentication flow has completed." 메시지 + PowerShell에 **`Gmail API 연결 성공`** 뜨면 끝

→ `token.json` 파일이 생성됩니다.

---

## 2. 매일 자동 발송 - GitHub Actions (★ 추천)

**PC를 꺼도 매일 08:00 KST에 GitHub 서버에서 자동 실행**됩니다.

### 2.1 저장소 시크릿 등록 (처음 한 번)

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 등록:

| Secret 이름 | 값 |
|---|---|
| `GMAIL_CLIENT_SECRET_JSON` | 로컬 `credentials/client_secret.json` **파일 전체 내용** |
| `GMAIL_TOKEN_JSON` | 로컬 `token.json` **파일 전체 내용** |
| `DIGEST_PRODUCTION_RECIPIENT` | 받는 사람 이메일 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `GEMINI_MODEL` | 모델명 (예: `gemini-2.0-flash`) |

> 파일 내용을 클립보드에 복사하려면:
> ```powershell
> Get-Content D:\BIG\coding\automail\token.json -Raw | Set-Clipboard
> ```

### 2.2 수동 실행으로 테스트

GitHub 저장소 → **Actions** → **`automail gmail digest`** → **Run workflow** → **Branch: main** → **Run workflow**

녹색 체크 ✅ 뜨면 성공. 받는 사람 메일함 확인.

### 2.3 매일 자동 실행

별도 설정 없이 매일 **08:00 KST(= 23:00 UTC)** 자동 실행됩니다. 일정은 `.github/workflows/automail.yml`의 `cron`에 정의되어 있어요.

### 2.4 token.json이 만료되면

GitHub Actions는 브라우저 로그인 창을 띄울 수 없어서, **`token.json`이 만료/철회되면 실패**합니다. 이때는:

```powershell
cd D:\BIG\coding\automail
del token.json
.\.venv\Scripts\python.exe scripts\gmail_digest.py --auth-smoke
```

위와 같이 로컬에서 새 토큰을 만든 뒤, **`GMAIL_TOKEN_JSON` 시크릿만 새 내용으로 업데이트**하면 됩니다.

---

## 3. 매일 자동 발송 - Windows 작업 스케줄러 (보조)

이건 **PC가 켜져 있을 때만** 동작합니다. GitHub Actions와 같이 쓸 필요는 없어요.

### 3.1 작업 등록 (처음 한 번)

```powershell
cd D:\BIG\coding\automail
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\schedule_windows.ps1
```

기본은 매일 **08:00**. 다른 시각으로 바꾸려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\schedule_windows.ps1 -DailyAt "14:20"
```

작업 이름: **`AutomailGmailDigest8AM`**

### 3.2 수동 실행 / 확인 / 삭제

```powershell
Start-ScheduledTask -TaskName 'AutomailGmailDigest8AM'

Get-ScheduledTask -TaskName 'AutomailGmailDigest8AM' | Get-ScheduledTaskInfo

Unregister-ScheduledTask -TaskName 'AutomailGmailDigest8AM' -Confirm:$false
```

### 3.3 PC가 꺼져 있을 때 동작 여부

- **종료(Shut down)** → ❌ 실행 안 됨
- **절전(Sleep)** → 작업 속성에서 "절전 모드 해제하여 실행" 옵션이 켜져 있어야 깨어남
- **로그아웃** → Interactive 작업이라 실행 안 될 수 있음
- **PC를 자주 끈다면 GitHub Actions(§2)를 쓰세요**

---

## 4. 로컬 수동 실행 (테스트·디버깅)

권장 순서로 위에서 아래로 실행해 보면 됩니다.

```powershell
cd D:\BIG\coding\automail
```

| 명령 | 무엇을 하나 |
|---|---|
| `.\.venv\Scripts\python.exe scripts\gmail_digest.py --auth-smoke` | Gmail API 연결만 확인 |
| `.\.venv\Scripts\python.exe scripts\gmail_digest.py --search-only` | 프리셋별 검색 건수만 출력 |
| `.\.venv\Scripts\python.exe scripts\gmail_digest.py --no-llm --dry-run` | LLM 안 쓰고 파일만 |
| `.\.venv\Scripts\python.exe scripts\gmail_digest.py --dry-run` | LLM 포함, 파일만 (발송·드래프트 X) |
| `.\.venv\Scripts\python.exe scripts\gmail_digest.py` | 실제 운영 (`.env` 설정대로 발송/초안) |

---

## 5. 자주 발생하는 에러와 해결

### 5.1 `access_denied` (OAuth 권한 거부)

**증상:** 브라우저 OAuth 진행 중 access_denied로 끝남.

**원인 & 해결:**
- 권한 동의 화면에서 **체크박스를 안 누르고 `계속`** → 체크박스 모두 선택 후 계속
- "확인하지 않은 앱" 화면에서 **오른쪽 큰 파란 버튼(`안전한 환경으로 돌아가기`)** 을 누름 → **왼쪽 작은 `계속`** 눌러야 함
- 로그인한 Gmail이 **테스트 사용자에 등록 안 됨** → Google Cloud Console → `대상` → 테스트 사용자에 추가
- 시크릿 창에서 정확한 계정으로 다시 시도

### 5.2 `invalid_grant: Token has been expired or revoked`

**증상:** GitHub Actions 또는 스케줄러에서 실패.

**해결:** §2.4 절차대로 로컬 재인증 → `GMAIL_TOKEN_JSON` 시크릿 업데이트.

### 5.3 `getaddrinfo failed` (DNS 실패)

**증상:** `oauth2.googleapis.com` 해석 실패.

**원인:** 그 시점에 PC가 인터넷에 못 닿음 (Wi-Fi 끊김, VPN, 회사망 등).

**해결:**
```powershell
ping oauth2.googleapis.com
nslookup oauth2.googleapis.com
```
연결 회복 후 재실행. 반복되면 GitHub Actions로 옮기는 게 안정적.

### 5.4 Gemini 429 (할당량 초과)

`--no-llm` 옵션으로 우회하거나, 할당량/모델 조정.

### 5.5 작업 스케줄러가 옛 경로를 가리킴

폴더를 이동했다면 (§3.1) 재등록해서 경로 갱신.

---

## 6. 폴더 구조

```
automail/
├── .env                       # 비밀·설정 (git 제외)
├── .env.example               # 변수 템플릿
├── requirements.txt
├── token.json                 # OAuth 갱신 토큰 (git 제외)
├── .github/workflows/
│   └── automail.yml           # GitHub Actions 워크플로우 (매일 08:00 KST)
├── config/
│   └── search_presets.yaml    # Gmail 검색 쿼리·enabled·max_messages
├── credentials/
│   └── client_secret.json     # Google Cloud OAuth 클라이언트 JSON (git 제외)
├── output/                    # summary_*.md, run_*.json, send_history.jsonl, error_*.json
├── scripts/
│   ├── gmail_digest.py        # 메인 CLI
│   └── schedule_windows.ps1   # Windows 매일 작업 등록
└── src/
    ├── config.py              # .env 로드
    ├── gmail_client.py        # OAuth, 검색, 발송
    ├── search.py              # YAML 프리셋
    ├── compose.py             # 메일 블록·본문
    ├── summarize.py           # 규칙 요약 + LLM
    ├── pipeline.py            # 전체 오케스트레이션
    └── history.py             # send_history.jsonl
```

---

## 7. 환경 변수

`.env`에서 설정합니다.

| 변수 | 용도 |
|---|---|
| `GMAIL_CREDENTIALS_PATH` | OAuth 클라이언트 JSON 경로 (기본 `credentials/client_secret.json`) |
| `GMAIL_TOKEN_PATH` | refresh 토큰 경로 (기본 `token.json`) |
| `GMAIL_FROM_DISPLAY_NAME` | (선택) 보낸 사람 표시 이름. 비우면 Gmail 계정 기본 이름. 주소는 항상 OAuth 계정과 동일(`getProfile`으로 자동 설정) |
| `DIGEST_RECIPIENT` | 테스트용 수신자 |
| `DIGEST_PRODUCTION_RECIPIENT` | 운영 수신자 |
| `USE_PRODUCTION_RECIPIENT` | `1`이면 운영 수신자 사용 |
| `CREATE_GMAIL_DRAFT` | `1`이면 Gmail 초안 생성 |
| `AUTO_SEND` | `1`이면 초안 대신 즉시 발송 |
| `DRY_RUN` | `1`이면 파일만 저장, 발송·초안 안 함 |
| `LLM_PROVIDER` | `gemini` / `genspark` / `openai` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Gemini 사용 시 |
| `GENSPARK_API_KEY`, `GENSPARK_BASE_URL` | Genspark 사용 시 |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | OpenAI 사용 시 |

---

## 8. 검색 조건 수정

`config/search_presets.yaml` 에서:

- `query`: [Gmail 검색 연산자](https://support.google.com/mail/answer/7190)
- `enabled`: `true`인 프리셋만 실행
- `max_messages`: 프리셋당 최대 메일 수

---

## 9. 산출물

| 경로 | 설명 |
|---|---|
| `output/summary_*.md` | 다이제스트 마크다운 |
| `output/run_*.json` | 실행 메타·건수 |
| `output/send_history.jsonl` | 실행 이력 (한 줄 JSON) |
| `output/error_*.json` | 실패 상세 |
| `output/draft_id_*.txt` | 초안 생성 시 초안 ID |
| `output/sent_message_id_*.txt` | 발송 시 메시지 ID |

---

## 10. GitHub에 처음 올릴 때 (한 번만)

```powershell
cd D:\BIG\coding\automail

<최초 push>
  - git init (git을 초기화하기,최초1번 only)
  - git add . (git안의 모든 파일을 복사하기)
  - git commit -m "first commit" (git version 기록)
  - git branch -M main (git의 저장위치를 main으로)
  - git remote add origin https://github.com/hyoungsin/jambro-contents-mall.git
      (git local 과 git website/ssh 와 연결하기,최초1번 only)
  - git push -u origin main (git website에 최종등록하기)

<2번째 이후후>
  - git add . (git안의 모든 파일을 복사하기)
  - git commit -m "commit about something" (git version 기록)
  - git branch -M main (git의 저장위치를 main으로)
  - git push -u origin main (git website에 최종등록하기)
```

> **주의:** `.env`, `token.json`, `credentials/`는 `.gitignore`로 GitHub에 올라가지 않게 막혀 있습니다. 시크릿은 §2.1 절차대로 **GitHub Settings → Secrets**에만 등록하세요.

---

## 11. 운영 체크리스트

매번 코드 수정·환경 변경 후 확인하면 좋은 순서:

1. `.venv` 존재 + `pip install -r requirements.txt`
2. `--auth-smoke`로 토큰 유효성 확인
3. `--search-only`로 프리셋 의도 확인
4. `--dry-run`으로 요약 품질 확인
5. 실제 1회 발송 후 받는 사람 메일함 확인
6. (로컬 스케줄러 사용 시) 작업 등록 상태 확인
7. (GitHub Actions 사용 시) Actions 탭에서 최근 실행 성공 여부 확인
