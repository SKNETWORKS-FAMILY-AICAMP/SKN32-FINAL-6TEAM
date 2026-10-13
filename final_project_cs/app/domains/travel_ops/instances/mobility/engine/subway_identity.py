"""공식 역ID의 정확 이름·주역명 대응과 파일 내용 판. 운행·방향을 추정하지 않는다."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

STATION_FILE = 'subway_realtime_stations_20260902_v1.json'
PRIMARY_NAME_LINES = frozenset(f'{n}호선' for n in range(1, 9))


def canonical_line(line):
    match = re.fullmatch(r'0?([1-9])호선', line) if isinstance(line, str) else None
    return match.group(1) + '호선' if match else line


def _text(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _id(value):
    return _text(value) and value.isascii() and value.isdigit() and any(c != '0' for c in value)


def source_signature(path):
    """없음도 추적한다. 권한/읽기 오류를 파일 부재로 바꾸지 않는다."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return (str(path), None)
    return (str(path), hashlib.sha256(raw).hexdigest())


class SubwayStationIndex:
    def __init__(self, payload, *, content_sha256):
        if not isinstance(payload, dict) or payload.get('schema_version') != '1.0':
            raise ValueError('공식 지하철 역ID 자료의 스키마가 잘못됐다')
        rows = payload.get('stations')
        if (not isinstance(rows, list) or not rows or type(payload.get('station_count')) is not int
                or payload['station_count'] != len(rows)):
            raise ValueError('공식 지하철 역ID 자료의 역 건수가 맞지 않는다')
        keys, ids, lines = {}, set(), {}
        for row in rows:
            if (not isinstance(row, dict) or not all(_id(row.get(k)) for k in ('line_id', 'station_id'))
                    or not all(_text(row.get(k)) for k in ('line', 'station', 'query_station'))):
                raise ValueError('공식 지하철 역ID 자료의 행이 잘못됐다')
            key = (canonical_line(row['line']), row['station'])
            if key in keys or row['station_id'] in ids:
                raise ValueError('공식 지하철 역ID 자료의 역이 중복됐다')
            if row['line_id'] in lines and lines[row['line_id']] != key[0]:
                raise ValueError('공식 지하철 역ID 자료의 노선 대응이 충돌한다')
            if key[0] in lines.values() and lines.get(row['line_id']) != key[0]:
                raise ValueError('공식 지하철 역ID 자료의 노선 번호가 충돌한다')
            keys[key] = {k: row[k] for k in ('line', 'station', 'query_station', 'line_id', 'station_id')}
            ids.add(row['station_id'])
            lines[row['line_id']] = key[0]
        if type(payload.get('line_count')) is not int or payload['line_count'] != len(lines):
            raise ValueError('공식 지하철 역ID 자료의 노선 건수가 맞지 않는다')
        if not valid_version(content_sha256):
            raise ValueError('공식 지하철 역ID 자료의 내용 해시가 잘못됐다')
        self._by_key = keys
        # 서울시 설명의 주역명(부역명) 표기만 사용한다. 같은 노선에서 모호한
        # 주역명이나 정확 이름과 충돌하는 별칭은 만들지 않는다. 공식 조회명은 유지한다.
        primary_candidates = {}
        for (line, station), row in keys.items():
            match = re.fullmatch(r'([^()\s]+)\(([^()]+)\)', station)
            if line in PRIMARY_NAME_LINES and match and match[2].strip():
                primary_candidates.setdefault((line, match[1]), []).append(row)
        self._by_primary_name = {key: rows[0] for key, rows in primary_candidates.items()
                                 if len(rows) == 1 and key not in keys}
        self._primary_conflicts = {key: [row['station_id'] for row in rows]
                                   for key, rows in primary_candidates.items()
                                   if len(rows) != 1 or key in keys}
        aliases = payload.get('source_aliases', [])
        if not isinstance(aliases, list):
            raise ValueError('공식 이름 대응 자료의 목록이 잘못됐다')
        by_id = {row['station_id']: row for row in keys.values()}
        self._by_source_alias = {}
        for alias in aliases:
            if not isinstance(alias, dict) or not _text(alias.get('alias')):
                raise ValueError('공식 이름 대응 자료의 별명이 잘못됐다')
            row = by_id.get(alias.get('station_id')) if isinstance(alias.get('station_id'), str) else None
            sources = alias.get('source_urls')
            if (row is None or row['line_id'] != alias.get('line_id')
                    or not isinstance(sources, list) or not sources
                    or any(not isinstance(url, str) or not url.startswith('https://') for url in sources)):
                raise ValueError('공식 이름 대응 자료의 역ID·노선·출처가 잘못됐다')
            key = (canonical_line(row['line']), alias['alias'])
            if key in keys or key in primary_candidates or key in self._by_source_alias:
                raise ValueError('공식 이름 대응 자료의 별명이 충돌하거나 중복됐다')
            self._by_source_alias[key] = row
        self.content_sha256 = content_sha256
        self.station_count = len(keys)
        self.line_count = len(lines)

    def lookup(self, line, station):
        if not isinstance(line, str) or not isinstance(station, str):
            return None
        key = (canonical_line(line), station)
        return deepcopy(self._by_key.get(key) or self._by_primary_name.get(key) or self._by_source_alias.get(key))

    def bind(self, leg):
        if not isinstance(leg, dict) or leg.get('mode', 'subway') != 'subway':
            return None
        start, end = (self.lookup(leg.get('line'), leg.get(key)) for key in ('from', 'to'))
        if start is None or end is None or start['station_id'] == end['station_id']:
            return {'status': 'unavailable', 'reason': 'station_identity_unmapped'}
        return {'status': 'matched', 'line_id': start['line_id'], 'station_id': start['station_id'],
                'target_station_id': end['station_id'], 'query_station': start['query_station'],
                'target_station': end['station'], 'line': start['line']}


def valid_version(version):
    return isinstance(version, str) and re.fullmatch('[0-9a-f]{64}', version) is not None


def load(path):
    """파일 한 번 읽은 내용으로 적재와 해시를 함께 만든다."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, (str(path), None)
    digest = hashlib.sha256(raw).hexdigest()
    return SubwayStationIndex(json.loads(raw), content_sha256=digest), (str(path), digest)


def boarding_identity(runtime, legs):
    if not legs or legs[0].get('mode', 'subway') != 'subway':
        return None
    index = getattr(runtime, 'subway_stations', None)
    if index is None:
        return {'status': 'unavailable', 'reason': 'station_identity_source_missing'}
    return index.bind(legs[0])
