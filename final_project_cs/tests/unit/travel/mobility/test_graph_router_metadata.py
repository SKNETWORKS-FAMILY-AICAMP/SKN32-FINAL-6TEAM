"""자료를 적재하기 전에도 실제 보행망 판·OSM 날짜를 알린다."""
import json

import pytest

from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter


@pytest.mark.parametrize(
    'version, source',
    [('road_graph_v1', 'osm_road_graph@2026-10-03'),
     ('road_graph_v2', 'osm_road_graph_v2@2026-10-03')],
)
def test_info_reports_manifest_version_and_date_before_loading(tmp_path, version, source):
    for name in ('nodes.jsonl.gz', 'edges.jsonl.gz'):
        (tmp_path / name).touch()
    (tmp_path / 'MANIFEST.json').write_text(json.dumps({
        'version': version, 'osm_data_at': '2026-10-03T20:20:50Z',
    }), encoding='utf-8')
    router = GraphRouter(tmp_path)
    assert router.info() == {'version': f'local:{version}', 'source_id': source}
    assert router.source_id == source
    assert not router._loaded


def test_metadata_without_manifest_keeps_legacy_identifier(tmp_path):
    for name in ('nodes.jsonl.gz', 'edges.jsonl.gz'):
        (tmp_path / name).touch()
    router = GraphRouter(tmp_path)
    assert router.info() == {
        'version': 'local:road_graph_v1', 'source_id': 'osm_road_graph@2026-09-18',
    }


def test_info_refuses_missing_graph_even_when_manifest_exists(tmp_path):
    (tmp_path / 'MANIFEST.json').write_text(json.dumps({
        'version': 'road_graph_v2', 'osm_data_at': '2026-10-03T20:20:50Z',
    }), encoding='utf-8')
    assert GraphRouter(tmp_path).info() is None
