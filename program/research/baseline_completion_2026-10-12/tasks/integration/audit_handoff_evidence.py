"""담당 원본 명세와 현재 소스를 대조하고, 지식 자료의 구체적 정합성 위험을 기록합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def compare(label, manifest, entries):
    rows=[]
    for path, expected in entries:
        target=CS/path
        current=sha(target) if target.is_file() else None
        rows.append(dict(path=path,expected=expected.lower(),current=current,same=current==expected.lower()))
    return dict(label=label,manifest=manifest.relative_to(ROOT).as_posix(),manifest_sha256=sha(manifest),total=len(rows),same=sum(x['same'] for x in rows),changed=[x for x in rows if not x['same']])

auth=HERE.parent/'auth/source-manifest.json'
orch=HERE.parent/'orchestration/scope-sha256.json'
sql=ROOT/'program/research/migration_safety_2026-10-12/candidate-manifest-v2.json'
comparisons=[compare('auth',auth,[(x['path'],x['sha256']) for x in load(auth)]),
 compare('orchestration',orch,load(orch).items()),
 compare('SQL candidate',sql,[('app/infrastructure/db/migrations/'+p,h) for p,h in load(sql)['sha256'].items()])]

junit_paths=[HERE.parent/'auth/isolated-20261012_044335.xml',HERE.parent/'orchestration/unit-final.xml',ROOT/'program/research/migration_safety_2026-10-12/final-unit-results-v1.xml',ROOT/'program/research/migration_safety_2026-10-12/db-results-v2.xml']
junit=[]
for p in junit_paths:
    cases=ET.parse(p).getroot().findall('.//testcase')
    counts={x:sum(c.find(x) is not None for c in cases) for x in ['failure','error','skipped']}
    junit.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),total=len(cases),passed=len(cases)-sum(counts.values()),**counts))

manifest=CS/'knowledge/travel/manifest.json'
material=[]
patterns={'unqualified_72h':r'72\s*시간','fixed_24h':r'24\s*시간','human_queue':r'담당자|상담원|사람에게|사람이\s*(?:본|판단|내용)|사람\s*손', 'assumed_auto_limit':r'두\s*번까지|2회까지|3회째|세\s*번째'}
for entry in load(manifest)['documents']:
    p=manifest.parent/entry['file']
    text=p.read_text(encoding='utf-8')
    material.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),declared_sections=entry['section_count'],actual_sections=len(re.findall(r'^## ',text,re.M)),findings=[dict(kind=kind,line=i,text=line) for kind,pat in patterns.items() for i,line in enumerate(text.splitlines(),1) if re.search(pat,line)]))

now=datetime.now(ZoneInfo('Asia/Seoul'))
output=HERE/'checks'/('handoff-evidence-'+now.strftime('%Y-%m-%d_%H%M%S')+'.json')
out=dict(at_kst=now.isoformat(),comparisons=comparisons,junit=junit,corpus=dict(manifest=manifest.relative_to(ROOT).as_posix(),sha256=sha(manifest),documents=len(material),sections=sum(x['actual_sections'] for x in material),documents_with_review_flags=sum(bool(x['findings']) for x in material),files=material),limitations=['일치하는 소스 해시는 기존 실행의 범위를 확대하지 않음','지식 문구 검색은 검토 후보이며 정책 무효·불법 여부 판정이 아님','벡터를 만들거나 업무 DB·외부 모델을 호출하지 않음','SQL 후보 이후 변경은 최신 격리 안전 실행기의 SQL 로그·JUnit으로 별도 확인','원본 담당 명세는 수정하지 않음'])
output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=output.relative_to(ROOT).as_posix(),comparisons=[dict(label=x['label'],total=x['total'],same=x['same'],changed=[r['path'] for r in x['changed']]) for x in comparisons],junit=junit,corpus={k:out['corpus'][k] for k in ['documents','sections','documents_with_review_flags']}),ensure_ascii=True))
