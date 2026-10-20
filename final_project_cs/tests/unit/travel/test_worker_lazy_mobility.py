"""실제 조립과 작은 이동 자료로 지연 적재 경계를 확인한다. 외부 통신은 금지한다."""
from datetime import datetime, timedelta, timezone
from contextlib import nullcontext
from types import SimpleNamespace
import socket
from uuid import uuid4

import pytest

from app import composition
from app.core.project_config import load_project_config
from app.core.service_bindings import bind_services
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import paths, runtime
from scripts import run_sweepers
from tests.unit.travel.mobility.test_review_fixes_runtime import _write_mini_data


@pytest.fixture(autouse=True)
def no_io_and_clean_engine(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('외부 연결을 요청했다')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    old_paths = paths.SOURCE, paths.DATA_DIR
    monkeypatch.setattr(wiring, '_STATE', {'mode': 'unconfigured', 'kw': None, 'datacheck': None})
    monkeypatch.setattr(wiring, '_ANNOUNCED', set())
    monkeypatch.setattr(runtime, '_SINGLETON', None)
    monkeypatch.setattr(composition, '_mobility_configuration_key', None)
    yield
    paths._layout(old_paths[1], old_paths[0])


@pytest.fixture
def configured(monkeypatch, tmp_path):
    _write_mini_data(tmp_path)
    settings = SimpleNamespace(mobility_data_dir=str(tmp_path), mobility_gh_url='', seoul_openapi_key='',
                               guardrails_path='config/guardrails.yaml', mobility_local_router=True)
    monkeypatch.setattr(composition, 'get_settings', lambda: settings)
    calls = []
    original = runtime.build_verifier
    def build(**kwargs):
        calls.append(dict(kwargs))
        return original(**kwargs)
    monkeypatch.setattr(runtime, 'build_verifier', build)
    warmed = []
    monkeypatch.setattr(wiring, '_warm_local_router', lambda rt: warmed.append(rt))
    return settings, calls, warmed


def build_controller(**kwargs):
    return composition.build_controller(llm=object(), broker=object(), **kwargs)


def test_api_default_retains_preload_and_warm(configured):
    settings, calls, warmed = configured
    controller = build_controller()
    assert controller.registry.get('mobility') is not None
    assert len(calls) == len(warmed) == 1
    assert runtime._SINGLETON is warmed[0]
    assert calls[0]['data_dir'] == settings.mobility_data_dir
    assert calls[0]['local_router'] is True


def test_worker_team_binding_observer_construction_do_not_load(configured):
    settings, calls, warmed = configured
    controller = build_controller(preload_mobility=False)
    with bind_services(controller.service_bindings):
        observer = composition.build_mobility_departure_observer(
            settings, SimpleNamespace(), guardrails=SimpleNamespace(get=lambda key: 60))
    assert callable(observer)
    assert wiring.mode() == 'enabled'
    assert wiring._STATE['datacheck']['ok'] is True
    assert wiring._STATE['kw']['data_dir'] == settings.mobility_data_dir
    assert wiring._STATE['kw']['local_router'] is True
    assert calls == warmed == [] and runtime._SINGLETON is None


def test_worker_watch_skipped_gate_does_not_load(configured, monkeypatch):
    settings, calls, warmed = configured
    seen = []
    original = composition.build_controller
    def build(**kwargs):
        seen.append(kwargs)
        return original(llm=object(), broker=object(), **kwargs)
    monkeypatch.setattr(composition, 'build_controller', build)
    monkeypatch.setattr(run_sweepers, '_wire_features', lambda: None)
    monkeypatch.setattr(run_sweepers, '_run_jobs', lambda *a, **kw: {'trip_cases': {'skipped': 1}})
    assert run_sweepers._run_once('synthetic', None) == {'trip_cases': {'skipped': 1}}
    assert seen == [{'preload_mobility': False}]
    assert calls == warmed == [] and runtime._SINGLETON is None


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return nullcontext()


def test_actual_watch_due_gate_closed_does_not_load(configured, monkeypatch):
    from app.application import job_gate
    from app.core import settings as core_settings
    controller = build_controller(preload_mobility=False)
    monkeypatch.setattr(run_sweepers, 'get_connection', Connection)
    monkeypatch.setattr(job_gate, 'claim', lambda *args, **kwargs: False)
    monkeypatch.setattr(job_gate, 'interval_seconds', lambda guard: (180, 180))
    monkeypatch.setattr(core_settings, 'get_guardrails', lambda: object())
    monkeypatch.setattr(run_sweepers, '_run_trip_watch_cases', lambda *args: pytest.fail('주기 문이 닫혔다'))
    with bind_services(controller.service_bindings):
        assert run_sweepers._watch_if_due('synthetic', forced=False) == {'skipped_until_due': 1}
    assert configured[1] == configured[2] == [] and runtime._SINGLETON is None


@pytest.mark.parametrize('has_due_item', [False, True])
def test_real_watch_empty_or_clear_weather_does_not_load(configured, monkeypatch, has_due_item):
    from app.domains.travel_ops.components.watch import trip_watch_cases
    controller = build_controller(preload_mobility=False)
    now = datetime.now(timezone.utc)
    item = SimpleNamespace(item_id=uuid4(), title='서울 활동', kind='activity', detail={},
                           starts_at=now, place={'name': '실내 장소'})
    due = [(uuid4(), item)] if has_due_item else []
    store = SimpleNamespace(tenant_id='synthetic', due=lambda *a, **kw: due)
    seen = []
    monkeypatch.setattr(trip_watch_cases.PendingStore, 'expire', lambda *a, **kw: [])
    def check(**kwargs):
        seen.append(kwargs)
        return {'verdict': 'clear', 'disruptions': [], 'failed': []}
    watcher = trip_watch_cases.TripWatchCaseOpener(store=store, check=check,
        clock=lambda: now, connection_factory=Connection, repository=None,
        run_case=lambda **kwargs: pytest.fail('맑은 판정에서 대안을 만들었다'))
    with bind_services(controller.service_bindings):
        result = watcher.tick()
    assert result.checked == int(has_due_item) and len(seen) == int(has_due_item)
    assert not result.opened and not result.ran and not result.fatal
    assert configured[1] == configured[2] == [] and runtime._SINGLETON is None


@pytest.mark.parametrize('first', ['basis', 'alternative', 'departure'])
def test_first_actual_gateway_loads_same_runtime_once(configured, monkeypatch, first):
    settings, calls, warmed = configured
    controller = build_controller(preload_mobility=False)
    from app.domains.travel_ops.instances.mobility.engine import departure_observer
    observed_runtime = []
    def observe(rt, *args, **kwargs):
        observed_runtime.append(rt)
        return {'status': 'confirmed'}
    monkeypatch.setattr(departure_observer, 'observe', observe)
    with bind_services(controller.service_bindings):
        if first == 'basis':
            assert wiring.basis()['mode'] == 'enabled'
        elif first == 'alternative':
            planner = legs.leg_planner(1, {}, modes=['subway'])
            assert callable(planner)
            a = {'key': 'a', 'name': '가', 'lat': 37.5001, 'lon': 127.0}
            b = {'key': 'b', 'name': '나', 'lat': 37.5201, 'lon': 127.0}
            got, why = planner(a, b, datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=9))))
            assert got is not None, why
            assert got['route']['options']
        else:
            assert wiring.observe_departure({}, 'option')['status'] == 'confirmed'
            assert observed_runtime == [runtime._SINGLETON]
        loaded = runtime._SINGLETON
        wiring.basis()
        wiring.basis()
        assert runtime._SINGLETON is loaded
    assert len(calls) == 1 and warmed == []
    assert calls[0] == wiring._STATE['kw']
    assert calls[0]['data_dir'] == settings.mobility_data_dir
    assert loaded.stats['timetable_stations'] == 3


