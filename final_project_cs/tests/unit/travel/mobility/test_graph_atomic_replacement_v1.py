"""회전 제약이 결합된 도로 파일을 교체하면 적재된 차량 경로를 재사용하지 않는다."""
import gzip
import json
import os
from pathlib import Path

import pytest

from app.domains.travel_ops.instances.mobility.engine import turn_restrictions
from app.domains.travel_ops.instances.mobility.engine.car import RouterDown
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from .test_car_turn_restrictions_v1 import disk_graph
from .test_graph_router import xy


def packed(rows):
    raw = ''.join(json.dumps(row)+'\n' for row in rows).encode('utf8')
    value = gzip.compress(raw, mtime=0)
    assert len(value) < 8192
    return value.ljust(8192, b'\0')


def prepared(tmp_path):
    policy_path, policy = disk_graph(tmp_path)
    for name in ('nodes.jsonl.gz', 'edges.jsonl.gz'):
        path = tmp_path/name
        rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]
        path.write_bytes(packed(rows))
        policy['graph_sha256'][name] = turn_restrictions.sha256(path)
    policy_path.write_text(json.dumps(policy), encoding='utf8')
    router = GraphRouter(tmp_path)
    before = router.route(xy(0, 0), xy(0, 2))
    return router, before, policy_path, policy


@pytest.mark.parametrize('name', ['nodes.jsonl.gz', 'edges.jsonl.gz'])
@pytest.mark.parametrize('refresh_policy', [False, True])
def test_same_size_and_time_atomic_graph_replacement_requires_fresh_router(tmp_path, name, refresh_policy):
    router, _, policy_path, policy = prepared(tmp_path)
    path = tmp_path/name
    previous = path.stat()
    rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).decode().splitlines()]
    if name.startswith('nodes'):
        rows[0]['lat'] += 0.00001
    else:
        rows[0]['ms'] = 30
    replacement = path.with_suffix('.replacement')
    replacement.write_bytes(packed(rows))
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    os.replace(replacement, path)
    assert path.stat().st_size == previous.st_size
    assert path.stat().st_mtime_ns == previous.st_mtime_ns
    assert turn_restrictions.sha256(path) != policy['graph_sha256'][name]
    if refresh_policy:
        policy['graph_sha256'][name] = turn_restrictions.sha256(path)
        policy_path.write_text(json.dumps(policy), encoding='utf8')
        assert GraphRouter(tmp_path).route(xy(0, 0), xy(0, 2))['paths']
    with pytest.raises(RouterDown, match='적재한 도로 그래프가 바뀌었다'):
        router.route(xy(0, 0), xy(0, 2))


def test_unchanged_graph_does_not_rehash_large_files(tmp_path, monkeypatch):
    router, before, _, _ = prepared(tmp_path)
    monkeypatch.setattr(turn_restrictions, 'sha256', lambda *_: pytest.fail('변경 없는 그래프 재해시 금지'))
    assert router.route(xy(0, 0), xy(0, 2)) == before


@pytest.mark.parametrize('name', ['nodes.jsonl.gz', 'edges.jsonl.gz'])
def test_missing_file_identity_still_detects_atomic_replacement(tmp_path, monkeypatch, name):
    original = Path.stat

    class NoFileIdentity:
        st_ino = 0

        def __init__(self, value):
            self.value = value

        def __getattr__(self, attr):
            return getattr(self.value, attr)

    def stat(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        return NoFileIdentity(value) if path.name in ('nodes.jsonl.gz', 'edges.jsonl.gz') else value

    monkeypatch.setattr(Path, 'stat', stat)
    test_same_size_and_time_atomic_graph_replacement_requires_fresh_router(tmp_path, name, True)
