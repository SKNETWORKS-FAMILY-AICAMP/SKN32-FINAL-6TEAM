from pathlib import Path
from datetime import datetime
import hashlib, json, shutil, re

ROOT=Path(__file__).resolve().parents[2]
TAG='2026-10-10_1521_동일요청좌표_도보웹대조'
EV=ROOT/'final_project_cs/wiki/records/evidence'/TAG
RAW=ROOT/'datasets/mobility/raw'/TAG
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):
    return p.relative_to(ROOT).as_posix()
manifest=EV/'final-integrity-v1.json'
current=json.loads(manifest.read_text(encoding='utf8'))
backups=[]
for source in [RAW/'arex-assessment-v1.json',manifest]:
    target=source.parent/'_backup'/'2026-10-10_1533_표시필드명_정확화'/source.name
    target.parent.mkdir(parents=True,exist_ok=False)
    shutil.copy2(source,target)
    digest=sha(source)
    assert sha(target)==digest
    backups.append({'source':rel(source),'backup':rel(target),'sha256':digest})
assessment=json.loads((RAW/'arex-assessment-v1.json').read_text(encoding='utf8'))
assert assessment['ui_fields'][0]=='formType'
assessment['ui_fields'][0]='formTypeA'
assessment['ui_fields_scope']='공개 inline 렌더링 코드에서 사용한 필드명; 원 응답 전체 스키마는 미확인'
(RAW/'arex-assessment-v1.json').write_text(json.dumps(assessment,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(__file__,EV/Path(__file__).name)
report=ROOT/'final_project_cs/wiki/records/reports'/f'{TAG}.md'
missing=[]
links=re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf8'))
local=[x for x in links if not x.startswith('https://')]
for link in local:
    if not (report.parent/link).resolve().exists():
        missing.append(link)
assert not missing,missing
verification={'checked_at':datetime.now().astimezone().isoformat(),'report_local_links_checked':len(local),'missing':missing,'field_correction':'공개 코드의 실제 필드명 formTypeA로 정확화; 원판 백업 보존','pytest_exit_code':0,'pytest_shutdown_console_warning':'41통과 후 pyreadline3 소멸자 Windows 핸들 오류가 stderr에 기록됨; 시험 실패/오류0, 실행 종료코드0','browser_render_verified':False}
with (EV/'publication-validation-v1.json').open('x',encoding='utf8') as f:
    json.dump(verification,f,ensure_ascii=False,indent=2)
current['backups']+=backups
current['created_at']=datetime.now().astimezone().isoformat()
current['artifact_hashes']={k:sha(ROOT/k) for k in current['artifact_hashes']}
for name in [Path(__file__).name,'publication-validation-v1.json']:
    current['artifact_hashes'][rel(EV/name)]=sha(EV/name)
allhashes=dict(current['source_test_data_hashes'],**current['artifact_hashes'])
assert all(sha(ROOT/k)==v for k,v in allhashes.items())
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in current['backups'])
manifest.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'hashes_checked':len(allhashes),'backups_checked':len(current['backups']),'report_links_checked':len(local),'missing_links':missing}))
