"""공표값 보강이 거리 확정·별도 운임·없는 간선을 침범하지 않는지 확인한다."""
import json

from app.domains.travel_ops.instances.mobility.engine.line_order import _load_distance_overlay


def test_overlay_keeps_confirmed_distances_and_rejects_special_or_invalid_edges(tmp_path):
    doc = {'lines': {ln: {'edges': [dict(a='A', b='B', distance_m=d)]}
                     for ln, d in [('02호선', 1200), ('09호선', None), ('신분당선', None)]}}
    rows = [dict(line=ln, a='A', b='B', distance_m=distance,
                 grade='공표값·대응방향 추정', sources=[{'source_id': 'public-fixture'}])
            for ln, distance in [('02호선', 1700), ('09호선', 2000), ('신분당선', 3000), ('01호선', 4000)]]
    path = tmp_path/'overlay.json'
    path.write_text(json.dumps({'edges': rows}), encoding='utf8')
    assert _load_distance_overlay(path, doc) == {('09호선', 'A', 'B'): 2000}


def test_conflicting_reverse_rows_are_not_silently_selected(tmp_path):
    doc = {'lines': {'09호선': {'edges': [dict(a='A', b='B', distance_m=None)]}}}
    rows = [dict(line='09호선', a=a, b=b, distance_m=d,
                 grade='공표값·대응방향 추정', sources=[{'source_id': 'public-fixture'}])
            for a, b, d in [('A', 'B', 2000), ('B', 'A', 2500)]]
    path = tmp_path/'overlay.json'
    path.write_text(json.dumps({'edges': rows}), encoding='utf8')
    assert _load_distance_overlay(path, doc) == {}
