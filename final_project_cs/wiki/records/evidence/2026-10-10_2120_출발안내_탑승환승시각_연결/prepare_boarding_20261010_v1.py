from pathlib import Path
from datetime import datetime
import hashlib, json, shutil

ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
TAG='2026-10-10_2120_출발안내_탑승환승시각_연결'
EV=CS/'wiki/records/evidence'/TAG
EV.mkdir(exist_ok=False)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):
    return p.relative_to(ROOT).as_posix()
old=json.loads((CS/'wiki/records/evidence/2026-10-10_1521_동일요청좌표_도보웹대조/final-integrity-v1.json').read_text(encoding='utf8'))
previous=dict(old['source_test_data_hashes'],**old['artifact_hashes'])
missing=[k for k in previous if not (ROOT/k).exists()]
assert not missing,missing
baseline={k:sha(ROOT/k) for k in previous}
changed=[k for k in previous if previous[k]!=baseline[k]]
backups=[]
for path in [CS/'app/domains/travel_ops/instances/mobility/engine/departure_observer.py',CS/'app/domains/travel_ops/components/watch/trip_reminders.py',CS/'wiki/teams/mobility.md']:
    target=path.parent/'_backup'/TAG/path.name
    target.parent.mkdir(parents=True,exist_ok=False)
    shutil.copy2(path,target)
    assert sha(path)==sha(target)==baseline[rel(path)]
    backups.append({'source':rel(path),'backup':rel(target),'sha256':sha(path)})
    if path.suffix=='.py':
        legacy=CS/'legacy'/TAG/path.relative_to(CS)
        legacy.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,legacy)
        backups.append({'source':rel(path),'backup':rel(legacy),'sha256':sha(path)})
wiki=CS/'wiki/teams/mobility.md'
before=sha(wiki)
contract='''

## 2026-10-10 출발 안내의 재계산 승차·환승 시각 계약

현재 출발 재검증은 `boarding_steps` 목록을 선택 필드로 반환합니다. 검증기가 반환한 버스·지하철 구간의 승차/하차 시각이 있는 경우에만 순서대로 만들며, 각 행은 `idx`, `mode`, `service`, `from`, `to`, `board_at`, `alight_at`, `boarding_basis`, `ride_basis`를 가집니다. 시각은 시간대가 있는 ISO8601 절대시각입니다. 첫 승차에 정확히 대응한 현재 도착 예측을 적용했을 때만 `boarding_basis=realtime_arrival_prediction`이며 이후 승차는 `timetable_model`, 승차 소요는 모두 `ride_basis=model`입니다. 지하철 첫 승차에는 선택한 `train_number`와 확인한 `towards` 종착역을 함께 실을 수 있습니다. 미래 환승을 현재 열차 관측으로 바꾸거나 추가 API 조회하지 않습니다.

출발 안내는 이 목록이 있으면 구간별 승차·하차 시각과 근거 구분을 번역 가능한 문구틀/원값에 붙입니다. 시각 역전·중복 구간·필수값 누락·실시간 근거 오표시는 안내 발행 실패로 드러냅니다. 선택 필드가 없는 기존 콜백과 직접 도보는 기존 총 소요 안내를 유지합니다. 모델 시각은 실제 탑승·하차 또는 정시 운행 보장이 아닙니다. 재검증 실패/늦음/통제 상태에서는 상세 안내도 발행하지 않습니다.
'''
assert sha(wiki)==before
wiki.write_text(wiki.read_text(encoding='utf8')+contract,encoding='utf8')
state={'tag':TAG,'created_at':datetime.now().astimezone().isoformat(),'baseline':baseline,'changed_since_previous':changed,'backups':backups,'wiki_contract_sha256':sha(wiki)}
(EV/'baseline-v1.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'baseline_files':len(baseline),'changed_since_previous':changed,'backups':len(backups)}))
