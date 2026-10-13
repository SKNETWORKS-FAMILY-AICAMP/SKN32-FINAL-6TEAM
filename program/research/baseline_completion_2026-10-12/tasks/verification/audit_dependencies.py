"""담당별 소스 해시와 실제 XML 시험 집계를 읽기 전용으로 대조한다."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
TASKS = HERE.parent
result = {'at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'owners':{},'scope':'담당 실행 근거의 링크·해시·개수 대조. 제품 전체·독립 검토·배포 승인 아님.'}
for owner, filename, kind in (('auth','source-manifest.json','list'),('orchestration','scope-sha256.json','dict'),('operations','source-manifest.json','files')):
    path = TASKS/owner/filename
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = [{'path':key,'sha256':value} for key,value in data.items()] if kind=='dict' else data if kind=='list' else data['files']
    observed=[]
    for row in rows:
        rel = row['path'].replace('\\','/')
        file = ROOT/rel if rel.startswith(('final_project_cs/','program/','scratch/')) else CS/rel
        actual = hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
        expected = row['sha256'].lower()
        observed.append({'path':rel,'recorded':expected,'actual':actual,'matches':actual==expected})
    result['owners'][owner]={'manifest':path.relative_to(ROOT).as_posix(),'files':observed}
xml_paths = [TASKS/'auth/isolated-20261012_044335.xml',TASKS/'orchestration/unit-final.xml',ROOT/'scratch/operations-20261012/backend-final-v5.xml']
result['xml'] = []
for path in xml_paths:
    root=ET.parse(path).getroot()
    rows=list(root.iter('testcase'))
    counts={'total':len(rows),'failures':sum(row.find('failure') is not None for row in rows),'errors':sum(row.find('error') is not None for row in rows),'skipped':sum(row.find('skipped') is not None for row in rows)}
    counts['passed']=counts['total']-counts['failures']-counts['errors']-counts['skipped']
    result['xml'].append({'path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**counts})
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%H%M%S')
output=HERE/'runs/2026-10-12_clean_travel'/('dependencies_'+stamp+'.json')
if output.exists(): raise SystemExit('이미 있는 결과 이름입니다.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(output),'owners':{owner:{'matches':sum(row['matches'] for row in data['files']),'total':len(data['files']),'mismatch':[row['path'] for row in data['files'] if not row['matches']]} for owner,data in result['owners'].items()},'xml':result['xml']},ensure_ascii=False,indent=2))
