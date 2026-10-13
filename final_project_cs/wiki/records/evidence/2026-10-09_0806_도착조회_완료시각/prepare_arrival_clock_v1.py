from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_도착조회_완료시각'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
backups = []
for name in ('app/domains/travel_ops/ports/data_sources/seoul_bus.py',
             'app/domains/travel_ops/instances/mobility/engine/departure_observer.py', 'wiki/teams/mobility.md'):
    p = cs / name
    b = p.parent / '_backup' / tag / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    backups.append({'source': p.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(),
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
debug = f'wiki/records/reports/debugs/{tag}_정상_신규응답을_미래시각으로_거절.md'
with (cs / debug).open('x', encoding='utf8') as f:
    f.write('# 신규 버스 응답의 조회 완료 시각 누락\n\n## 미해결\n\nseoul_bus.boardable_arrival는 조회 시작 now를 그대로 선택 함수에 넘깁니다. TravelSource는 정상 응답을 받은 뒤 confirmed_at을 찍으므로 지연이 있는 새 응답은 confirmation_in_future로 거절될 수 있습니다. departure_observer도 confirmed_at<=조회 시작 now만 허용합니다. 실제 응답 대기 시간을 출발/접근/마감 판정에 포함하는 통제 재현이 필요합니다. 실제 API 호출 없이 시계를 진행시킨 주입 transport로 먼저 확인합니다.\n')
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'\n\n## {tag} 도착 조회 완료 시각과 출발 재검증 계약\n\n버스 소스는 조회를 마친 뒤 현재 시각을 다시 읽고 evaluated_at으로 보존합니다. confirmed_at은 원 응답 시각을 유지하고 공급 mkTm·캐시 경과와 구분합니다. 응답 대기 뒤 출발 분을 올림하고 기존 접근 시간을 온전히 더한 ready_at으로 차량을 선택합니다. 출발 관측은 evaluated_at을 기준으로 출발·접근·운행일·마감·예상 소요를 다시 계산하며 신규 응답을 시작 시각보다 늦다는 이유로 거절하지 않습니다. 완료 시각 역전/시간대 누락·확인시각이 완료시각 이후·접근 전 차량은 거절합니다. 값 없는 소스의 대체 모델도 알려진 조회 대기 뒤 계산하고 마감 초과는 안내 보류로 돌립니다. evaluated_at 없는 기존 시험용 콜백은 전달 now 계약을 유지합니다. 실제 탑승/위치 관측·미래 환승 차량 예측을 완료한 것은 아닙니다.\n')
state = {'tag': tag, 'created_at': now.isoformat(), 'backups': backups, 'debug': debug,
         'prior_source_hashes': 210, 'prior_artifacts': 6}
with (ev / 'start-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
with (Path(__file__).parent / 'arrival-clock-work-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False)
print(tag)
