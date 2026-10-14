"""Apply the scoped deployment control-flow update after original backup."""
from pathlib import Path

p = Path('final_project_cs/deploy/auto_deploy.sh')
s = p.read_text(encoding='utf-8')
start = s.index('settle_ok() {')
end = s.index('  echo "$SHORT" > "$STATE/current_tag"', start)
s = s[:start] + '''if TRIPILOT_TAG="$SHORT" python3 "$GUARD" rollout --state-dir "$SAFETY_STATE" --timeout 240 --settle "${SETTLE_SECONDS:-30}" >>"$LOG" 2>&1 </dev/null; then
''' + s[end:]
start = s.index('  if TRIPILOT_TAG="$PREV" docker compose up')
end = s.index('  exit 1\nfi', start)
s = s[:start] + '''  # rollout 자체가 실제 이전 이미지 ID로 복구하고 확인한다. 태그로 다시 덮지 않는다.
  log "복구 결과는 위 migration_safe_deploy 기록 확인 — 자동 재시도하지 않는다"
''' + s[end:]
p.write_text(s, encoding='utf-8', newline='\n')
