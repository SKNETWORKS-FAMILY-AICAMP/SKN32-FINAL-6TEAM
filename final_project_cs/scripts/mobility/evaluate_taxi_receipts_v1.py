"""개인 보관소의 영수증 추출본을 현재 모델로 재평가한다. 네트워크·보정 없음.

개별 위치·영수증·예측은 프로젝트 밖 입력/출력에만 보관한다.
공유 요약에는 식별자·장소·날짜·좌표·개별 금액을 쓰지 않는다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import socket
import statistics

PROJECT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT.parent


def private_path(value):
    path = Path(value).resolve()
    if path.is_relative_to(WORKSPACE):
        raise ValueError('개별 영수증 자료는 팀 작업 폴더 밖 개인 보관소를 사용합니다')
    return path


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-input', required=True)
    parser.add_argument('--private-output', required=True)
    parser.add_argument('--public-summary', required=True)
    args = parser.parse_args()
    source, output = private_path(args.private_input), private_path(args.private_output)
    public = Path(args.public_summary).resolve()
    if not public.is_relative_to(WORKSPACE):
        raise ValueError('공유 요약은 작업 폴더의 새 파일로 보존합니다')
    if output.exists() or public.exists():
        raise ValueError('기존 평가를 덮어쓰지 않습니다. 새 출력 이름을 사용하세요')
    data = json.loads(source.read_text(encoding='utf8'))
    rows = data['results']
    identifiers = [row['receipt']['id'] for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('중복 영수증을 평가에 합산할 수 없습니다')
    def no_network(*args, **kwargs):
        raise RuntimeError('개인 영수증 평가는 네트워크를 사용하지 않습니다')
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    from app.domains.travel_ops.instances.mobility.engine import paths
    paths.configure(WORKSPACE/'datasets/mobility/processed', source='private_receipt_offline')
    from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, CarService
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    from app.domains.travel_ops.instances.mobility.engine.taxi_budget import with_option_fee
    engine = PROJECT/'app/domains/travel_ops/instances/mobility/engine'
    rules = json.loads((engine/'rules/rules_v0.3.json').read_text(encoding='utf8'))
    holidays = json.loads((engine/'rules/holidays_2026_2027.json').read_text(encoding='utf8'))['holidays']
    files = list(engine.glob('*.py'))+list((engine/'rules').glob('*.json'))
    for folder in ('graph','road_graph_v2'):
        files += [p for p in (paths.PROCESSED/'mobility'/folder).glob('*') if p.is_file()]
    before = {str(p.relative_to(WORKSPACE)):sha(p) for p in files}
    service = CarService(CarGraph.load(holidays=holidays), GraphRouter.default(), rules)
    evaluated, excluded = [], []
    for row in rows:
        receipt = row['receipt']
        if receipt['city'] != '서울':
            excluded.append({'id':receipt['id'],'reason':'unsupported_city'})
            continue
        for key in ('meter','total'):
            if type(receipt[key]) is not int or receipt[key] <= 0:
                raise ValueError('영수증 미터·총액이 잘못됐습니다')
        # 사진에서 확인한 총결제와 미터의 차액이다. 사전 옵션료 예측이 아니다.
        fee = receipt['total']-receipt['meter']
        if fee < 0 or (receipt.get('extra') is not None and fee != receipt['extra']):
            raise ValueError('별도 이용료와 실제 총액이 일치하지 않습니다')
        depart = datetime.fromisoformat(receipt['date']+'T'+receipt['start']+':00+09:00')
        prediction = service.leg(tuple(row['start_lonlat']),tuple(row['end_lonlat']),depart,taxi=True,kind='중형')
        after = with_option_fee(prediction, {'fee_won':fee})
        evaluated.append({'id':receipt['id'],'receipt':receipt,
            'start_lonlat':row['start_lonlat'],'end_lonlat':row['end_lonlat'],
            'endpoint_quality':row.get('endpoint_quality'), 'prediction':prediction,
            'budget_with_observed_fee':after,
            'meter_error_won':prediction['meter_won']-receipt['meter'],
            'meter_absolute_percentage_error':abs(prediction['meter_won']/receipt['meter']-1)*100,
            'budget_covers_meter':prediction['fare_won'] >= receipt['meter'],
            'previous_budget_covers_total':prediction['fare_won'] >= receipt['total'],
            'budget_with_observed_fee_covers_total':after['fare_won'] >= receipt['total']})
    after_hashes = {str(p.relative_to(WORKSPACE)):sha(p) for p in files}
    if before != after_hashes:
        raise RuntimeError('평가 중 코드·자료가 바뀌었습니다')
    n = len(evaluated)
    if not n:
        raise ValueError('지원 범위의 실제 결제 자료가 필요합니다')
    summary = {'checked_at':datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'unique_receipts':len(rows),'compared_seoul_receipts':n,'excluded_unsupported_city':len(excluded),
        'comparison_work_complete':n==len(rows)-len(excluded),
        'meter_mae_won':statistics.mean(abs(r['meter_error_won']) for r in evaluated),
        'meter_mape_percent':statistics.mean(r['meter_absolute_percentage_error'] for r in evaluated),
        'meter_underestimated':sum(r['meter_error_won']<0 for r in evaluated),
        'descriptive_meter_within_1000_won':sum(abs(r['meter_error_won'])<=1000 for r in evaluated),
        'budget_covers_meter':sum(r['budget_covers_meter'] for r in evaluated),
        'previous_budget_covers_total':sum(r['previous_budget_covers_total'] for r in evaluated),
        'budget_with_observed_fee_covers_total':sum(r['budget_with_observed_fee_covers_total'] for r in evaluated),
        'option_fee_basis':'実額'.replace('実額','영수증에서 확인한 실제 차액; 사전 예측 아님'),
        'reserve_rate_changed':False,'model_unchanged_during_evaluation':True,
        'developer_api_calls':0,'network_connect_blocked':True,'source_file_sha256':sha(source),
        'scope':'제공 서울 중형 표본의 사후 재생·결제 대조 완료. 도시 전체 정확도·사전 옵션료 예측·새 독립 표본 통과 아님',
        'quality_gate_passed':None}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'summary':summary,'rows':evaluated,'excluded':excluded,
                                 'source_and_data_sha256':before},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    public.parent.mkdir(parents=True,exist_ok=True)
    public.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
