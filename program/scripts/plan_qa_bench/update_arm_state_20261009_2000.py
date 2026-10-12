"""Record the completed fixed cache diagnostic; preserve the previous state."""
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / 'program/research/daily_rag_slm/arm_serving_2026-10-09.json'
RESULT = ROOT / 'program/scripts/plan_qa_bench/results/heartbeat_20261009_1953_arm'
now = datetime.now().astimezone().isoformat()
backup = STATE.parent / '_backup' / (datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_arm_ABBA_final')
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(STATE, backup / STATE.name)
state = json.loads(STATE.read_text(encoding='utf-8'))
capture = json.loads((RESULT / 'capture.json').read_text(encoding='utf-8'))
verify = json.loads((RESULT / 'abba_final_verification.json').read_text(encoding='utf-8'))
intervals = json.loads((RESULT / 'abba_intervals.json').read_text(encoding='utf-8'))
state.setdefault('observation_history', []).append({k: state.get(k) for k in ['recorded_at_kst','resource_observed_at_utc','resource_measurement','current_job_at_observation','saved_at_observation','completed_jobs','pending_jobs_after_refill','source_observation','report']})
state.update(recorded_at_kst=now, resource_observed_at_utc=capture['observed_at'], resource_measurement=capture['resource_summary'], free_bytes=capture['free_bytes'], active=True, enabled=True, worker_pid=171515, worker_restarted=False, lock_held=True, restart_count_observed=0, current_job_at_observation=capture['active']['job_id'], saved_at_observation=capture['active']['saved'], expected_at_observation=capture['active']['expected'], completed_jobs=6, running_jobs=1, registered_jobs_after_refill=14, pending_jobs_after_refill=7, cpu_target_24h_proven=False)
state['source_observation'] = (RESULT / 'observation.json').relative_to(ROOT).as_posix()
state['raw_results'] = RESULT.relative_to(ROOT).as_posix()
state['report'] = 'final_project_cs/wiki/records/reports/2026-10-09_2000_six-hour-gpu-arm-report.md'
diagnostic = state['cache_diagnostic']
diagnostic.update(completed_jobs=4, completed_calls=240, measured_improvement=True, measured_improvement_scope='Same fixed model and five selected itinerary contexts, 55 matched followup questions; development latency diagnostic only', preliminary_not_final_ABBA=False, final_ABBA=True, independent_holdout=False, product_adoption=False, verification=(RESULT / 'abba_final_verification.json').relative_to(ROOT).as_posix(), runs=verify['runs'], primary_metric={k: verify[k] for k in ['matched_followup_ids','matched_median_of_run_medians_on_s','matched_median_of_run_medians_off_s','matched_reduction','development_diagnostic_pass','identical_predictions_all4']}, intervals=intervals)
state['cache_archive_verification'] = {'new_verified':8,'new_expected':8,'all_four_run_verified':16,'all_four_run_expected':16,'backup':backup.relative_to(ROOT).as_posix()}
state['next_actions'] = ['Preserve running concurrent2 profile and seven pending jobs; collect completed attempts without a second worker', 'Broaden independent context and tenant isolation validation before any cache adoption; new-context first request remains about159seconds', 'Keep 60 unique questions separate from240 repeated calls and retain all failures']
STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'backup':backup.relative_to(ROOT).as_posix(),'state':STATE.relative_to(ROOT).as_posix()},ensure_ascii=False))
