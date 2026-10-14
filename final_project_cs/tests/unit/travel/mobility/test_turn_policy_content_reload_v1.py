"""크기·수정시각이 보존된 회전자료 교체도 다음 차량 요청에서 재검사한다."""
from copy import deepcopy
import json
import os

import pytest

from app.domains.travel_ops.instances.mobility.engine.car import RouterDown
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from .test_car_turn_restrictions_v1 import disk_graph, rule
from .test_graph_router import make_records, xy


def encoded(data):
    value = json.dumps(data).encode('utf8') if isinstance(data, dict) else data
    assert len(value) <= 4096
    return value.ljust(4096, b' ')


def prepared(tmp_path):
    path, data = disk_graph(tmp_path)
    path.write_bytes(encoded(data))
    router = GraphRouter(tmp_path)
    before = router.route(xy(0, 0), xy(0, 2))
    return path, data, router, before


def replace_preserving_metadata(path, data):
    previous = path.stat()
    # 파일을 원자적으로 교체해도 copy2 등으로 원래 메타데이터가 보존될 수 있다.
    replacement = path.with_suffix('.replacement')
    replacement.write_bytes(encoded(data))
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    os.replace(replacement, path)
    assert path.stat().st_size == previous.st_size
    assert path.stat().st_mtime_ns == previous.st_mtime_ns


def test_valid_content_replacement_recalculates_vehicle_route(tmp_path):
    path, data, router, before = prepared(tmp_path)
    changed = deepcopy(data)
    changed['rules'] = [rule(make_records(), (1, 0), (1, 1), (1, 2))]
    replace_preserving_metadata(path, changed)
    after = router.route(xy(0, 0), xy(0, 2))
    fresh = GraphRouter(tmp_path).route(xy(0, 0), xy(0, 2))
    assert before['paths'][0]['distance'] > fresh['paths'][0]['distance']
    assert after == fresh


@pytest.mark.parametrize('fault', ['corrupt', 'graph_binding', 'invalid_rule'])
def test_invalid_same_metadata_content_never_uses_cached_policy(tmp_path, fault):
    path, data, router, _ = prepared(tmp_path)
    if fault == 'corrupt':
        data = b'{'
    elif fault == 'graph_binding':
        data['graph_sha256']['edges.jsonl.gz'] = '0' * 64
    else:
        data['rules'][0]['outgoing'] = 9999
    replace_preserving_metadata(path, data)
    with pytest.raises(RouterDown, match='turn_restrictions'):
        router.route(xy(0, 0), xy(0, 2))


def test_identical_content_keeps_loaded_policy_without_rehashing_graph(tmp_path, monkeypatch):
    path, data, router, before = prepared(tmp_path)
    replace_preserving_metadata(path, data)
    from app.domains.travel_ops.instances.mobility.engine import turn_restrictions
    monkeypatch.setattr(turn_restrictions, 'sha256', lambda *_: pytest.fail('같은 내용의 그래프 재해시 금지'))
    assert router.route(xy(0, 0), xy(0, 2)) == before
