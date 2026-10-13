"""거리 보강 파일이 빠지거나 새 판이 추가되어도 조용히 다른 입력을 쓰지 않는다."""
import hashlib
import json

from app.domains.travel_ops.instances.mobility.engine import datacheck, paths
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime


def test_manifest_rejects_removed_overlay_and_fallback_to_older_track(tmp_path, monkeypatch):
    base = tmp_path/'mobility'
    base.mkdir()
    monkeypatch.setattr(paths, 'PROCESSED', tmp_path)
    v1, v2, overlay = (base/name for name in (
        'rail_edge_track_v1.jsonl.gz', 'rail_edge_track_v2.jsonl.gz', 'rail_distance_overlay_v1.json'))
    for p in (v1, v2, overlay):
        p.write_bytes(b'same-size-content')
    entries = [{'path': p.name, 'bytes': p.stat().st_size,
                'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (v1, v2, overlay)]
    (base/datacheck.GIT_MANIFEST_NAME).write_text(json.dumps({'files': entries}), encoding='utf8')
    monkeypatch.setattr(datacheck, '_paths', lambda: {'rail_track': v2, 'rail_distance_overlay': overlay})
    assert datacheck.check()['ok']
    v2.unlink()
    overlay.unlink()
    monkeypatch.setattr(datacheck, '_paths', lambda: {'rail_track': v1})
    result = datacheck.check()
    assert not result['ok']
    assert {r['file'] for r in result['mismatched']} == {'rail_track', 'rail_distance_overlay'}


def test_runtime_detects_new_distance_version_and_new_overlay(tmp_path):
    order = tmp_path/'line_station_order_v1.json'
    v1 = tmp_path/'rail_edge_track_v1.jsonl.gz'
    order.write_text('{}', encoding='utf8')
    v1.write_bytes(b'old')
    runtime = Runtime(None, timetable_built_at='', rules_version='', stats={}, source_mtimes={
        'order': (str(order), order.stat().st_mtime), 'rail_track': (str(v1), v1.stat().st_mtime)})
    assert runtime.changed_sources() == []
    (tmp_path/'rail_edge_track_v2.jsonl.gz').write_bytes(b'new')
    (tmp_path/'rail_distance_overlay_v1.json').write_text('{}', encoding='utf8')
    assert set(runtime.changed_sources()) == {'rail_track', 'rail_distance_overlay'}
