@setlocal & set "TRIPILOT_BATCH=%~f0" & set "TRIPILOT_ROOT=%~dp0" & set "TRIPILOT_ACTION=stop" & powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text=[IO.File]::ReadAllText($env:TRIPILOT_BATCH,[Text.Encoding]::UTF8); $body=($text -split '(?m)^#==POWERSHELL==\r?$',2)[1]; & ([scriptblock]::Create($body))" && exit /b 0 || exit /b 1
#==POWERSHELL==
$ErrorActionPreference = 'Stop'
try {
    $start = Join-Path $env:TRIPILOT_ROOT 'triPilot-실행.bat'
    $text = [IO.File]::ReadAllText($start, [Text.Encoding]::UTF8)
    $body = ($text -split '(?m)^#==POWERSHELL==\r?$', 2)[1]
    & ([scriptblock]::Create($body))
} catch { Write-Host '종료 실행 파일을 읽지 못했습니다.'; exit 1 }
