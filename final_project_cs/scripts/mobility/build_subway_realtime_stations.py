"""서울시 공개 역정보 원문을 식별정보로 추출한다. 시간표 역코드에서 ID를 만들지 않는다."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

HEADER = ('SUBWAY_ID', 'STATN_ID', 'STATN_NM', '호선이름')
SOURCE_URL = 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do'


def canonical_line(value):
    """숫자 호선의 선행0만 통일한다. 다른 노선은 합치지 않는다."""
    if not isinstance(value, str) or not value:
        raise ValueError('line must be a nonempty string')
    match = re.fullmatch(r'0?([1-9])호선', value)
    return f'{match[1]}호선' if match else value


def _identifier(value):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and value.isascii() and value.isdigit() and int(value) > 0:
        return value
    raise ValueError('official identifier must be a positive integer or ASCII digit string')


def build_snapshot(rows, *, source_sha256, basis_date):
    if not rows or tuple(rows[0]) != HEADER:
        raise ValueError('unexpected official worksheet header')
    stations, ids, keys, line_names, line_ids = [], set(), set(), {}, {}
    for source_row, row in enumerate(rows[1:], start=2):
        if len(row) != len(HEADER):
            raise ValueError(f'column count mismatch at source row {source_row}')
        line_id, station_id, station, line = row
        line_id, station_id = _identifier(line_id), _identifier(station_id)
        if not isinstance(station, str) or not station.strip() or not isinstance(line, str) or not line.strip():
            raise ValueError(f'missing name at source row {source_row}')
        line = canonical_line(line)
        key = (line, station)
        if station_id in ids or key in keys:
            raise ValueError(f'duplicate ID or line/station at source row {source_row}')
        if ((line_id in line_names and line_names[line_id] != line)
                or (line in line_ids and line_ids[line] != line_id)):
            raise ValueError(f'inconsistent line identity at source row {source_row}')
        ids.add(station_id)
        keys.add(key)
        line_names[line_id], line_ids[line] = line, line_id
        stations.append({'line_id': line_id, 'station_id': station_id, 'station': station,
                         'line': line, 'query_station': station, 'source_row': source_row})
    if not stations:
        raise ValueError('official worksheet has no stations')
    return {'schema_version': '1.0', 'source': '서울특별시 OA-12764 공개 역정보',
            'source_url': SOURCE_URL, 'source_sha256': source_sha256, 'source_basis_date': basis_date,
            'created_at': datetime.now().astimezone().isoformat(),
            'license': '공공누리 제1유형, 출처: 서울특별시',
            'station_count': len(stations), 'line_count': len(line_names), 'stations': stations,
            'realtime_arrival_verified': False, 'connected_to_departure': False}


def extract_file(source, output, *, basis_date):
    import openpyxl

    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('Use a new output file; existing station evidence is preserved')
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        rows = list(workbook['Data'].iter_rows(values_only=True))
    finally:
        workbook.close()
    snapshot = build_snapshot(rows, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), basis_date=basis_date)
    with output.open('x', encoding='utf8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, allow_nan=False)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--basis-date', required=True, help='공식 파일 목록에 표시된 자료 날짜')
    args = parser.parse_args()
    snapshot = extract_file(args.source, args.out, basis_date=args.basis_date)
    print(json.dumps({'stations': snapshot['station_count'], 'lines': snapshot['line_count'],
                      'source_sha256': snapshot['source_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
