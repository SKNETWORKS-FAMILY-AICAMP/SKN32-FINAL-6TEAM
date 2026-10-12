"""v12 마감 감사의 고정 명령·읽기 범위·모델별 원문 경로를 새 이름으로 준비한다."""
from pathlib import Path
import json

evidence = Path(__file__).resolve().parent
root = evidence.parents[3]
candidate = "legacy/deployment_candidates/2026-10-12_022208_plugin_v12"
stamp = "2026-10-12_0227"
runner = "v12-read-boundary-final-unit.py"
hook = "v12-read-boundary-exact-command-hook.py"
fixed = '"C:/Users/playdata2/anaconda3/python.exe" ' + (evidence / runner).relative_to(root).as_posix()
source = (evidence / "v11-read-recovery-exact-command-hook.py").read_text(encoding="utf-8-sig")
(evidence / hook).write_text(source.replace("v11-read-recovery-final-unit.py", runner), encoding="utf-8")
launcher = (evidence / "v11-read-recovery-final-launch.py").read_text(encoding="utf-8-sig")
launcher = launcher.replace("2026-10-12_015017_plugin_v11", "2026-10-12_022208_plugin_v12")
launcher = launcher.replace("v11-read-recovery-final-2026-10-12_0212", "v12-read-boundary-closing-" + stamp)
launcher = launcher.replace("v11-read-recovery-final-unit.py", runner)
launcher = launcher.replace("v11-read-recovery-exact-command-hook.py", hook)
launcher = launcher.replace('candidate/"review-notes/read-recovery-contract.md"', 'candidate/"review-notes/read-boundary-followup.md"')
launcher = launcher.replace("고정 v10 후보", "고정 v12 후보")
(evidence / "v12-read-boundary-final-launch.py").write_text(launcher, encoding="utf-8")

prompt = f'''Perform a narrowly scoped, independent READ-ONLY closing delta review of frozen candidate v12:
{root.as_posix()}/{candidate}
The prior actual Opus/Sonnet v11 full review found two static concerns, which Codex then reproduced with actual state reducers and memory/component seams. Those BEFORE reproductions are not real DB/HTTP tests. v11 original full isolated Linux 468/468 is preserved. v12 full isolated Linux run is separately underway; inspect its result only if already available, otherwise do not claim it passed.

ONLY product delta from v11 is trip_messages.py _run_decision:
1. safe_read validates snapshot.base_version against both current_context.version (before resolver/classification) and fresh current.version (after classification/routing but before answer).
2. safe_read detail calls _place_extras on a separate get_connection connection. The component place_info may rollback its connection on known SQL errors; separate connection preserves the main Case lock and uncommitted state transitions. Non-safe legacy paths unchanged.

Required reads within candidate (full relevant functions):
- app/domains/travel_ops/components/conversation/trip_messages.py _run_decision and handle_trip_message existing retry entry.
- fact_read_retry.py: restore, lock_read_case, retry_read.
- app/domains/travel_ops/components/places/place_info.py: place_info/_catalog_row rollback handling.
- tests/unit/travel/test_fact_read_recovery.py new version drift and rollback cases.
- tests/e2e/test_fact_read_recovery_web.py new context/fresh race cases and rollback completion case.
- review-notes/read-boundary-followup.md.
v11 corresponding product source is permitted for comparison. No shared product/credentials/customer data may be read.

Check the version checks reject before answering and roll back Case transitions rather than losing input; the second check is after uncommitted classification/routing and outer connection must rollback on failure. Check no same-connection savepoint is incorrectly trusted to contain an inner conn.rollback. Separate enrichment connection must not call LLM/Team or mutate Case. Check the new HTTP tests use a real append_version on another connection rather than merely returning a fabricated version, and use current public fixed409 JSON rather than unsafe exception text. GPS must stay memory-only. Business gating and side-effect once semantics must remain unchanged. Do not expand to unrelated redesigns. Distinguish any residual read staleness that is permitted by point-in-time reads from this specific mixed-version bug; do not demand global itinerary locks as an unrequested policy change.

Execute this exact synthetic pure unit command ONCE with a sufficiently long timeout (do not run it in background):
{fixed}
PreToolUse denies every other Bash command including ls/cd/chains. Use Read/Glob/Grep for inspection. No edits/writes, DB/network/HTTP/operating API/deployment. Never read .env, keys, credentials, customer data, datasets, connection secrets. Runner uses synthetic placeholder settings and external IO0. Expected94 tests but report actual result. It includes A30+B14+existing50, not actual PG/HTTP. Do not claim the model directly executed DB tests.

Report in Korean: confirmed defects first with exact candidate file/line and minimal prerequisite/repro; separate static concerns from executed evidence. If none found in this narrow delta, say that narrowly. Include direct files read, exact test count/output, actual model and unverified conditions/permission denials. No source modification.
'''
for label in ("opus", "sonnet"):
    prefix = evidence / (label + "-v12-read-boundary-closing-" + stamp)
    permissions = json.loads((evidence / ("sonnet-v11-read-recovery-final-2026-10-12_0212-permissions.json")).read_text(encoding="utf-8-sig"))
    permissions["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = '"C:/Users/playdata2/anaconda3/python.exe" "' + (evidence / hook).as_posix() + '"'
    Path(str(prefix) + "-permissions.json").write_text(json.dumps(permissions, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(str(prefix) + "-prompt.txt").write_text(prompt, encoding="utf-8")
print(json.dumps({"candidate": candidate, "fixed": fixed, "labels": ["opus", "sonnet"]}))
