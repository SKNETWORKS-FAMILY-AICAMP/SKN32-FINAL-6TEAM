from pathlib import Path
from datetime import datetime
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
NOW=datetime.now().astimezone(); TAG=NOW.strftime('%Y-%m-%d_%H%M')+'_공항철도_공표승차시간_대조'
EV=CS/'wiki/records/evidence'/TAG; EV.mkdir(exist_ok=False)
RAW=ROOT/'datasets/mobility/raw'/TAG; RAW.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return p.relative_to(ROOT).as_posix()
def save(p,d):
 with p.open('x',encoding='utf8') as f: json.dump(d,f,ensure_ascii=False,indent=2)
base=CS/'wiki/records/evidence/2026-10-09_1321_공항철도_공식웹_대체정보_확보/final-integrity-v1.json'
prior=json.loads(base.read_text(encoding='utf8'))
checks={p:sha(ROOT/p)==h for p,h in {**prior['source_test_data_hashes'],**prior['artifact_hashes']}.items()}
assert len(checks)==286 and all(checks.values())
save(EV/'baseline-verification-v1.json',{'created_at':NOW.isoformat(),'checks':checks,'count':286})
facts=json.loads((Path(__file__).parent/'arex-published-hongik-v1.json').read_text(encoding='utf8'))
save(RAW/'published-minutes-v1.json',facts)
backups=[]
for p in [CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md',CS/'app/domains/travel_ops/instances/mobility/engine/runtime.py',CS/'app/domains/travel_ops/instances/mobility/engine/verify_time.py']:
 dest=p.parent/'_backup'/TAG/p.name;dest.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(p,dest);assert sha(p)==sha(dest)
 backups.append({'source':rel(p),'backup':rel(dest),'sha256':sha(p)})
save(EV/'backup-manifest-v1.json',{'created_at':NOW.isoformat(),'backups':backups})
debug=CS/'wiki/records/reports/debugs'/f'{TAG}.md'
debug.write_text('''# 공표되지 않은 출발을 승차 가능한 열차로 선택
## 미해결

홍대입구 공항철도 휴일 13:29 준비 시 verify_leg는 공식 일반열차 시간표에 없는13:30을 선택했습니다. 공식 다음 출발은13:33입니다. 현재 적재는 gzip 시간표를 우선하며 원자료의 열차 종류/정차 여부가 통합 시간표에서 비어 있고 적재 때 모든 출발을 승차 후보로 읽습니다.

위치: app/domains/travel_ops/instances/mobility/engine/verify_time.py:138,445,504 및 datasets/mobility/scripts/build_timetable_v1.py:218. 현재 저장 공항철도 홍대입구786행과 공식 평일/휴일 양방향682분의 차이는104행(그룹당26), 공식 분 누락0·일치 분 중복0입니다. 104행의 원래 열차 종류는 현재 보유 축소자료로 확정하지 않습니다.

재현: 실제자료로 runtime.build_verifier(data_dir=<datasets/mobility/processed 절대경로>,gh_url='',seoul_key='',quiet=True)를 구성하고 _v.verify_leg(0,{'line':'공항철도','from':'홍대입구','to':'공덕'},809,'holiday',False)를 실행합니다. 기존 depart_min=810. 공식 근거 https://www.airportrailroad.com/train/normal/info/030/0 .

위험: 실시간 응답 실패 때 시간표 대체 계산이 탈 수 없는 열차를 선택하고 출발/환승 안내를 앞당길 수 있습니다. 공식 표는 분 단위 예정시각이며 실제 도착 정확도 측정이 아닙니다. 기존 시간표/과거 보고서는 보존합니다.
''',encoding='utf8')
wiki=CS/'wiki/teams/mobility.md'
with wiki.open('a',encoding='utf8') as f: f.write(f'''

## {TAG} 공표 승차 시간 대조의 내부 계약

보유 시간표의 출발이 실제 정차/승차 시각인지 공식 운영기관의 완전한 역별 평일·휴일 양방향 표와 대조합니다. 별도 published_boarding_timetable_v1.json은 원시간표 SHA256에 묶인 분 단위 사실값이며 원본 행은 삭제/수정하지 않습니다. 같은 역·노선·요일·방향에서 공식 모든 분이 원자료와 정확히1대1 대응할 때만 그 집합 안의 행을 승차 후보로 읽고 밖의 행은 적재 제외 건수로 드러냅니다. 공식 분 누락·중복·잘못된 스키마·원자료 판 불일치는 조용히 보정하지 않고 적재를 실패시킵니다. 열차 종류·초·행선지·새 열차를 추정하지 않습니다. 적용 범위는 확보한 홍대입구4그룹뿐이며 다른 역은 기존대로입니다.

대조 자료의 생성/교체/삭제와 내용 변경은 런타임 재구성과 기존 출발 안내의 입력 판 대조에 반영합니다. 없는 환경의 기존 계산은 유지하며 현재 자료가 있는 환경에서 읽기 오류를 없는 것으로 처리하지 않습니다. 원시간표 수집일/신선도는 새 대조 조회일로 바꾸지 않습니다. 공표 예정값과 실제 도착예측·실탑승을 구분합니다. 검증 결과는 새 보고서에 보존합니다.
''')
state={'tag':TAG,'evidence':rel(EV),'raw':rel(RAW),'debug':rel(debug),'prepared_at':NOW.isoformat(),'base_manifest':rel(base)}
save(Path(__file__).parent/'published-boarding-state-v1.json',state)
print(json.dumps(state,ensure_ascii=False))
