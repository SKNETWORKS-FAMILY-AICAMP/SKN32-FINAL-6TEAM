"""개인 결제 대조에서 사후 옵션료를 예측에 쓰지 않는 사전 상품 재생."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import socket
import statistics

from .evaluate_taxi_receipts_v1 import private_path

PROJECT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-baseline', required=True)
    parser.add_argument('--private-products', required=True)
    parser.add_argument('--private-output', required=True)
    parser.add_argument('--public-summary', required=True)
    args = parser.parse_args()
    source, products, output = map(private_path, (args.private_baseline, args.private_products, args.private_output))
    summary_path = Path(args.public_summary).resolve()
    if not summary_path.is_relative_to(WORKSPACE) or output.exists() or summary_path.exists():
        raise ValueError('새 개인 출력과 작업 폴더의 새 익명 집계 경로가 필요합니다')
    def blocked(*_args, **_kwargs):
        raise RuntimeError('개인 자료 진단은 외부 통신을 하지 않습니다')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
    from app.domains.travel_ops.instances.mobility.engine import paths
    from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, CarService
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    from app.domains.travel_ops.instances.mobility.engine.errors import CaseInputError
    from app.domains.travel_ops.instances.mobility.engine.taxi_call_policy import resolve_call_fee
    from app.domains.travel_ops.instances.mobility.engine.taxi_pricing import with_call_product
    paths.configure(WORKSPACE/'datasets/mobility/processed', source='private_pretrip_offline')
    engine = PROJECT/'app/domains/travel_ops/instances/mobility/engine'
    rules = json.loads((engine/'rules/rules_v0.3.json').read_text(encoding='utf8'))
    holidays = json.loads((engine/'rules/holidays_2026_2027.json').read_text(encoding='utf8'))['holidays']
    files = list(engine.glob('*.py')) + list((engine/'rules').glob('*.json'))
    for folder in ('graph', 'road_graph_v2'):
        files += [p for p in (paths.PROCESSED/'mobility'/folder).glob('*') if p.is_file()]
    def snapshot():
        return {str(p.relative_to(WORKSPACE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = snapshot()
    service = CarService(CarGraph.load(holidays=holidays), GraphRouter.default(), rules)
    choices = json.loads(products.read_text(encoding='utf8'))
    baseline = json.loads(source.read_text(encoding='utf8'))['rows']
    if set(choices['products']) != {r['id'] for r in baseline}:
        raise ValueError('모든 표본에 사전 선택 상품 식별이 필요합니다')
    rows = []
    for r in baseline:
        # 선택 상품에는 실제 옵션료·최종 결제액을 받지 않습니다.
        product = choices['products'][r['id']]
        if not isinstance(product, str):
            raise ValueError('상품은 문자열 식별자만 받습니다')
        receipt = r['receipt']
        depart = datetime.fromisoformat(receipt['date']+'T'+receipt['start']+':00+09:00')
        pricing_error = None
        try:
            resolve_call_fee(product, depart)
        except CaseInputError as exc:
            pricing_error = str(exc)
        predicted = service.leg(tuple(r['start_lonlat']), tuple(r['end_lonlat']), depart, taxi=True)
        priced = None if pricing_error else with_call_product(predicted, product, depart)
        # 실제값은 예측 완료 후 오차 계산에서만 읽습니다.
        rows.append({'id': r['id'], 'prediction': predicted, 'pretrip_prediction': priced,
                     'product': product, 'pricing_error': pricing_error,
                     'actual_meter_won': receipt['meter'], 'actual_total_won': receipt['total'],
                     'historical_brand_policy_confirmed': choices['historical_brand_policy_confirmed'].get(r['id'], False),
                     'endpoint_quality': r['endpoint_quality']})
    if snapshot() != before:
        raise RuntimeError('진단 도중 코드 또는 자료 변경')
    supported = [r for r in rows if r['pretrip_prediction'] is not None]
    errors = [r['prediction']['meter_won'] - r['actual_meter_won'] for r in rows]
    summary = {'checked_at': datetime.now().astimezone().isoformat(),
        'n': len(rows), 'pretrip_product_supported': len(supported),
        'missing_pretrip_quote': len(rows)-len(supported),
        'supported_retrospective_budget_covers_total': sum(r['pretrip_prediction']['fare_won'] >= r['actual_total_won'] for r in supported),
        'historical_brand_policy_confirmed_n': sum(r['historical_brand_policy_confirmed'] for r in rows),
        'meter_mae_won': statistics.mean(map(abs, errors)), 'meter_underestimates': sum(e < 0 for e in errors),
        'meter_within_1000_won': sum(abs(e) <= 1000 for e in errors),
        'actual_meter_time_or_option_fee_used_as_prediction_input': False,
        'actual_option_fee_injected': False, 'private_receipts_used_for_fit': False,
        'reserve_rate_changed': False, 'developer_api_calls': 0, 'network_blocked': True,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'products_sha256': hashlib.sha256(products.read_bytes()).hexdigest(),
        'scope': '현재'+' 공식 상품 정책의 서울4건 후향 재생. 과거 약관·실제 GPS·사전 견적이 없는 부분은 별도 미확인. 새 독립 검증 아님'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'summary': summary, 'rows': rows, 'code_data_sha256': before}, ensure_ascii=False, indent=2), encoding='utf8')
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
