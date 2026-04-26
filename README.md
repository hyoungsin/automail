## automail

매일(또는 수동) **Gmail 검색 → 요약 → 발송(또는 초안 생성)** 자동화 프로젝트입니다.

---

## Github배포 (mono-repository 기준)

PowerShell에서 `automail` 폴더 기준:

```powershell
cd D:\BIG\vive-coding\automail
git init (git을 초기화하기,최초1번 only)
git add . (git안의 모든 파일을 복사하기)
git commit -m "first commit" (git version 기록)
git branch -M main (git의 저장위치를 main으로)
git remote add origin https://github.com/hyoungsin/automail.git
    (git local 과 git website/ssh 와 연결하기,최초1번 only)
git push -u origin main (git website에 최종등록하기)
```

> 주의: `.env`, `token.json`, `credentials/` 등 민감정보는 `.gitignore`로 **GitHub에 올라가지 않게** 되어 있어야 합니다.

---

## GitHub Actions로 “PC 꺼도” 매일 08:00 자동 실행

이 저장소에는 `automail gmail digest` 워크플로우가 포함되어 있고,
**매일 08:00 KST(= 23:00 UTC)**에 실행되도록 설정되어 있습니다.

### 1) GitHub 설정(Secrets 등록)

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 아래 3개를 등록합니다.

- **`GMAIL_CLIENT_SECRET_JSON`**: 로컬 `credentials/client_secret.json` **파일 전체(JSON 전체)** 붙여넣기
- **`GMAIL_TOKEN_JSON`**: 로컬 `token.json` **파일 전체(JSON 전체)** 붙여넣기
- **`DIGEST_PRODUCTION_RECIPIENT`**: 수신자(예: `marius.oh@lge.com`)

### 2) 1회 테스트 실행

GitHub 저장소 → **Actions** → `automail gmail digest` → **Run workflow**

### 3) 끊길 수 있는 경우(유일)

Actions는 브라우저 로그인 창을 띄울 수 없어, `token.json`이 **invalid_grant(만료/철회)** 되면 실패합니다.
이 경우 로컬에서 아래를 한 번 실행해 새 토큰을 만든 뒤, GitHub Secret `GMAIL_TOKEN_JSON`만 갱신하면 됩니다.

```powershell
cd D:\BIG\vive-coding\automail
.\.venv\Scripts\python.exe scripts\gmail_digest.py --auth-smoke
```

---

## 더 자세한 문서

- 로컬 실행/구조/트러블슈팅: `workflow.md`

## 1. 무엇을 하는 프로젝트인가

| 항목 | 내용 |
|------|------|
| 목표 | 매일(또는 수동) **Gmail 검색 → 요약 → 발송 설계(초안/드래프트)** |
| 스택 | Python 3, Gmail API(OAuth), 선택 LLM(Genspark / Gemini / OpenAI) |
| 발송 방식 | **즉시 발송이 아니라 Gmail 초안 생성**이 기본(확인 후 발송) |

**데이터 흐름:** 스크립트 실행 → YAML 검색 프리셋 → 메일 메타·스니펫 수집 → 규칙 기반 마크다운 → (선택) LLM 다듬기 → `output/` 저장 → (설정 시) Gmail 드래프트.

---

## 2. 폴더 구조

```
automail/
├── .env                    # 비밀·설정 (git 제외)
├── .env.example            # 변수 템플릿
├── requirements.txt
├── token.json              # OAuth 갱신 토큰 (git 제외, 최초 로그인 후 생성)
├── config/
│   └── search_presets.yaml # Gmail 검색 쿼리·enabled·max_messages
├── credentials/
│   └── client_secret.json  # Google Cloud OAuth 클라이언트 JSON (git 제외)
├── output/                 # summary_*.md, run_*.json, send_history.jsonl, error_*.json
├── scripts/
│   ├── gmail_digest.py     # 메인 CLI
│   └── schedule_windows.ps1# Windows 매일 08:00 작업 등록
└── src/
    ├── config.py           # .env 로드
    ├── gmail_client.py     # OAuth, 검색, 드래프트
    ├── search.py           # YAML 프리셋
    ├── compose.py          # 메일 블록·드래프트 본문
    ├── summarize.py        # 규칙 요약 + LLM(Gemini / Genspark agent_ask / OpenAI)
    ├── pipeline.py         # 전체 오케스트레이션
    └── history.py          # send_history.jsonl
```

