# 50번 방 ③ — role-mobility 에 develop 을 merge 한다(규칙 16: merge 만 · rebase 금지). push 하지 않는다.
#   저장소 루트에서:  powershell -ExecutionPolicy Bypass -File .\50_merge.ps1
#   merge 대상은 50_before.ps1 이 적은 _50/develop_hash.txt — 검토한 것과 같은 커밋만 받는다.
#   --no-commit 으로 합치고 → 회귀 after → --json 대조. 전부 초록이면 커밋, 아니면 커밋하지 않고 멈춘다.
#   되돌리기: 커밋 전 `git merge --abort` · 커밋 뒤(push 전) `git reset --hard ORIG_HEAD`
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$D = "_50"; $LOG = "$D/50_merge.txt"; Remove-Item -ErrorAction SilentlyContinue $LOG
function W([object[]]$lines) { foreach ($l in $lines) { Write-Host "$l"; "$l" | Out-File -Encoding utf8 -Append $LOG } }

W "50번 merge — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') · 기기 $env:COMPUTERNAME"
if (-not (Test-Path "$D/develop_hash.txt")) { W "! $D/develop_hash.txt 없음 — 50_before.ps1 먼저"; exit 1 }
$dev = (Get-Content "$D/develop_hash.txt" | Select-Object -First 1).Trim()
$devS = $dev.Substring(0,7)
$br = (git rev-parse --abbrev-ref HEAD).Trim()
$dirty = @(git status --porcelain --untracked-files=no)
if ($br -ne "role-mobility") { W "! role-mobility 가 아니다 — 멈춘다"; exit 1 }
if ($dirty.Count) { W $dirty; W "! 추적 파일 변경 있음 — 멈춘다"; exit 1 }
if (Test-Path .git/MERGE_HEAD) { W "! 진행 중인 merge 가 있다 — 멈춘다"; exit 1 }
if (-not (Test-Path "$D/json_before")) { W "! $D/json_before 없음 — --json 대조를 못 한다. 50_before.ps1 을 -SkipReg 없이 돌린다"; exit 1 }
$pre = (git rev-parse --short HEAD).Trim()
W "merge 전 HEAD $pre · 받을 develop $devS"
$now = (git rev-parse origin/develop).Trim()
if ($now -ne $dev) { W "주의: origin/develop 이 그 뒤 또 움직였다($($now.Substring(0,7))). 검토한 $devS 만 받는다." }

$out = & git -c core.quotepath=off merge --no-ff --no-commit $dev 2>&1 | ForEach-Object { "$_" }
$mc = $LASTEXITCODE
W ""; W "===== git merge --no-ff --no-commit $devS ====="; W $out; W "  (종료코드 $mc)"
$conf = @(git -c core.quotepath=off diff --name-only --diff-filter=U)
if ($mc -ne 0 -or $conf.Count) {
    W ""; W "===== 충돌 $($conf.Count)건 — 여기서 멈춘다(자동으로 풀지 않는다) ====="
    $ours = "^(final_project_cs/app/modules/travel_ops/mobility_engine/|tests/mobility/|scripts/|modules/mobility/|docs/mobility/|config/mobility/)"
    foreach ($f in $conf) { if ($f -match $ours) { W "  우리 자리 → ours  : $f" } else { W "  팀 파일   → theirs: $f" } }
    W "방침: 우리 쪽 mobility_engine 등은 지키고(git checkout --ours -- <파일>), 팀 파일은 팀 것을 따른다(git checkout --theirs -- <파일>)."
    W "이 기록을 Claude 에게 보여 주고 같이 푼다. 그만두려면: git merge --abort"
    exit 2
}
W ""; W "===== merge 로 들어온 변경 (스테이징) ====="
W (& git -c core.quotepath=off --no-pager diff --cached --stat=200 HEAD 2>&1 | ForEach-Object { "$_" })

W ""; W "회귀 after 시작 (약 10분) → $D/reg_after.txt"
& powershell -ExecutionPolicy Bypass -File .\50_reg.ps1 -Tag after
$rc = $LASTEXITCODE
W "회귀 after — 종료코드 0 아닌 항목 $rc"

$jd = & python ..\scratch\repo_tools_31_34_38_20260922\31_json_diff.py "$D/json_before" "$D/json_after" 2>&1 | ForEach-Object { "$_" }
$jc = $LASTEXITCODE
W ""; W "===== --json 대조 before ↔ after ====="; W $jd; W "  (종료코드 $jc)"

if ($rc -eq 0 -and $jc -eq 0) {
    $msg = "merge: origin/develop $devS → role-mobility (50번 · 201dad5 이후 반영 · 회귀 123 · --json 차이 0)"
    $co = & git commit -m $msg 2>&1 | ForEach-Object { "$_" }
    W ""; W "===== 커밋 ====="; W $co
    W "새 merge 커밋 $((git rev-parse --short HEAD).Trim()) · develop $devS · 기기 $env:COMPUTERNAME"
    W "push 는 본인이 한다:  git push origin role-mobility"
} else {
    W ""; W "! 초록이 아니다 — 커밋하지 않았다. merge 는 스테이징 상태로 남아 있다."
    W "  기록을 Claude 에게 보여 준다. 그만두려면: git merge --abort"
    exit 3
}
