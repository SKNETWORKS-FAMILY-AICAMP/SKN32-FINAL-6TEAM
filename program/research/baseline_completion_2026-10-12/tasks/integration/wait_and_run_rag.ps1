# 메모리 여유가 생기면 BGE-M3 벡터 계산 → 검색 시험 16개를 차례로 돌린다.
# 계산 중 남은 가상 메모리가 바닥나면 다른 세션을 지키려고 계산을 끊고 다시 기다린다.
# 2026-10-12 Claude 세션(인계 claude-handoff-1924 이어받기)이 만들었다. 세션이 끊겨도 돌도록 별도 프로세스로 띄운다.
param(
    [double]$StartFreeGB = 3.5,   # 이만큼 비어 있어야 시작
    [double]$AbortFreeGB = 0.4,   # 계산 중 이 밑으로 내려가면 끊음
    [int]$MaxHours = 12,
    [int]$MaxTries = 4
)
$ErrorActionPreference = 'Continue'
$w = 'C:\Users\playdata2\Documents\final_workspace'
$task = "$w\program\research\baseline_completion_2026-10-12\tasks\integration"
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmm'
$log = "$task\checks\wait-and-run-rag-$stamp.log"
function Note($m) { ('{0} {1}' -f (Get-Date -Format 'HH:mm:ss'), $m) | Out-File -Append -Encoding utf8 $log }
function FreeGB { (Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory / 1MB }

Note "start pid=$PID start>=$StartFreeGB abort<$AbortFreeGB"
$deadline = (Get-Date).AddHours($MaxHours)
$saved = $null
$try = 0
while (-not $saved -and (Get-Date) -lt $deadline -and $try -lt $MaxTries) {
    if ((FreeGB) -lt $StartFreeGB) { Start-Sleep 30; continue }
    $try++
    $elog = "$task\checks\local-embedding-lowpeak-$stamp-try$try.log"
    Note ("try $try free={0:N1}GB log={1}" -f (FreeGB), $elog)
    $env:PYTHONUTF8 = '1'
    $p = Start-Process python -ArgumentList '-B', 'program/research/baseline_completion_2026-10-12/tasks/integration/encode_travel_locally.py', 'datasets/travel/baseline_completion_20261012/embeddings-2026-10-12_095012.json' -WorkingDirectory $w -RedirectStandardOutput $elog -RedirectStandardError "$elog.err" -WindowStyle Hidden -PassThru
    $aborted = $false
    while (-not $p.HasExited) {
        if ((FreeGB) -lt $AbortFreeGB) {
            Note ("abort low memory free={0:N1}GB" -f (FreeGB))
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $aborted = $true; break
        }
        Start-Sleep 2
    }
    $p.WaitForExit()
    Note "encode exit=$($p.ExitCode) aborted=$aborted"
    $line = Get-Content $elog -Encoding utf8 -ErrorAction SilentlyContinue | Where-Object { $_ -like 'saved *' } | Select-Object -Last 1
    if ($line) { $saved = ($line -split ' ')[1] }
    elseif (-not $aborted) { Note 'encode failed without low-memory abort; stop'; break }
    else { Start-Sleep 60 }
}
if (-not $saved) { Note 'no embeddings saved; end'; exit 1 }
Note "embeddings=$saved"

$rlog = "$task\checks\rag-16-$stamp.log"
$env:ACOP_INTEGRATION_PREPARE_DATA = '1'
$env:ACOP_INTEGRATION_EMBEDDINGS = "$w\$saved"
$env:ACOP_INTEGRATION_REUSE_OWN_CLUSTER = "$task\checks\2026-10-12_092645_945781_isolated_integration\pgdata"
Set-Location $w
& python -B program/research/baseline_completion_2026-10-12/tasks/integration/run_isolated_integration.py -m 'not live' tests/integration/rag/test_rag_integration.py tests/integration/rag/test_travel_corpus_retrieval.py *> $rlog
Note "rag exit=$LASTEXITCODE log=$rlog"
