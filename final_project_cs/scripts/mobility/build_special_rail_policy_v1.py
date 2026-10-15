"""신분당선 공식 구간 요금과 양쪽 표기가 일치한 역간 거리만 등록한다.

원자료: datasets/mobility/raw/official_distance_20261008/15041074.csv
이미 존재하는 출력은 덮어쓰지 않는다. 경로별 정답을 수록하지 않는다.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT.parent/'datasets/mobility/raw/official_distance_20261008/15041074.csv'
OUTPUT = ROOT/'app/domains/travel_ops/instances/mobility/engine/rules/special_rail_fares_v1.json'


def main():
    rows = list(csv.DictReader(SOURCE.read_text(encoding='cp949').splitlines()))
    names = [r['역명'].split('(')[0] for r in rows]
    distances, conflicts = [], []
    for a, b in zip(rows, rows[1:]):
        left, right = round(float(a['후행역간거리'])*1000), round(float(b['역간거리'])*1000)
        edge = {'a': a['역명'].split('(')[0], 'b': b['역명'].split('(')[0]}
        if left == right and left > 0:
            distances.append(dict(edge, distance_m=left))
        else:
            conflicts.append(dict(edge, forward_m=left, reverse_m=right))
    policy = {'version': '1', 'effective_from': '2025-06-28', 'checked_at': '2026-10-08',
        'sources': ['https://www.shinbundang.co.kr/dxline/dxline4_1.jsp',
                    'https://www.data.go.kr/data/15041074/fileData.do'],
        'distance_input_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'scope': '성인 교통카드. 기본·거리 운임은 기존 수도권 규칙; 추가운임은 이용 구간마다 한 번.',
        'lines': {'신분당선': {'stations': names,
            'zones': [{'id': 'north', 'from': '신사', 'to': '강남'},
                      {'id': 'middle', 'from': '강남', 'to': '정자'},
                      {'id': 'south', 'from': '정자', 'to': '광교'}],
            'surcharges': {'north': 700, 'middle': 1000, 'south': 1000,
                'middle+south': 1500, 'middle+north': 1700, 'middle+north+south': 2200},
            'confirmed_edges': distances, 'excluded_conflicting_edges': conflicts}}}
    with OUTPUT.open('x', encoding='utf8') as stream:
        json.dump(policy, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'stations': len(names), 'confirmed_edges':len(distances), 'conflicts':conflicts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
