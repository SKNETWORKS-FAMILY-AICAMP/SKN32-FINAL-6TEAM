"""사전 실행 계획을 백업하고 실제 연결검사·부분 실행에 연결한다."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import shutil

base=Path(__file__).parent
path=base/'evaluation_plan.json'
plan=json.loads(path.read_text(encoding='utf-8'))
stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S')
backup=base/'_backup'/f'{stamp}_before_actual_smoke_and_D3'/path.name
backup.parent.mkdir(parents=True,exist_ok=False)
shutil.copy2(path,backup)
evidence=json.loads((base/'runtime_20261009_0232/runtime_verification.json').read_text(encoding='utf-8'))
registration=json.loads((base/'queue_registered_A_20261009.json').read_text(encoding='utf-8'))
snapshot=json.loads((base.parent/'gpu_backlog_20261008/A_snapshot_saluki_registered_20261009.json').read_text(encoding='utf-8'))
jobs={j['suite']:j for j in snapshot['manifest']['jobs'] if j['id'].startswith('saluki_')}
plan.update(weights_downloaded=True,status='smoke_passed_D3_actually_running_full_comparison_not_complete',runtime_runner_sha256=jobs['d3']['runner_sha256'],engine_commit='4ebdf2c74acce30883d8e34b7c70b3eb8146f2fe',runtime_runner_reference='program/scripts/plan_qa_bench/server/queues/saluki_eval_20261009.py',observed_at_utc=evidence['captured_at_utc'],saved_total_partial=184,completed_total=0,completed_suites=0,expected_suites=5,execution_report='final_project_cs/wiki/records/reports/2026-10-09_023533_saluki-install-smoke-and-evaluation.md',model_storage='A existing /dev/shm RAM; volatile; B root disk preservation receiving, not completed',local_off_machine_weight_archive_complete=False)
plan['smoke'].update(status='model_load_and_12_calls_passed; original_9_of_12_accuracy_is_separate',saved=12,parsed=12,errors=0,correct=9,max_prompt_tokens=1953,canonical_input_match=[12,12],runtime_evidence='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/runtime_verification.json')
for suite in plan['matched_suites']:
    key={'E/MX':'mx','D3':'d3','H':'h','D':'d','D2':'d2'}[suite['name']]
    suite.update(prompt_sha256=jobs[key]['prompt_sha256'],job_id=jobs[key]['id'],saved_partial_snapshot=184 if key=='d3' else 0,completed=0,status='running' if key=='d3' else 'ready_sequential_after_current_D3',complete=False)
plan['matched_suites'].sort(key=lambda s:['D3','E/MX','H','D','D2'].index(s['name']))
plan['state_change_backup']='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/'+str(backup.relative_to(base)).replace('\\','/')
temporary=path.with_suffix('.runtime-update.tmp')
with temporary.open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
temporary.replace(path)
print(json.dumps({'plan':str(path),'backup':str(backup),'status':plan['status'],'partial':plan['saved_total_partial'],'full_expected':plan['planned_total']}))
