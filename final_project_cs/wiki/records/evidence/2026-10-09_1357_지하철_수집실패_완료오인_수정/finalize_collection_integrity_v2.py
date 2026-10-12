from pathlib import Path
from datetime import datetime
import json, shutil, hashlib, re, subprocess, sys, os

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'; NOW=datetime.now().astimezone()
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8')); EV=ROOT/state['evidence']
old=json.loads((EV/'final-integrity-v1.json').read_text(encoding='utf8'))
REPORT=ROOT/old['report']; HTML=ROOT/old['assets']/'mobility-readiness.html'; WIKI=CS/'wiki/teams/mobility.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
backups=[]
for p in [REPORT,HTML,WIKI]:
    b=p.parent/'_backup'/NOW.strftime('%Y-%m-%d_%H%M%S_최종검사보완')/p.name
    b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
    backups.append({'path':p.relative_to(ROOT).as_posix(),'backup':b.relative_to(ROOT).as_posix(),'sha256':sha(p)})
(EV/'finalization-backups-v2.json').write_text(json.dumps(backups,ensure_ascii=False,indent=2),encoding='utf8')
text=HTML.read_text(encoding='utf8')
text=re.sub(r'<label for="filter">.*?</select>','',text)
text=re.sub(r'<script>.*?</script>','',text,flags=re.S)
text=text.replace('<h2>21개 기능의 현재 판단</h2>','<p>추가 문서 상태 검사: 89/98 = 90.8%, 기존 결함 문서9개의 상태 표기 누락. 기능 검사505/505와 별도 결과입니다.</p><h2>21개 기능의 현재 판단</h2>')
HTML.write_text(text,encoding='utf8')
args=[sys.executable,'C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py',str(HTML)]
p=subprocess.run(args,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
(EV/'visual-self-check-v2.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf8'); assert p.returncode==0,p.stdout
notes='''

## 최종 추가 검사 정정

추가 문서 상태 검사는 89/98 = 90.8% 통과·9건 실패입니다. 기존 결함 문서9개에 `## 해결됨`/`## 미해결` 표기가 없어 실패했으며, 이번 새 결함 문서의 상태 표기는 통과했습니다. 기능 관련505/505 통과와 다른 검사입니다. [전체 원문](../evidence/TAG/debug-status-v1.log)에 실패 문서 목록을 보존했습니다. 이전 문서의 해결 여부를 추정해 닫지 않았고 별도 확인이 남았습니다.

시각화 자체 검사는 처음에 일반 필터 JavaScript를 모션 제어 코드로 판단해 실패했습니다. 필터를 제거한 정적 시각화로 바꾸고 접근성·단일 파일 검사 재실행을 통과했습니다. [재검사](../evidence/TAG/visual-self-check-v2.log). 원래 HTML/보고서/wiki는 [추가 백업](../evidence/TAG/finalization-backups-v2.json)에 보존했습니다. 브라우저 렌더링은 여전히 미확인입니다.
'''.replace('TAG',state['tag'])
with REPORT.open('a',encoding='utf8') as f:f.write(notes)
with WIKI.open('a',encoding='utf8') as f:f.write('\n추가 검사: 기능505/505와 별도로 문서 상태89/98통과·기존9건표기누락 실패. 새 결함 문서 상태는 통과했으며 과거 문서를 추정해 닫지 않았습니다. 시각화 필터를 제거하고 정적 단일파일 검사 재통과·브라우저 렌더링 미확인. 최종 파일 근거는 같은 evidence의 final-integrity-v2.json입니다.\n')
sources=old['source_test_data_hashes']; assert all(sha(ROOT/path)==h for path,h in sources.items())
artifacts={path:sha(ROOT/path) for path in old['artifact_hashes']}
for path in EV.iterdir():
    if path.is_file() and path.name!='final-integrity-v2.json':artifacts[path.relative_to(ROOT).as_posix()]=sha(path)
all_backups=old['backups']+backups; assert all(sha(ROOT/b['backup'])==b['sha256'] for b in all_backups)
current={**old,'created_at':NOW.isoformat(),'source_test_data_hashes':sources,'artifact_hashes':artifacts,'backups':all_backups,'additional_doc_test':{'passed':89,'failed':9,'total':98},'visual_self_check':True,'browser_rendered':False}
with (EV/'final-integrity-v2.json').open('x',encoding='utf8') as f:json.dump(current,f,ensure_ascii=False,indent=2)
allchecks=[sha(ROOT/path)==h for section in (sources,artifacts) for path,h in section.items()];assert all(allchecks)
with (EV/'final-validation-v2.json').open('x',encoding='utf8') as f:json.dump({'hashes_checked':len(allchecks),'hashes_matched':sum(allchecks),'backups_checked':len(all_backups),'backups_matched':len(all_backups),'feature_tests':{'passed':505,'new':38,'deselected':165},'document_tests':{'passed':89,'failed':9},'visual_self_check':True,'browser_rendered':False},f,ensure_ascii=False,indent=2)
shutil.copy2(Path(__file__),EV/Path(__file__).name)
print(json.dumps({'hashes':len(allchecks),'backups':len(all_backups),'visual':'passed','document_status':'89 passed, 9 failed'},ensure_ascii=False))
