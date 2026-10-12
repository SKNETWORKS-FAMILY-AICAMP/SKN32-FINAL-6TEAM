"""통상 관측만 백업 후 갱신한다. 새 완료·실패가 있으면 결과 회수 단계로 넘긴다."""
import json, re, shutil, sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[3]
stamp=sys.argv[1]
results=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
research=ROOT/'program/research/daily_rag_slm'
target=research/'gpu_backlog_2026-10-08.json'
data=json.loads(target.read_text(encoding='utf-8'))
a=json.loads((results/f'A_snapshot_{stamp}.json').read_text(encoding='utf-8'))
b=json.loads((results/f'B_snapshot_{stamp}.json').read_text(encoding='utf-8'))
ac=json.loads((results/f'A_conditions_{stamp}.json').read_text(encoding='utf-8'))
bc=json.loads((results/f'B_conditions_{stamp}.json').read_text(encoding='utf-8'))
old=data['gpu_A']['state']['jobs'];new=a['state']['jobs']
terminal={'completed','completed_with_errors','failed'}
changes=[j for j,v in new.items() if v['status'] in terminal and old.get(j,{}).get('status')!=v['status']]
assert not changes, 'New terminal jobs require archival and reports: '+str(changes)
assert re.search(r'^\s*'+str(a['worker_pid'])+r'\s+\d+\s+\d+\s+python3.*gpu_eval_queue.py',a['processes'],re.M)
phase=data['gpu_B'].get('current_phase','full_training')
variant=data['gpu_B'].get('current_variant','winnow_e4b_oos')
audited_bases={'winnow_e4b_oos':'/root/hf_models/winnow-e4b-hf',
 'spark_s1_4b_oos':'/root/hf_models/spark_s1_4b',
 'jevify_e4b_oos':'/root/hf_models/jevify_e4b'}
assert variant in audited_bases, 'New training variant needs an explicit stage audit'
expected_process={
 'full_training':'qlora_train2.py '+audited_bases[variant],
 'basic_evaluation':'qlora_eval2.py '+audited_bases[variant],
}
assert phase in expected_process and expected_process[phase] in b['processes'], 'Current audited phase changed; collect results and audit next stage before updating'
assert bc['existing_base_config'] and bc['existing_train'] and bc['b56_markers']['SMOKE_DONE']
assert not bc['b56_markers']['ALLDONE'], 'B56 completed; collect its new results'
ready=len(ac['ready'])
assert ready>=3, 'Queue needs refill'
download_deferred=(data['gpu_B'].get('download_space_deferred_until_current_temporary_base_cleanup') is True
 and variant=='spark_s1_4b_oos' and bc['download_paths_present']['spark_s1_4b'])
assert int(bc['rounded_available_GB'].rstrip('G'))>=22 or download_deferred, 'Queued download needs resource review'
existing=data['gpu_B']['ready_without_model_download']
downloads=data['gpu_B']['queued_jobs_requiring_model_download']
queued=data['gpu_B']['queued_full_training_jobs']
assert existing+downloads==queued
backup=research/'_backup'/(datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_routine_'+stamp)
backup.mkdir(parents=True,exist_ok=False);shutil.copy2(target,backup/target.name)
data['gpu_A'].update({'snapshot':str((results/f'A_snapshot_{stamp}.json').relative_to(ROOT)).replace('\\','/'),
 'conditions_snapshot':str((results/f'A_conditions_{stamp}.json').relative_to(ROOT)).replace('\\','/'),
 'observed_at_utc':a['observed_at_utc'],'state':a['state'],'answers_saved_at_snapshot':a['answers'],
 'jobs_ready_waiting':ready,'instant_gpu_memory_and_utilization':a['gpu_snapshot'],'root_available_bytes':ac['root_space']['available_bytes']})
data['gpu_B'].update({'snapshot':str((results/f'B_snapshot_{stamp}.json').relative_to(ROOT)).replace('\\','/'),
 'conditions_snapshot':str((results/f'B_conditions_{stamp}.json').relative_to(ROOT)).replace('\\','/'),
 'observed_at_utc':b['observed_at_utc'],'instant_gpu_memory_and_utilization':b['gpu_snapshot'],
 'root_available_bytes':bc['root_space']['available_bytes'],'download_space_observed_GB_rounded_up':int(bc['rounded_available_GB'].rstrip('G'))})
data['latest_routine_observation']={'new_completed_jobs':0,'new_failed_jobs':0,'new_failed_or_unparsed_answers':0,
 'worker_restart':False,'queue_refill':False,'reason':f'No material completion or failure change;{ready} ready A jobs and{queued} queued B recipes remain.{existing} use an existing base;{downloads} need download preparation. Space must be rechecked after current temporary input cleanup before download.',
 'recorded_at':datetime.now().isoformat(),'backup':str(backup.relative_to(ROOT)).replace('\\','/')}
temporary=target.with_suffix('.tmp')
temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(target)
record={'new_completed':0,'new_failed':0,'ready_A':ready,'B_existing_base_recipes':existing,'B_automatic_download_recipes':downloads,
 'B_current_variant':variant,'B_current_phase':phase,'B_download_space_deferred':download_deferred,
 'B_future_download_space_must_be_rechecked':True,'queue_refill':False,'restart':False,'backup':str(backup.relative_to(ROOT)).replace('\\','/')}
with (results/f'routine_observation_{stamp}.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps(record,ensure_ascii=True))
