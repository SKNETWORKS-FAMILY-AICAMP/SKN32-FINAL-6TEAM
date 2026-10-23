"""사후 결제값을 예측 입력에 넣지 않고 현재 모델을 개인 보관소에서 재생한다."""
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-baseline',required=True)
    parser.add_argument('--private-output',required=True)
    parser.add_argument('--public-summary',required=True)
    args=parser.parse_args()
    source,output=private_path(args.private_baseline),private_path(args.private_output)
    summary_path=Path(args.public_summary).resolve()
    if not summary_path.is_relative_to(WORKSPACE):
        raise ValueError('익명 집계는 작업 폴더의 새 파일이어야 합니다')
    if output.exists() or summary_path.exists():
        raise ValueError('기존 진단 결과를 덮어쓰지 않습니다')
    def no_network(*_args,**_kwargs):
        raise RuntimeError('개인 자료 진단은 외부 통신을 하지 않습니다')
    socket.socket.connect=no_network
    socket.socket.connect_ex=no_network
    socket.create_connection=no_network
    from app.domains.travel_ops.instances.mobility.engine import paths
    from app.domains.travel_ops.instances.mobility.engine.car import CarGraph,CarService
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    paths.configure(WORKSPACE/'datasets/mobility/processed',source='private_diagnosis_offline')
    engine=PROJECT/'app/domains/travel_ops/instances/mobility/engine'
    rulefile=engine/'rules/rules_v0.3.json'
    rules=json.loads(rulefile.read_text(encoding='utf8'))
    holidays=json.loads((engine/'rules/holidays_2026_2027.json').read_text(encoding='utf8'))['holidays']
    files=list(engine.glob('*.py'))+list((engine/'rules').glob('*.json'))
    for folder in ('graph','road_graph_v2'):
        files += [p for p in (paths.PROCESSED/'mobility'/folder).glob('*') if p.is_file()]
    def snapshot():
        return {str(p.relative_to(WORKSPACE)):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in files}
    before_hash=snapshot()
    baseline=json.loads(source.read_text(encoding='utf8'))['rows']
    if len({r['id'] for r in baseline}) != len(baseline):
        raise ValueError('중복 영수증')
    service=CarService(CarGraph.load(holidays=holidays),GraphRouter.default(),rules)
    rows=[]
    for row in baseline:
        receipt=row['receipt']
        depart=datetime.fromisoformat(receipt['date']+'T'+receipt['start']+':00+09:00')
        # 예측은 출발 좌표·도착 좌표·출발 시각만 사용한다. 실제시간·결제·옵션료 미주입.
        prediction=service.leg(tuple(row['start_lonlat']),tuple(row['end_lonlat']),depart,taxi=True)
        rows.append({'id':row['id'],'receipt':receipt,'endpoint_quality':row['endpoint_quality'],
            'before':row['prediction'],'after':prediction,
            'error_before_won':row['prediction']['meter_won']-receipt['meter'],
            'error_after_won':prediction['meter_won']-receipt['meter'],
            'time_error_after_s':prediction['topis_time_s']-receipt['minutes']*60})
    after_hash=snapshot()
    if before_hash!=after_hash:
        raise RuntimeError('진단 도중 코드 또는 자료 변경')
    def stats(key):
        predictions=[r[key]['meter_won'] for r in rows]
        actual=[r['receipt']['meter'] for r in rows]
        return {'n':len(rows),'mae_won':statistics.mean(abs(a-p) for a,p in zip(actual,predictions)),
            'mape_percent':statistics.mean(abs(p/a-1)*100 for a,p in zip(actual,predictions)),
            'underestimates':sum(p<a for a,p in zip(actual,predictions)),
            'within_1000_won':sum(abs(p-a)<=1000 for a,p in zip(actual,predictions))}
    summary={'checked_at':datetime.now().astimezone().isoformat(),'before':stats('before'),'after':stats('after'),
        'actual_time_or_fare_used_as_prediction_input':False,'observed_option_fee_used':False,
        'reserve_rate_changed':False,'developer_api_calls':0,'network_blocked':True,
        'code_data_changed_during_run':False,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'scope':'제공 서울4건의 개발 진단 재생; 실제GPS 미확보·출발점 근사 포함; 새 독립 검증 아님'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'summary':summary,'rows':rows,'source_and_data_sha256':before_hash},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    summary_path.parent.mkdir(parents=True,exist_ok=True)
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