def test_lazy_and_eager_compute_identical_small_route(configured):
    def result(preload):
        wiring._STATE.update(mode='unconfigured', kw=None, datacheck=None)
        runtime._SINGLETON = None
        composition._mobility_configuration_key = None
        controller = build_controller(preload_mobility=preload)
        with bind_services(controller.service_bindings):
            planner = legs.leg_planner(1, {}, modes=['subway'])
            return planner({'key': 'a', 'name': '가', 'lat': 37.5001, 'lon': 127.0},
                           {'key': 'b', 'name': '나', 'lat': 37.5201, 'lon': 127.0},
                           datetime(2026, 10, 7, 12, tzinfo=timezone(timedelta(hours=9))))
    eager, lazy = result(True), result(False)
    assert eager[0] is not None and lazy[0] is not None
    # 실행 관측 시각만 다르며 경로·방문 시각·원자료 판은 같아야 한다.
    assert eager[0]['departure_context'].pop('captured_at')
    assert lazy[0]['departure_context'].pop('captured_at')
    assert eager == lazy


def test_missing_dataset_still_rejects_lazy_worker(configured, tmp_path):
    settings, calls, warmed = configured
    settings.mobility_data_dir = str(tmp_path / 'missing')
    with pytest.raises(wiring.MobilityUnavailable, match='자료 확인 실패'):
        build_controller(preload_mobility=False)
    assert wiring.mode() == 'broken' and calls == warmed == []


def test_lazy_worker_still_checks_manifest_hash(configured):
    from pathlib import Path
    settings, calls, warmed = configured
    paths.configure(settings.mobility_data_dir)
    wiring.datacheck.write_manifest()
    timetable = Path(settings.mobility_data_dir) / 'travel/processed/mobility/timetable_v1.jsonl'
    old = timetable.read_bytes()
    changed = old.replace(b'weekday', b'holiday', 1)
    assert len(changed) == len(old) and changed != old
    timetable.write_bytes(changed)
    with pytest.raises(wiring.MobilityUnavailable, match='자료 확인 실패'):
        build_controller(preload_mobility=False)
    assert any(row['why'] == '해시가 명세와 다르다' for row in wiring._STATE['datacheck']['mismatched'])
    assert calls == warmed == []


def test_disabled_mobility_team_does_not_configure(configured):
    settings, calls, warmed = configured
    config = load_project_config().model_copy(deep=True)
    for team in config.teams:
        if team.team_id == 'mobility':
            team.active = False
    controller = build_controller(config=config, preload_mobility=False)
    assert ('legs', 'leg_planner') not in controller.service_bindings.values
    assert wiring.mode() == 'unconfigured' and calls == warmed == []


def test_live_settings_change_still_requires_restart(configured):
    settings, calls, warmed = configured
    build_controller(preload_mobility=False)
    settings.mobility_local_router = False
    with pytest.raises(composition.CompositionError, match='restart'):
        build_controller(preload_mobility=False)
    assert calls == warmed == []
