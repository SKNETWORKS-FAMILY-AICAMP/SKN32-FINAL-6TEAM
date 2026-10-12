"""동결된 웹 대조군으로 버스 탐색·지하철 요금 안내 변경을 재검산한다."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from scripts.mobility.summarise_fresh_web_experiment import paired

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / 'datasets/mobility/raw/kakao_golden'
DEV = RAW / 'development_2026-10-08_v1'
ASSETS = ROOT / 'wiki/records/reports/assets/2026-10-08_mobility_development_v3'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def modal(rows, refs, index, mode):
    selected = {}
    for row in rows:
        obj = row['transit']
        traces = {o['id']: o for o in obj.get('comparison', {}).get('options', [])}
        opts = [o for o in obj.get('route', {}).get('options', [])
                if {leg.get('mode', 'subway') for leg in traces[o['id']]['check']['legs']} == {mode}]
        if not opts or refs[row['id']][3][index] is None:
            continue
        opt = min(opts, key=lambda o: o['eta_min'])
        trace = next(o for o in obj['comparison']['options'] if o['id'] == opt['id'])
        if trace.get('wait_min') is None:
            continue
        selected[row['id']] = {**opt, **trace}
    time = paired([o['eta_min'] - o['wait_min'] for o in selected.values()],
                  [refs[i][3][index][0] for i in selected]) if selected else None
    known = {i: o for i, o in selected.items() if o.get('fare_krw') is not None}
    upper = {i: o for i, o in known.items() if '상단 예상액' in o['label'] or '할인 전 상한' in o['label']}
    exact_or_est = {i: o for i, o in known.items() if i not in upper}
    result = {'reference_available': sum(r[3][index] is not None for r in refs.values()),
              'comparable': len(selected), 'fare_present': len(known), 'fare_upper': len(upper),
              'fare_exact_or_single_estimate': len(exact_or_est), 'time_without_wait': time,
              'fare_in_web_range': sum(refs[i][3][index][3] <= o['fare_krw'] <= refs[i][3][index][4]
                                      for i, o in known.items()),
              'fare_upper_covers_web_max': sum(o['fare_krw'] >= refs[i][3][index][4] for i, o in upper.items()),
              'failures': dict(Counter(r['transit']['failure']['code'] for r in rows if 'failure' in r['transit']))}
    return result, selected


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    refs = {r[0]: r for r in load(RAW / 'fresh_web_100_v1.json')}
    paths = [RAW/'fresh_ours_bus_100_v1.json', DEV/'bus_after_v1.json',
             RAW/'fresh_ours_transit_100_v1.json', DEV/'subway_after_v3.json']
    result = {'created_at': datetime.now().astimezone().isoformat(),
              'purpose': '개발용 기존 100쌍 재사용. 수정 후 독립 검증이 아니다.',
              'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              'timing_note': '여러 실험·시험 동시 실행. 처리 시간의 전후 우열을 판정하지 않는다.',
              'mode_definition': 'id 접두가 아니라 실제 구간열의 모든 탑승 수단이 일치하는 후보'}
    selections = []
    for name, path, index, mode in zip(('bus_before','bus_after','rail_before','rail_after'), paths,
                                       (2,2,3,3), ('bus','bus','subway','subway'), strict=True):
        result[name], opts = modal(load(path)['rows'], refs, index, mode)
        selections.append(opts)
    before, after = selections[:2]
    result['bus_change'] = {'recovered': sorted(after.keys()-before.keys()),
                            'lost': sorted(before.keys()-after.keys()),
                            'retained': len(before.keys() & after.keys())}
    before, after = selections[2:]
    same = [i for i in before.keys() & after.keys()
            if before[i]['check']['legs'] == after[i]['check']['legs']]
    result['rail_same_route'] = {'n': len(same),
        'before_present': sum(before[i].get('fare_krw') is not None for i in same),
        'after_present': sum(after[i].get('fare_krw') is not None for i in same),
        'new_upper': sum(before[i].get('fare_krw') is None and after[i].get('fare_krw') is not None for i in same)}
    with (ASSETS/'development-summary.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
