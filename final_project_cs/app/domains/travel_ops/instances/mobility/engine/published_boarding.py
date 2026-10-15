"""운영기관 공표 분과 원시간표를 대조한다. 열차·정차 여부를 추정하지 않는다."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

FILE = 'published_boarding_timetable_v1.json'


def source_signature(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return str(path), None
    return str(path), hashlib.sha256(raw).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class PublishedBoarding:
    def __init__(self, doc, signature):
        if not isinstance(doc, dict) or doc.get('schema_version') != '1.0':
            raise ValueError('공표 승차 시간 자료의 스키마가 잘못됐다')
        self.signature = signature
        self.base_sha256 = doc.get('timetable_sha256')
        if not isinstance(self.base_sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.base_sha256):
            raise ValueError('공표 승차 시간 자료에 원시간표 해시가 없다')
        groups = doc.get('groups')
        if not isinstance(groups, list) or not groups:
            raise ValueError('공표 승차 시간 자료에 대조 그룹이 없다')
        self.groups, self.seen, self.excluded = {}, {}, Counter()
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError('공표 승차 시간 그룹이 잘못됐다')
            line, station = group.get('line'), group.get('station_nm')
            if any(not isinstance(s, str) or not s or s != s.strip() for s in (line, station)):
                raise ValueError('공표 승차 시간 그룹에 정확한 역/노선 이름이 없다')
            if group.get('day_type') not in ('weekday', 'saturday', 'holiday') or group.get('dir') not in ('U', 'D'):
                raise ValueError('공표 승차 시간 그룹의 요일/방향이 잘못됐다')
            minutes = group.get('minutes')
            if (not isinstance(minutes, list) or not minutes
                    or any(type(m) is not int or not 0 <= m <= 30 * 60 for m in minutes)
                    or minutes != sorted(set(minutes)) or group.get('complete') is not True):
                raise ValueError('공표 승차 시간은 완전한 중복 없는 정렬된 분 목록이어야 한다')
            url, observed = group.get('source_url'), group.get('observed_at')
            if not isinstance(url, str) or urlparse(url).scheme != 'https' or not urlparse(url).netloc:
                raise ValueError('공표 승차 시간의 출처 URL이 잘못됐다')
            try:
                stamp = datetime.fromisoformat(observed)
            except (TypeError, ValueError):
                raise ValueError('공표 승차 시간의 조회시각이 잘못됐다') from None
            if stamp.tzinfo is None:
                raise ValueError('공표 승차 시간 조회시각에 시간대가 없다')
            key = line, station, group['day_type'], group['dir']
            if key in self.groups:
                raise ValueError('공표 승차 시간 그룹이 중복됐다')
            self.groups[key] = dict(group, minutes=frozenset(minutes))
            self.seen[key] = Counter()

    def check_base(self, path):
        if file_sha256(path) != self.base_sha256:
            raise RuntimeError('공표 승차 시간 대조의 원시간표 판이 바뀌었다 — 새 원자료를 대조해야 한다')

    def observe(self, row, minute):
        key = row.get('line'), row.get('station_nm'), row.get('day_type'), row.get('dir')
        group = self.groups.get(key)
        if group is None or minute is None:
            return True
        if minute not in group['minutes']:
            self.excluded[key] += 1
            return False
        self.seen[key][minute] += 1
        return True

    def finish(self):
        for key, group in self.groups.items():
            seen = self.seen[key]
            if set(seen) != group['minutes'] or any(n != 1 for n in seen.values()):
                raise RuntimeError(f'공표 승차 시간과 원자료가 1대1 대응하지 않는다: {key}')

    def evidence(self, line, station, day_type):
        groups = [g for key, g in self.groups.items() if key[:3] == (line, station, day_type)]
        return [{'source_url': g['source_url'], 'observed_at': g['observed_at'],
                 'sha256': self.signature[1]} for g in groups]

    def summary(self):
        return [{'line': k[0], 'station_nm': k[1], 'day_type': k[2], 'dir': k[3],
                 'matched': sum(self.seen[k].values()), 'excluded': self.excluded[k]}
                for k in self.groups]


def load(path):
    signature = source_signature(path)
    if signature[1] is None:
        return None, signature
    doc = json.loads(Path(path).read_text(encoding='utf8'))
    if source_signature(path) != signature:
        raise RuntimeError('공표 승차 시간 자료를 읽는 사이 입력이 바뀌었다')
    return PublishedBoarding(doc, signature), signature
