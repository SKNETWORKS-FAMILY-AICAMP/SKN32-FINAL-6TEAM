"""통상 관측은 실행 상태만 갱신한다. 완료·실패가 없으면 새 성과 리포트를 만들지 않는다."""
import json, shutil
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parents[3]
results=root/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
research=root/'program/research/daily_rag_slm'
backup=research/'_backup/2026-10-08_1023_queue_observation'
backup.mkdir(parents=True,exist_ok=True)
a=json.loads((results/'A_snapshot_1019.json').read_text(encoding='utf-8'))
b=json.loads((results/'B_snapshot_1019.json').read_text(encoding='utf-8'))
conditions=json.loads((results/'B_conditions_1023.json').read_text(encoding='utf-8'))
assert a['state']['jobs']['frog_mx']['status']=='running'
assert conditions['configs']['/root/hf_models/gemma-4-E4B-it/config.json']
assert int(conditions['download_space_check'].splitlines()[-1].strip().rstrip('G'))>=22
status=research/'gpu_backlog_2026-10-08.json'
assert not (backup/status.name).exists(), 'Already recorded'
shutil.copy2(status,backup/status.name)
data=json.loads(status.read_text(encoding='utf-8'))
data['gpu_A'].update({'observed_at':'2026-10-08T10:20:00+09:00','snapshot':str((results/'A_snapshot_1019.json').relative_to(root)).replace('\\','/'),
 'answers_saved_at_snapshot':a['answers'],'state':a['state'],'jobs_completed':1,'jobs_running':1,'jobs_ready_waiting':15,'instant_gpu_memory_and_utilization':a['gpu_snapshot']})
data['gpu_B'].update({'observed_at':'2026-10-08T10:23:00+09:00','snapshot':str((results/'B_snapshot_1019.json').relative_to(root)).replace('\\','/'),
 'conditions_snapshot':str((results/'B_conditions_1023.json').relative_to(root)).replace('\\','/'),
 'instant_gpu_memory_and_utilization':b['gpu_snapshot'],'jobs_running':1,'queued_full_training_jobs':4,
 'ready_with_existing_automatic_preparation':4,'ready_without_model_download':2,'queued_jobs_requiring_model_download':2,
 'download_space_observed_GB_rounded_up':22,
 'readiness_note':'B54 downloads its two inputs automatically; current first-download threshold14GB and second22GB pass at this observation. Recheck space after current adapter/conversion and after each download; B56 has existing Gemma base and completed smoke. Download preparation is separate from completed training.',
 'next_executable':'B54 spark_s1_4b_oos input download, smoke and full training after current Winnow training/evaluation',
 'b56_status':'SMOKE_DONE; waiting for ALLDONE_B54; no completed cosine/finch full training'})
data['latest_routine_observation']={'new_completed_jobs':0,'new_failed_jobs':0,'worker_restart':False,'queue_refill':False,
 'reason':'15 prepared A evaluations and4 existing executable B recipes with automatic input preparation remain queued; no material result change',
 'backup':str(backup.relative_to(root)).replace('\\','/')}
tmp=status.with_suffix('.tmp')
tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
tmp.replace(status)
# 공유 파일에 인프라의 파일시스템 호스트가 남지 않게 관측 원본은 git 밖 백업에 보존하고 표시를 줄인다.
condition_file=results/'A_conditions_1021.json'
raw=json.loads(condition_file.read_text(encoding='utf-8'))
raw['disk']=[' '.join(line.split()[1:]) for line in raw['disk'].splitlines()[1:]]
condition_file.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
print('OBSERVATION_RECORDED; no new completed or failed jobs; no duplicated worker')
