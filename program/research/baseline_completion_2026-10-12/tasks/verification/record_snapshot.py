"""실행별 실제 수집·완료·실패를 합산 없이 새 증거 파일로 보존한다."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
now=datetime.now(ZoneInfo('Asia/Seoul'))
runs=[]
for folder in sorted((HERE/'runs').iterdir()):
    if not folder.is_dir():
        continue
    for progress in sorted(folder.glob('*-progress.jsonl')):
        label=progress.name.removesuffix('-progress.jsonl')
        rows=[json.loads(line) for line in progress.read_text(encoding='utf-8').splitlines()]
        collection_path=folder/(label+'-collection.json')
        collection=json.loads(collection_path.read_text(encoding='utf-8')) if collection_path.exists() else {}
        selected=collection.get('common_nodeids',[])+collection.get('travel_nodeids',[])
        finished=folder/(label+'-outcomes.json')
        termination=folder/(label+'-termination.json')
        before_path=folder/(label+'-source-before.json')
        before=json.loads(before_path.read_text(encoding='utf-8')) if before_path.exists() else {}
        changed=[key for key,value in before.items() if not (CS/key).exists() or hashlib.sha256((CS/key).read_bytes()).hexdigest()!=value]
        completed={row['nodeid'] for row in rows if row['when']=='call' or row['when']=='setup' and row['outcome'] in ('failed','skipped')}
        failures=[row for row in rows if row['outcome']=='failed']
        counts=Counter(row['outcome'] for row in rows if row['when']=='call' or row['when']=='setup' and row['outcome']=='skipped')
        status=json.loads(finished.read_text(encoding='utf-8')) if finished.exists() else {}
        runs.append({'label':label,'folder':folder.relative_to(ROOT).as_posix(),
            'selected':len(selected),'completed_unique':len(completed),'counts':dict(counts),
            'errors':[row['nodeid'] for row in failures if row['when']!='call'],
            'failure_families':dict(Counter(row['nodeid'].split('::')[0] for row in failures)),
            'failures':failures,'current_changed_since_start':changed,
            'finalized':finished.exists(),'exit':status.get('exit'),
            'finished_at_kst':status.get('finished_at_kst'),
            'termination':json.loads(termination.read_text(encoding='utf-8')) if termination.exists() else None})
output=HERE/'runs/2026-10-12_final_hash_1'/('validation-snapshot-'+now.strftime('%H%M%S')+'.json')
if output.exists():
    raise SystemExit('기존 증거가 있습니다.')
result={'at_kst':now.isoformat(),'scope':'실행별 결과를 분리. source 비교는 순차 관측이며 공유 코드 동결을 뜻하지 않음.','runs':runs}
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(output),'runs':[{k:row[k] for k in ('label','selected','completed_unique','counts','finalized','exit')} for row in runs]},ensure_ascii=False,indent=2))
