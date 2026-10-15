"""저장 안내는 같은 일반 시간표라도 급행 내용 판이 다르면 재계산한다."""
from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest

from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import departure_context as DC, runtime as RT
from .test_departure_observer_v1 import scene, call, prediction
from .test_express_source_reload_v1 import source, write_runs  # noqa: F401
from .test_review_fixes_runtime import _write_mini_data


def inputs(digest='a', *, path='internal-table', modified=1):
    return {'09호선': (path, (modified, 100, 10), digest*64)}


def captured(runtime, context):
    saved = context['options']['p']
    return DC.capture([{'id': 'p', 'eta_min': 5, '_start': 600,
                       '_legs': saved['legs'], '_check': saved['check']}],
        runtime=runtime, origin=context['from_place'], destination=context['to_place'],
        stage='planning', party=context['party'], first_visit=context['first_visit'],
        service_date=date(2026, 10, 9), start_min=600)


def test_capture_records_an_express_content_version():
    runtime, context = scene()
    runtime.express_sources = inputs()
    saved = captured(runtime, context)
    version = saved['basis'].get('express_version')
    assert isinstance(version, str) and len(version) == 64
    assert 'internal-table' not in str(saved['basis'])


def test_changed_express_version_holds_before_external_arrival_query():
    runtime, context = scene()
    runtime.express_sources = inputs()
    saved = captured(runtime, context)
    runtime.express_sources = inputs('b')
    got = call(runtime, saved, bus_arrival=lambda *a, **kw: pytest.fail('낡은 안내에서는 조회하지 않음'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'basis_changed'


def test_identical_contents_at_a_new_path_do_not_hold_an_unchanged_route():
    runtime, context = scene()
    runtime.express_sources = inputs()
    saved = captured(runtime, context)
    runtime.express_sources = inputs(path='moved-table', modified=5)
    assert call(runtime, saved, bus_arrival=prediction)['status'] == 'realtime'


def test_old_context_without_express_version_is_replanned_on_tracked_runtime():
    runtime, context = scene()
    runtime.express_sources = inputs()
    got = call(runtime, context, bus_arrival=lambda *a, **kw: pytest.fail('옛 문맥에서는 조회하지 않음'))
    assert got['status'] == 'needs_replan' and got['reason'] == 'basis_changed'


def test_untracked_manual_runtime_keeps_the_existing_context_contract():
    runtime, context = scene()
    saved = captured(runtime, context)
    assert set(saved['basis']) == {'timetable_built_at', 'rules_version'}
    assert call(runtime, saved, bus_arrival=prediction)['status'] == 'realtime'


def test_absent_and_created_table_and_map_order_are_distinct_inputs():
    runtime, context = scene()
    runtime.express_sources = {'09호선': ('table09', None), **{'01호선': ('table01', None)}}
    absent = captured(runtime, context)
    runtime.express_sources = dict(reversed(list(runtime.express_sources.items())))
    assert captured(runtime, context)['basis'] == absent['basis']
    runtime.express_sources['09호선'] = inputs()['09호선']
    assert captured(runtime, context)['basis'] != absent['basis']


def test_real_file_reload_invalidates_old_notice_and_new_context_passes(tmp_path, source, monkeypatch):
    _write_mini_data(tmp_path)
    write_runs(source)
    first = RT.get_verifier(quiet=True, data_dir=tmp_path, gh_url='', seoul_key='')
    legs = [{'mode': 'subway', 'line': '01호선', 'from': 'A', 'to': 'C'}]
    origin, destination = {'lat': 37.5, 'lon': 127.0}, {'lat': 37.52, 'lon': 127.0}
    def context(runtime):
        return DC.capture([{'id': 'p', 'eta_min': 4, '_start': 600, '_legs': legs,
            '_check': {'legs': deepcopy(legs), 'walk_place_in': 0, 'walk_stop_in': 0,
                       'walk_stop_out': 0, 'walk_place_out': 0}}], runtime=runtime,
            origin=origin, destination=destination, stage='planning', party={}, first_visit=False,
            service_date=date(2026, 10, 7), start_min=600)
    old = context(first)
    monkeypatch.setattr(wiring, '_STATE', dict(mode='enabled', kw={}))
    write_runs(source, 300)
    now = datetime.fromisoformat('2026-10-07T10:05:00+09:00')
    args = dict(now=now, deadline=now+timedelta(minutes=25), origin=origin, destination=destination)
    held = wiring.observe_departure(old, 'p', **args)
    assert held['status'] == 'needs_replan' and held['reason'] == 'basis_changed'
    current = RT.get_verifier()
    assert current is not first and first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600
    assert context(first)['basis'] == old['basis']
    new = context(current)
    got = wiring.observe_departure(new, 'p', **args)
    assert new['basis'] != old['basis']
    assert got['status'] == 'model_revalidated' and got['arrival_at'].endswith('10:09:00+09:00'), got
    assert got['leg_results'][0]['depart_min'] == 605


def test_tracked_source_without_content_hash_cannot_capture_a_fresh_basis():
    runtime, context = scene()
    runtime.express_sources = {"09호선": ("old-table", (1, 100, 10))}
    with pytest.raises(ValueError, match="내용 해시"):
        captured(runtime, context)
