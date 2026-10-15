"""전용 DB 전체 실행 원본으로 현재 연결 관문을 대조합니다. 시험 subprocess는 실행하지 않습니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib, importlib.util, json, subprocess, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
sys.path.insert(0,str(CS))
from scripts.verify_dod_v11 import ITEMS, _state_of
from scripts.check_release_gate import _frozen_changes

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def outcomes(run):
    assert (run/'result.json').is_file(), f'Not finished: {run.name}'
    reports=[json.loads(line) for line in (run/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
    out={}
    for row in reports:
        node=row['nodeid']
        if row['outcome']=='failed':out[node]='ERROR' if row['when']!='call' else 'FAILED'
        elif row['outcome']=='skipped':out[node]='SKIPPED'
        elif row['when']=='call' and node not in out:out[node]='PASSED'
    return out

common=HERE/'checks/2026-10-12_055926_851705_isolated_integration'
travel=HERE/'checks/2026-10-12_060205_589376_isolated_integration'
results={}
runs=[]
groups={}
for label,run in [('common',common),('travel',travel)]:
    current=outcomes(run)
    collection=load(run/'collection.json')
    selected=set(collection[label+'_nodeids'])
    assert selected==set(current), f'Incomplete outcomes for {label}'
    assert not set(results)&set(current),'Suite overlap'
    groups[label]=selected
    results.update(current)
    result=load(run/'result.json')
    runs.append(dict(label=label,path=run.relative_to(ROOT).as_posix(),junit_sha256=digest(run/'junit.xml'),counts=dict(Counter(current.values())),source_changed=result['source_changed'],network_blocks=result['network_blocks'],exit=result['exit'],cleanup=load(run/'cleanup.json')))

nodes_by_path={}
for node,state in results.items():nodes_by_path.setdefault(node.split('::')[0],[]).append(state)
items=[]
for item in ITEMS:
    checks=[dict(nodeid=node,state=_state_of(results,node)) for node in item.checks]
    items.append(dict(number=item.number,title=item.title,mvp=item.mvp,checks=checks,passed=bool(checks) and all(c['state']=='PASSED' for c in checks)))
coverage=[]
for prefix in ['tests/security/','tests/contract/','tests/architecture/','eval/tests/']:
    subset={k:v for k,v in results.items() if k.startswith(prefix)}
    coverage.append(dict(prefix=prefix,total=len(subset),counts=dict(Counter(subset.values()))))

changed=_frozen_changes()
phase=subprocess.run([sys.executable,'-B','-m','scripts.map_commits_to_phase','--count','20','--strict'],cwd=CS,capture_output=True,text=True,encoding='utf-8',errors='replace')
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
outdir=HERE/'checks'/('final-gate-'+stamp)
outdir.mkdir(exist_ok=False)
(outdir/'commit-phase.log').write_text(phase.stdout+phase.stderr,encoding='utf-8')
report=dict(at_kst=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),scope='最新 격리 전체 실행의 원본 결과로 연결 검사 대조; 원래 subprocess 릴리스 래퍼 실행·출시 승인 아님'.replace('最新','최신'),runs=runs,unique_nodes=len(results),overlap=len(groups['common']&groups['travel']),coverage=coverage,legacy_linked_gate=dict(script_sha256=digest(CS/'scripts/verify_dod_v11.py'),passed=sum(x['passed'] for x in items),total=len(items),items=items,limit='v11 당시 문구는 현재 wiki 후속 계약을 대체하지 않음'),frozen_files=dict(changed=changed,passed=not changed),historical_commit_phase=dict(exit=phase.returncode,passed=phase.returncode==0,log='commit-phase.log',limit='현재 인명 책임이나 새 commit·push 작업을 뜻하지 않음'),remaining='자료 전제·실자료 정확도·개인 AI 외부 종단·환경 적용 인수는 별도')
(outdir/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=outdir.relative_to(ROOT).as_posix(),unique_nodes=len(results),coverage=coverage,linked_passed=report['legacy_linked_gate']['passed'],linked_total=len(items),frozen_ok=not changed,commit_phase_exit=phase.returncode),ensure_ascii=True))
