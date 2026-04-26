# 7단계: 로컬 작업 스케줄러 등록 (매일 지정 시각)
# 관리자 권한 불필요(현재 사용자 계정으로 등록).
# OAuth 최초 1회는 수동으로 `python scripts\gmail_digest.py --auth-smoke` 후 token.json 생성 권장.
#
# 사용 예:
#   .\schedule_windows.ps1                    # 매일 08:00
#   .\schedule_windows.ps1 -DailyAt "14:20"   # 매일 14:20 (테스트용)

param(
    [string]$DailyAt = "08:00"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "먼저 $ProjectRoot 에서 python -m venv .venv 후 pip install -r requirements.txt 를 실행하세요."
    exit 1
}

$TaskName = "AutomailGmailDigest8AM"
$Script = Join-Path $ProjectRoot "scripts\gmail_digest.py"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Description = "automail: Gmail 검색·요약·드래프트 (매일 $DailyAt 로컬 시각)"

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description $Description `
    -Force | Out-Null

Write-Host "등록 완료: 작업 이름 '$TaskName'"
Write-Host "  실행: 매일 $DailyAt (이 PC 로컬 시간)"
Write-Host "  프로그램: $Python"
Write-Host "  인수: `"$Script`""
Write-Host "  작업 디렉터리: $ProjectRoot"
Write-Host ""
Write-Host "중요: 이전에 테스트로 다른 시각(예: 14:35)으로 등록했다면, 이 스크립트를 다시 실행해야 08:00으로 되돌아갑니다."
Write-Host "확인(트리거/다음 실행): Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo | Format-List *"
Write-Host "확인: 작업 스케줄러(taskschd.msc) → 작업 스케줄 라이브러리 → $TaskName"
Write-Host "삭제: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