---

## 3. 최초 설정 (한 번)

### 3.1 Python 가상환경

PowerShell에서 프로젝트 루트(`automail`) 기준:

```powershell
cd D:\BIG\vive-coding\automail
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

이후 예시 명령은 모두 **`.venv`의 python** 사용:

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py [옵션]
```

### 3.2 환경 변수

```powershell
copy .env.example .env
```

`.env`에서 최소로 채울 항목은 **`.env.example` 주석과 동일**. 요약:

| 변수 | 용도 |
|------|------|
| `GMAIL_CREDENTIALS_PATH` | OAuth 클라이언트 JSON 경로 (기본 `credentials/client_secret.json`) |
| `GMAIL_TOKEN_PATH` | 저장할 refresh 토큰 (기본 `token.json`) |
| `DIGEST_RECIPIENT` | 테스트용 수신(초안 받을 주소) |
| `USE_PRODUCTION_RECIPIENT` / `DIGEST_PRODUCTION_RECIPIENT` | 운영 전환 시 |
| `CREATE_GMAIL_DRAFT` / `DRY_RUN` | 드래프트 생성 여부, 파일만 저장 |
| `AUTO_SEND` | `1`이면 초안 대신 즉시 발송(`DIGEST_*` 수신자) |
| `LLM_PROVIDER` | `genspark` / `gemini` / `openai` 또는 키 기반 자동 선택 |
| Genspark | `GENSPARK_API_KEY`(또는 `GSK_API_KEY`, `GSK_KEY`), `GENSPARK_BASE_URL`(기본 `https://www.genspark.ai`), `GENSPARK_TASK_TYPE`(기본 `super_agent`) |
| Gemini | `GEMINI_API_KEY` 또는 `GOOGLE_AI_API_KEY`, `GEMINI_MODEL` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |

### 3.3 Google Cloud (Gmail API)

1. 프로젝트 생성 → **Gmail API 사용 설정**  
2. **OAuth 클라이언트** 유형: **데스크톱** → JSON 다운로드 → `credentials/client_secret.json` 등으로 저장  
3. OAuth 동의 화면: 앱이 **테스트**면 **테스트 사용자**에 로그인할 Gmail 추가  

---

## 4. 권장 검증 순서 (명령어)

아래는 **위에서 아래로** 실행하는 것을 권장합니다.

```powershell
cd D:\BIG\vive-coding\automail
```

### 4.1 Gmail 연결만

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py --auth-smoke
```

브라우저 로그인 후 `token.json` 생성되면 성공.

### 4.2 검색 건수만 (LLM·드래프트 없음)

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py --search-only
```

### 4.3 파일만 (LLM 끔, 드래프트 없음)

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py --no-llm --dry-run
```

### 4.4 LLM 포함, 파일만

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py --dry-run
```

### 4.5 운영에 가깝게 (요약 파일 + Gmail 초안)

```powershell
.\.venv\Scripts\python.exe scripts\gmail_digest.py
```

(`.env`에서 `DRY_RUN=0`, `CREATE_GMAIL_DRAFT=1`, `DIGEST_RECIPIENT` 필요)

### 4.6 CLI 옵션 요약

| 옵션 | 의미 |
|------|------|
| `--auth-smoke` | API 연결만 확인 |
| `--search-only` | 프리셋별 검색 건수 JSON 출력 |
| `--no-llm` | 규칙 기반 마크다운만 (LLM 호출 안 함) |
| `--dry-run` | `output/` 저장만, Gmail 드래프트 안 만듦 |
| `--no-draft` | 이번 실행만 드래프트 생략 |

