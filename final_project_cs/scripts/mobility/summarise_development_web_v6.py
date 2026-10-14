"""동결된 100쌍에서 버스 탐색·지하철 거리 보강을 재대조한다."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from scripts.mobility.summarise_development_web import modal
from scripts.mobility.summarise_fresh_web_experiment import paired

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / 'datasets/mobility/raw/kakao_golden'
DEV = RAW / 'development_2026-10-08_v1'
ASSETS = ROOT / 'wiki/records/reports/assets/2026-10-08_mobility_development_v6'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    refs = {r[0]: r for r in load(RAW / 'fresh_web_100_v1.json')}
    paths = [RAW/'fresh_ours_bus_100_v1.json', DEV/'bus_after_v9.json',
             RAW/'fresh_ours_transit_100_v1.json', DEV/'subway_after_v5.json']
    data = ROOT.parent / 'datasets/mobility/processed/mobility'
    inputs = [RAW/'fresh_web_100_v1.json', *paths,
              data/'rail_edge_track_v2.jsonl.gz', data/'rail_distance_overlay_v1.json',
              ROOT/'app/domains/travel_ops/instances/mobility/engine/rules/special_rail_fares_v1.json']
    result = {
        'created_at': datetime.now().astimezone().isoformat(),
        'purpose': '개발용 기존 100쌍 재사용. 독립 검증·실제 승차 측정이 아니다.',
        'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'timing_note': '동시 실행 조건이 달라 처리 속도 우열을 판정하지 않는다.',
        'mode_definition': '실제 구간열 전체의 탑승 수단이 일치하는 후보',
        'distance_grade': '공표값·대응방향 추정은 확정 거리와 분리해 기존 오차 범위를 적용한다.',
    }
    selections = []
    for name, path, index, mode in zip(
        ('bus_before', 'bus_after', 'rail_before', 'rail_after'), paths,
        (2, 2, 3, 3), ('bus', 'bus', 'subway', 'subway'), strict=True
    ):
        result[name], opts = modal(load(path)['rows'], refs, index, mode)
        selections.append(opts)
    for label, before, after, index in (
        ('bus', *selections[:2], 2), ('rail', *selections[2:], 3)
    ):
        common = sorted(before.keys() & after.keys())
        same = [i for i in common if before[i]['check']['legs'] == after[i]['check']['legs']]
        result[label + '_change'] = {
            'recovered': sorted(after.keys() - before.keys()),
            'lost': sorted(before.keys() - after.keys()),
            'retained': len(common),
            'paired_common_before': paired(
                [before[i]['eta_min'] - before[i]['wait_min'] for i in common],
                [refs[i][3][index][0] for i in common]),
            'paired_common_after': paired(
                [after[i]['eta_min'] - after[i]['wait_min'] for i in common],
                [refs[i][3][index][0] for i in common]),
            'same_route': {
                'n': len(same),
                'before_present': sum(before[i].get('fare_krw') is not None for i in same),
                'after_present': sum(after[i].get('fare_krw') is not None for i in same),
            },
        }
    ASSETS.mkdir(parents=True, exist_ok=True)
    with (ASSETS/'development-summary.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
