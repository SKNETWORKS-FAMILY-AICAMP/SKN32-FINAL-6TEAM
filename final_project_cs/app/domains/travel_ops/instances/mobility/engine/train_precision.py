"""공식 열차별 시각을 정확한 기존 승차편에 연결한다. 새로운 승차편은 만들지 않는다."""
from __future__ import annotations

from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

FILE = 'published_train_precision_v1.json.gz'


def seconds(value):
    try:
        h, m, s = map(int, value.split(':'))
    except (AttributeError, ValueError):
        return None
    if not 0 <= h <= 30 or not 0 <= m < 60 or not 0 <= s < 60:
        return None
    n = h * 3600 + m * 60 + s
    return n if 0 < n <= 30 * 3600 else None


class Departure:
    def __init__(self, run, index, source):
        self.run, self.index, self.source = run, index, source
        self.departure_sec = run['stops'][index][2]

    def arrival_sec(self, path, target):
        """정차 순서가 선택 경로와 같을 때만 그 열차의 도착초를 반환한다."""
        if not path or target not in path:
            return None
        segment = path[:path.index(target) + 1]
        stops = self.run['stops'][self.index:self.index + len(segment)]
        if [s[0] for s in stops] != segment or len(stops) != len(segment):
            return None
        arrival = stops[-1][1]
        return arrival if arrival is not None and arrival >= self.departure_sec else None


class TrainPrecision:
    def __init__(self, doc):
        if doc.get('schema_version') != 1:
            raise ValueError('공식 열차 시각 보조표 스키마가 잘못됐습니다')
        self.doc = doc
        self.by_key = defaultdict(list)
        self.matched = 0
        for run in doc['runs']:
            stops = run['stops']
            if run['line'] not in ('02호선', '03호선') or run['day_type'] not in ('weekday','saturday','holiday') or run['dir'] not in ('U','D'):
                raise ValueError('공식 열차 시각 보조표의 노선/요일/방향이 잘못됐습니다')
            for i, (station, arrival, departure) in enumerate(stops):
                if any(type(x) is not int or not 0 < x <= 30*3600 for x in (arrival,departure) if x is not None):
                    raise ValueError('공식 열차 시각 보조표의 초 값이 잘못됐습니다')
                if arrival is not None and departure is not None and arrival > departure:
                    raise ValueError('공식 열차 시각 보조표의 정차 시각이 역전됐습니다')
                if i:
                    prev=stops[i-1]
                    if (prev[2] if prev[2] is not None else prev[1]) > (arrival if arrival is not None else departure):
                        raise ValueError('공식 열차 시각 보조표의 정차 순서가 역전됐습니다')
                if departure is not None:
                    key=run['line'],station,run['day_type'],run['dir'],departure
                    self.by_key[key].append(Departure(run,i,doc))

    def match(self, row):
        # 채운 행선지나 같은 분의 다른 편을 정확한 열차라고 단정하지 않는다.
        if row.get('dest_inferred'):
            return None
        key=row.get('line'),row.get('station_nm'),row.get('day_type'),row.get('dir'),seconds(row.get('dep_time'))
        matches=self.by_key.get(key, [])
        if len(matches) != 1:
            return None
        if row.get('dest_nm') != matches[0].run['stops'][-1][0]:
            return None
        self.matched += 1
        return matches[0]


def load_for_timetable(path, companion_path=None):
    path=Path(path)
    companion=Path(companion_path) if companion_path is not None else path.with_name(FILE)
    if not companion.exists():
        return None
    raw=companion.read_bytes()
    doc=json.loads(gzip.decompress(raw).decode('utf-8'))
    if doc.get('timetable_sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError('공식 열차 시각 보조표의 기준 시간표 판이 바뀌었습니다')
    result=TrainPrecision(doc)
    if hashlib.sha256(companion.read_bytes()).digest() != hashlib.sha256(raw).digest():
        raise RuntimeError('공식 열차 시각 보조표를 읽는 사이 입력 판이 바뀌었습니다')
    return result