---

## 5. 검색 조건 수정

파일: `config/search_presets.yaml`

- `query`: [Gmail 검색 연산자](https://support.google.com/mail/answer/7190)  
- `enabled`: `true`인 프리셋만 실행  
- `max_messages`: 프리셋당 상한  

---

## 6. Windows 매일 08:00 자동 실행

### 6.1 작업 등록 (한 번)

PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BIG\vive-coding\automail\scripts\schedule_windows.ps1"
```

테스트로 **다른 시각**(예: 당일 오후 2:20)에 맞추려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BIG\vive-coding\automail\scripts\schedule_windows.ps1" -DailyAt "14:20"
```

다시 아침 8시로 되돌리려면 `-DailyAt "08:00"` 없이 위 첫 줄만 실행(기본값 08:00).

등록 이름: **`AutomailGmailDigest8AM`** (로컬 시각 매일 지정 시각, 로그인된 사용자·Interactive)

### 중요: PC가 꺼져 있으면 실행되지 않음

- **전원 종료(Shut down)** 또는 **배터리 방전으로 꺼짐** → 작업 스케줄러는 **동작하지 않습니다.** (바뀐 적 없음, 클라우드가 아닌 **이 노트북 안에서만** 돕니다.)
- **절전(Sleep)** 중이면, 작업 속성의 **「절전 모드를 해제하여 이 작업 실행」** 등을 켜야 8시에 깨어나며 돌 수 있습니다. (기기·설정에 따라 실패할 수 있음)
- **로그아웃만** 한 상태(현재 등록 방식: Interactive)에서는 **실행이 안 될 수 있습니다.** 8시에 돌리려면 **로그인된 상태**를 권장합니다.
- **배터리만 연결**일 때 막히지 않게 하려면 작업 **조건**에서 “AC 전원일 때만”을 끄는 식으로 설정합니다. (스크립트의 `AllowStartIfOnBatteries`는 이와 맞춤)

**PC를 끈 채로도 매일 돌리려면** 로컬 스케줄이 아니라 **항상 켜진 서버**, 또는 **Cursor/클라우드 Automation**처럼 **본인 PC 밖에서** 스크립트를 돌리는 방식을 써야 합니다.

### 6.2 수동으로 즉시 실행 (테스트)

```powershell
Start-ScheduledTask -TaskName 'AutomailGmailDigest8AM'
```

### 6.3 확인·삭제

- GUI: `Win + R` → `taskschd.msc` → 작업 라이브러리에서 이름 검색  
- 삭제 (PowerShell):

```powershell
Unregister-ScheduledTask -TaskName 'AutomailGmailDigest8AM' -Confirm:$false
```

### 6.4 Cursor Automation을 쓸 경우

동일 인자로 예약하면 됩니다:

- 실행: `D:\BIG\vive-coding\automail\.venv\Scripts\python.exe`  
- 인수: `"D:\BIG\vive-coding\automail\scripts\gmail_digest.py"`  
- 시작 위치: `D:\BIG\vive-coding\automail`  

---

## 7. 산출물·로그

| 경로 | 설명 |
|------|------|
| `output/summary_*.md` | 다이제스트 마크다운 |
| `output/run_*.json` | 실행 메타·건수 |
| `output/send_history.jsonl` | 실행 이력 한 줄 JSON |
| `output/error_*.json` | 실패 시 상세 |
| `output/draft_id_*.txt` | (드래프트 생성 시) 초안 ID |

---

## 8. 원 문서의 1~10단계와 매핑

| 단계 | 이 저장소에서 |
|------|----------------|
| 1 Gmail API 준비 | Google Cloud + `credentials/client_secret.json` |
| 2 스크립트 | `scripts/gmail_digest.py` |
| 3 검색 조건 | `config/search_presets.yaml` |
| 4 요약 형식 | `src/compose.py` |
| 5·8 수신자 | `.env` `DIGEST_*`, `USE_PRODUCTION_RECIPIENT` |
| 즉시 발송(선택) | `.env` `AUTO_SEND=1` → 초안 대신 발송(끝나면 `0`) |
| 6 Secrets | `.env`, `token.json` |
| 7 스케줄 | `schedule_windows.ps1` 또는 Cursor Automation |
| 9 예외 | `output/error_*.json`, 로그, LLM 실패 시 규칙 기반 유지 |
| 10 운영 | `send_history.jsonl`, 프리셋 조정, 토큰 주기 확인 |

---

## 9. 알려진 이슈·팁

- **`api.genspark.ai` DNS 실패:** Genspark는 **`https://www.genspark.ai`** + `POST /api/tool_cli/agent_ask`, 헤더 **`X-Api-Key`** 를 사용함 (`src/summarize.py`). `.env`에 옛 `api.genspark.ai`가 있으면 제거하거나 `www`로 변경.  
- **Gemini 429:** 재시도 후 규칙 기반으로 폴백. 필요 시 `--no-llm` 또는 할당량·모델 조정.  
- **OAuth 테스트 사용자:** 동의 화면이 테스트 모드면 로그인 계정을 테스트 사용자에 등록.  
- **스케줄 실행:** 토큰 만료 시 실패할 수 있음 → 수동 `--auth-smoke`로 재인증.  
- **API 키:** `.env`·채팅에 노출되지 않게 관리; 유출 시 재발급.

---

## 6.5 (대안) PC를 꺼도 매일 실행: GitHub Actions 크론

개인 PC를 자주 끄는 환경이라면 로컬 작업 스케줄러 대신 **GitHub Actions(항상 켜져 있는 실행 환경)**로 옮기는 것이 가장 간단합니다.

이 저장소에는 `automail/.github/workflows/automail.yml` 워크플로우가 포함되어 있으며,
매일 **08:00 KST(= 23:00 UTC)**에 `python scripts/gmail_digest.py`를 실행하도록 되어 있습니다.

### 준비물(Secrets 등록)

GitHub 저장소 Settings → Secrets and variables → Actions → New repository secret:

- `GMAIL_CLIENT_SECRET_JSON`: Google Cloud에서 받은 OAuth 클라이언트 JSON 파일 내용을 그대로 붙여넣기(`credentials/client_secret.json`)
- `GMAIL_TOKEN_JSON`: 로컬에서 생성된 `token.json` 내용을 그대로 붙여넣기(헤드리스 refresh 용)
- `DIGEST_PRODUCTION_RECIPIENT`: 수신자(예: `marius.oh@lge.com`)

(선택) LLM을 쓰면:
- `LLM_PROVIDER`, `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GENSPARK_API_KEY` / `GENSPARK_BASE_URL`

### 주의(헤드리스 OAuth)

Actions는 브라우저 로그인 창을 띄울 수 없기 때문에,
**`token.json`이 invalid_grant(만료/철회)**가 되면 워크플로우는 실패합니다.
이 경우 로컬에서 `python scripts/gmail_digest.py --auth-smoke`로 재인증해서 새 `token.json`을 만든 뒤,
GitHub Secret `GMAIL_TOKEN_JSON`을 업데이트하면 다시 정상 동작합니다.

---

## 10. 다음에 개발할 때 빠른 체크리스트

1. `.venv` 존재 + `pip install -r requirements.txt`  
2. `credentials/client_secret.json` + `token.json` 유효성 (`--auth-smoke`)  
3. `search_presets.yaml` 의도 반영 여부 (`--search-only`)  
4. `output/summary_*.md` 품질 (`--dry-run` → 전체 실행)  
5. Gmail 초안 확인 후 운영 수신자 전환  
6. 스케줄 작업 존재 여부 (`taskschd.msc` 또는 `Get-ScheduledTask`)
