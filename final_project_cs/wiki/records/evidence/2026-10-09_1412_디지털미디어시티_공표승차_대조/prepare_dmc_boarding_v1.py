from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];sys.stdout.reconfigure(encoding='utf8')
NOW=datetime.now().astimezone(); TAG=NOW.strftime('%Y-%m-%d_%H%M')+'_디지털미디어시티_공표승차_대조'
EV=ROOT/'final_project_cs/wiki/records/evidence'/TAG;EV.mkdir()
RAW=ROOT/'datasets/mobility/raw'/TAG;RAW.mkdir(parents=True)
DEBUG=ROOT/'final_project_cs/wiki/records/reports/debugs'/(TAG+'.md')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def save(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
prior=json.loads((ROOT/'final_project_cs/wiki/records/evidence/2026-10-09_1357_지하철_수집실패_완료오인_수정/final-integrity-v2.json').read_text(encoding='utf8'))
hashes=prior['source_test_data_hashes']|prior['artifact_hashes']
assert all(sha(ROOT/p)==h for p,h in hashes.items()),'baseline changed'
save(EV/'baseline-v1.json',{'matched':len(hashes),'total':len(hashes),'hashes':hashes})
backups=[]
for p in [ROOT/'datasets/mobility/processed/mobility/published_boarding_timetable_v1.json',ROOT/'datasets/mobility/processed/mobility/MANIFEST_git_v1.json',ROOT/'final_project_cs/wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md']:
 b=p.parent/'_backup'/TAG/p.name;b.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(p,b)
 backups.append({'path':rel(p),'backup':rel(b),'sha256':sha(p)})
save(EV/'backup-manifest-v1.json',backups)
facts=json.loads((Path(__file__).parent/'dmc-published-facts-v1.json').read_text(encoding='utf8'))
save(RAW/'official-minute-facts-v1.json',facts)
shutil.copy2(Path(__file__).parent/'dmc-published-preaudit-v1.json',EV/'before-data-audit-v1.json')
state={'tag':TAG,'evidence':rel(EV),'raw':rel(RAW),'debug':rel(DEBUG),'prepared_at':NOW.isoformat(),'previous_integrity':'final_project_cs/wiki/records/evidence/2026-10-09_1357_지하철_수집실패_완료오인_수정/final-integrity-v2.json'}
save(Path(__file__).parent/'dmc-published-state-v1.json',state)
wiki=ROOT/'final_project_cs/wiki/teams/mobility.md'
with wiki.open('a',encoding='utf8') as f:f.write(f'\n\n## {TAG} 공식 시간표 확대 계약\n\n공식 운영기관 디지털미디어시티 일반열차 평일·휴일 양방향5~24시 완전 표4그룹의682분을 기존 원시간표와 정확히1대1 대조한 범위만 승차 후보에 연결합니다. 홍대입구 기존4그룹과 원시간표 행·수집일·해시는 그대로 보존합니다. 대조 밖104행은 적재 후보에서 제외하며 열차종류·정차 여부를 추정하지 않습니다. 공표 자료8그룹과 명세 해시만 갱신하고 원자료 누락/중복 시 적재 실패 계약을 유지합니다. 공표 시각은 실제 ETA나 실탑승 측정이 아닙니다. 새 조회시각은 대조 자료에만 붙이고 원자료 신선도를 바꾸지 않습니다. 변경 전후 실제 자료 교대 재생과 다른 그룹 불변·제품 입력 판 변경·관련 회귀 검사 뒤 결과를 새 보고서에 남깁니다.\n')
with DEBUG.open('x',encoding='utf8') as f:f.write(f'# 디지털미디어시티 공표 밖 출발의 승차 후보 혼입\n\n## 미해결\n\n{NOW.isoformat()} 공식 AREX 일반열차 표4그룹682분과 보유786행을 대조했습니다. 공식 모든 분은 정확히1행 대응하나104행이 표 밖에 있습니다. 현재 공표 대조는 홍대입구만 적용되어 디지털미디어시티에서 이104행이 후보로 남습니다. 원행의 종류/통과 여부는 미확정입니다. [사전 대조](../../evidence/{TAG}/before-data-audit-v1.json)·[공식 표]({facts["source_url"]}).\n\n평일·휴일 서울방향13:26 준비 시 기존13:27:40이 먼저 선택되는지, 공항방향13:37 준비 시13:38:30이 선택되는지 실제 원자료로 재생합니다. 공식 표 기준 예상 후보는 각각13:29/13:39입니다.\n')
print(json.dumps({'state':state,'baseline':len(hashes),'backups':len(backups)},ensure_ascii=False))
