from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

sys.stdout.reconfigure(encoding='utf8')
root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
tag = '2026-10-11_0421_혼합환승_제품운임_연결'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(parents=True, exist_ok=False)
relpaths = ['app/domains/travel_ops/instances/mobility/engine/options.py',
            'app/domains/travel_ops/instances/mobility/engine/plan.py',
            'app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json',
            'wiki/teams/mobility.md',
            'tests/unit/travel/mobility/test_mixed_fare_upper_v1.py']
backups = []
for rel in relpaths:
    p = cs / rel
    target = p.parent / '_backup' / tag / p.name
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    shutil.copy2(p, target)
    backups.append({'source': p.relative_to(root).as_posix(),
                    'backup': target.relative_to(root).as_posix(),
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    if rel.startswith('app/'):
        legacy = cs / 'legacy' / tag / rel
        legacy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, legacy)
prior = cs / 'wiki/records/evidence/2026-10-11_0317_미발행출발_지연복구/final-integrity-v1.json'
data = json.loads(prior.read_text(encoding='utf8'))
matches = 0
diffs = []
for rel, digest in data['source_test_data_hashes'].items():
    p = root / rel
    if not p.exists():
        p = cs / rel
    current = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if current == digest:
        matches += 1
    else:
        diffs.append({'path': rel, 'before': digest, 'current': current})
state = {'tag': tag, 'created_at': datetime.now().astimezone().isoformat(),
         'backups': backups, 'prior_matches': matches, 'prior_total': len(data['source_test_data_hashes']),
         'prior_changes': diffs, 'limited_api_calls': 0,
         'provider_daily_used': None, 'provider_daily_remaining': None, 'provider_reset_at': None,
         'quota_action': '공유 사용량을 확인하지 못해 제한 API를 호출하지 않음'}
(ev / 'baseline-v1.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
(Path(__file__).parent / 'transfer-product-work-v1.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
debug = cs / 'wiki/records/reports/debugs' / (tag + '.md')
debug.write_text('''# 혼합 환승 할인 예상액의 제품 안내 미연결

## 미해결

발견 시점: 2026-10-11. 실제 제품은 options.fare_of에서 버스 혼합 경로를 모두 None으로 반환하고, plan.Planner.leg에서 개별 요금 합만 안내한다. transfer_fare는 제품 호출이 없고 시험에서만 실행된다.

원인: 버스 거리 자료를 일괄 금지하던 옛 규칙이 남아 있다. 현재 구간 거리 자료가 완전하다고 해서 교통카드 청구 운임거리와 같다고 확정할 수는 없으므로, 거리 모델에 따른 할인 예상액과 결제 확정액을 구분하여 연결해야 한다.

위험: 할인 전 합계가 예상 교통비로 쓰여 혼합 경로의 비교와 재계획 판단이 불리해진다. 동일 노선 재승차·환승시간 초과·자료 누락을 무시한 할인도 금지해야 한다.

재현: 새 test_transfer_fare_product_v1.py를 수정 전 실행하고 로그를 동일 이름 evidence 폴더에 보존한다. 기존 웹 개발 표본의 구간열을 동결하여 전후 비교한다. 새 독립 표본·실제 결제 측정은 아니다.
''', encoding='utf8')
p = cs / 'wiki/teams/mobility.md'
assert hashlib.sha256(p.read_bytes()).hexdigest() == backups[3]['sha256']
text = p.read_text(encoding='utf8')
contract = '''## 2026-10-11 혼합 환승 할인 예상액의 제품 연결 계약

버스가 포함된 환승 경로는 일반 성인 교통카드를 1인 1장 사용하고 승·하차 태그를 한다는 조건으로 할인 예상액을 먼저 안내한다. 계산은 선택된 버스 노선 ID·승하차 순번·정류소 ID의 연속 구간 거리와 기존 지하철 거리 범위 상단을 합산한다. 버스 구간거리는 청구 운임거리로 확정하지 않고 모델 추정으로 취급한다. label에 「성인 1인 1카드·승하차 태그 시 환승 할인 예상액 · 거리 모델·조조 미적용」을 붙인다. 새 공개 필드는 추가하지 않는다.

버스 순번/노선 식별값 불일치·중간 거리 누락·같은 버스 노선 재승차·후속 승차 기준 환승시간 초과·5회 초과 승차·적용 유형 밖·별도 철도운임 미확인은 할인 예상액을 내지 않고 기존 할인 전 예상액 상단 계산으로 돌아간다. 지하철 개찰 안 연속 환승은 한 승차로 묶는다. 최대 이용시간은 지하철/시내버스 5시간·마을버스 1시간이며 초과 후보에는 통합 할인을 적용하지 않는다. 선로 추정/공표 거리 우선순위와 알려지지 않은 거리의 임의 채움 금지는 유지한다.

환승 창은 선택된 경로의 승하차 모델 시각에 적용한다. 실제 카드 태그·실제 탑승·실제 결제액을 측정했다고 표시하지 않는다. 조조 할인은 최초 수단만의 별도 조건을 아직 결합하지 않았으므로 적용하지 않는다. 확인한 공식 근거: [서울시 통합환승 할인제](https://news.seoul.go.kr/traffic/transfer_discount), [서울시 노선정보 응답 항목](https://www.data.go.kr/data/15000193/openapi.do), 2026-10-11 조회.

'''
at = text.find('\n## ')
p.write_text(text[:at + 1] + contract + text[at + 1:], encoding='utf8')
print(json.dumps({'tag': tag, 'backups': len(backups), 'matches': matches, 'total': state['prior_total'], 'changes': [d['path'] for d in diffs]}, ensure_ascii=False))
