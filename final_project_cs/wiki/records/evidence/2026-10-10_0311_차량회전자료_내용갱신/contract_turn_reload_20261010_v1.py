from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';sys.stdout.reconfigure(encoding='utf8')
state=json.loads((Path(__file__).parent/'turn-reload-state-20261010-v1.json').read_text(encoding='utf8'));EV=ROOT/state['evidence']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((EV/'baseline-v1.json').read_text(encoding='utf8'))
assert all(sha(ROOT/p)==h for p,h in baseline['hashes'].items()),'진행 중 다른 작업 변경 감지'
code=CS/'app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py';wiki=CS/'wiki/teams/mobility.md';stamp=datetime.now().astimezone().strftime('%Y-%m-%d_%H%M%S_회전내용갱신_수정전')
backups=[]
for p in (code,wiki):
 b=p.parent/'_backup'/stamp/p.name;b.parent.mkdir(parents=True);shutil.copy2(p,b)
 backups.append({'path':p.relative_to(ROOT).as_posix(),'backup':b.relative_to(ROOT).as_posix(),'sha256':sha(p)})
with (EV/'backup-manifest-v1.json').open('x',encoding='utf8') as f:json.dump(backups,f,ensure_ascii=False,indent=2)
debug=CS/'wiki/records/reports/debugs'/(state['tag']+'.md')
with debug.open('x',encoding='utf8') as f:f.write(f'''# 크기·수정시각이 같은 회전자료 교체를 놓칩니다

## 미해결

위치: [회전자료 적재](../../../../../app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py)의 load. 파일 크기와 mtime_ns만 비교해 캐시를 재사용합니다. 같은 메타데이터로 원자 교체한 정상 규칙 변경·손상 JSON·다른 그래프 해시·잘못된 방향 관계가 다음 차량 요청에 반영되지 않았습니다.

재현 명령: `python -m pytest tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py -q -p no:cacheprovider`. 수정 전 4실패·1통과. [실제 JUnit 원문](../../evidence/{state['tag']}/before-v1.xml). 합성 도로의 통제 재현이며 실제 교통 관측이 아닙니다.

위험: 자료 갱신 뒤 옛 회전 허용/금지를 쓰거나 손상된 새 자료를 정상으로 무시할 수 있습니다. 실제 배포에서 발생한 건수는 확인하지 않았습니다. 그래프 파일 자체의 같은 메타데이터 내용 교체·탐색 도중 교체는 별도 범위입니다.
''')
plan=CS/'wiki/records/plans'/(state['tag']+'.md')
with plan.open('x',encoding='utf8') as f:f.write('''# 차량 회전자료 내용 교체 검증

목표: 회전 제한 파일의 크기·수정시각이 같아도 다음 차량 요청에 새 내용을 적용하고, 잘못된 내용이면 명시적으로 실패시킵니다.

실시간 대체 소스는 공식 정적 웹만 열렸고 브라우저 초기화·공개 HTML 조회가 실패해 열차ID·생성시각·역 귀속을 추가 확인하지 못했습니다. 제한 API는 공유 사용량 미확인으로 호출하지 않습니다. 다음 우선순위인 기존 차량 회전 제약의 자료 갱신 결함을 최소 단위로 해결합니다.

범위: turn_restrictions.load의 파일 내용 판별만 수정. 한 번 읽은 바이트의 SHA256으로 캐시를 비교하고 그 바이트를 파싱합니다. 그래프 결합 검증·삭제 실패·정적 단순 적용 범위와 차/도보/자전거 분리는 유지합니다. 같은 내용은 기존 테이블을 재사용해 큰 그래프를 매 요청 재해시하지 않습니다.

완료 조건: 수정 전 실패4건 재현, 신규5건·기존 관련 회귀 통과, 실제 보유 자료의 변경 없는 경로 교대 재생, 다른 작업 해시 보존, 백업·보고서·정적 시각화 보존. 실제 도로 통행·웹 경로 정확도·전체21개 기능 완료로 세지 않습니다.
''')
assert sha(wiki)==backups[1]['sha256']
with wiki.open('a',encoding='utf8') as f:f.write(f'''\n\n## {state['tag']} 회전자료 내용 갱신 계약

차량 회전 제한 파일은 크기·수정시각만으로 기존 적재본을 재사용하지 않습니다. 차량 요청마다 파일 바이트를 한 번 읽어 SHA256으로 내용 판을 비교하고, 변경 시 그 바이트를 파싱해 그래프 결합/방향 관계를 재검증합니다. 같은 내용은 기존 테이블을 재사용하고 큰 도로 그래프를 다시 해시하지 않습니다. 적재 뒤 삭제·읽기 오류·손상은 RouterDown으로 드러내며 옛 규칙으로 복귀하지 않습니다. 도보·자전거와 기존 단순 제약 범위는 그대로입니다. 도로 그래프 파일 자체의 같은 메타데이터 교체나 탐색 도중 교체까지 보장하는 계약은 아닙니다. [결함 기록](../records/reports/debugs/{state['tag']}.md).\n''')
with (EV/'before-v1-run.json').open('x',encoding='utf8') as f:json.dump({'command':'python -m pytest tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py -q -p no:cacheprovider --basetemp=../.tmp/mobility_complete_20261008/turn_reload_before_v1 --junitxml=wiki/records/evidence/'+state['tag']+'/before-v1.xml','cwd':'final_project_cs','failed':4,'passed':1,'total':5,'evidence':'before-v1.xml','full_console_log_saved':False},f,ensure_ascii=False,indent=2)
print(json.dumps({'code_sha256':sha(code),'backups':len(backups),'debug':debug.relative_to(ROOT).as_posix()},ensure_ascii=False))
