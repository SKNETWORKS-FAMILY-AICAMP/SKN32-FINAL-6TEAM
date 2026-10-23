from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
now = datetime.now().astimezone()
stamp = now.strftime('%Y-%m-%d_%H%M')
tag = stamp + '_混合요금_조조경계'.replace('混合', '혼합')
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
state = {'tag': tag, 'created_at': now.isoformat(), 'backups': [],
         'initial_source_matches': 218, 'initial_artifact_matches': 6}
for rel in ['app/domains/travel_ops/instances/mobility/engine/options.py',
            'app/domains/travel_ops/instances/mobility/engine/plan.py', 'wiki/teams/mobility.md']:
    p = cs / rel
    b = p.parent / '_backup' / tag / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    state['backups'].append({'source': p.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(),
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
debug = cs / 'wiki/records/reports/debugs' / (tag + '_버스조조_불확실성으로_혼합상단요금까지_누락.md')
state['debug'] = debug.relative_to(cs).as_posix()
with debug.open('x', encoding='utf8') as f:
    f.write('''# 버스 조조 할인 불확실성으로 혼합 경로의 예상액 상단까지 누락

## 미해결

위치: app/domains/travel_ops/instances/mobility/engine/options.py의 bus_fare·fare_upper_of, plan.py의 공개 fare_krw 처리. bus_fare는 배차로 계산한 승차 창이06:30을 가로지르면 정확 금액을 내지 않는다. 이 결과를 개별 요금 합의 상단에도 그대로 쓰므로 알려진 단일 기본요금이 있어도 혼합 경로의 예상액 상단을 뺀다. 각 묶음을 첫 승차처럼 조조 할인하는 계산도 할인 미적용 상단 목적과 다르다.

위험도: 예산 비교에 쓸 알려진 금액이 빠지거나 할인 적용 금액이 상단으로 표시될 수 있다. 실제 카드 결제 오차는 미측정이다. 공식 요금은 서울시 물가정보 버스·교통 요금 안내에서 확인하고 규칙 파일 값을 재사용한다. 공항·투어·미등록 노선·누락 지하철 거리는 기본값으로 채우지 않는다. 재현 명령과 실행 출력은 같은 태그 evidence에 보존한다. 기존 웹 집계 수치는 아직 다시 측정하지 않았다.
''')
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {stamp} 혼합 경로 할인 미적용 예상액 상단 계약

fare_upper_of는 버스가 포함된 여러 승차의 개별 일반 요금 합을 예상액 상단으로 전달한다. 버스는 알려진 유형의 규칙 기본요금을 사용하며 조조 승차 창이 불확실해도 기본요금 상단을 잃지 않는다. 지하철 묶음은 기존 승인된 거리 범위·별도 운임 검사를 유지하고 조조 할인을 적용하지 않는 subway_fare_upper를 사용한다. 지하철 단독 상단의 기존 조조 동작과 fare_of의 정확액 판정은 유지한다. 공개 혼합 상단 문구에는 조조 할인 미적용을 명시한다. 공항·투어·미등록 유형·누락 거리·승차 결과 불일치는 채우지 않는다. 할인 후 실제 운임·카드 태그·개인별 요금은 별도 관문이다.
''')
for p in [scratch / 'fare-discount-upper-work-v1.json', ev / 'start-v1.json']:
    with p.open('x', encoding='utf8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
print(tag)
