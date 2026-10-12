"""백그라운드 회차의 같은 판 유지와 비활성 종류의 미실행을 검증한다."""
from contextlib import nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services, current_bindings, standalone_services
from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange
from app.domains.travel_ops.components.watch import trip_watch_batch, trip_watch_cases, trip_watch
from scripts import run_sweepers


@pytest.fixture(autouse=True)
def feature_process_state(monkeypatch):
    """각 시험이 별도 worker 프로세스의 시작을 나타낸다."""
    monkeypatch.setattr(run_sweepers, "_features_ready", False)


def test_successful_independent_initialization_keeps_the_warmed_pointer_across_rounds(monkeypatch):
    from app import composition
    from app.core import settings as settings_module
    from app.domains.travel_ops.components.conversation import item_pointer
    from app.domains.travel_ops.instances._shared import itinerary_team

    monkeypatch.setattr(settings_module, "get_guardrails", lambda: SimpleNamespace(get=lambda key: "on"))
    monkeypatch.setattr(itinerary_team, "_POINTER", None)

    class Response:
        status_code = 200

        def json(self):
            return {"message": {"content": '{"item":2}'}}

    monkeypatch.setattr(item_pointer.OllamaItemPointer, "_http", lambda *a, **k: Response())
    config = SimpleNamespace(ollama_pointer_model="synthetic-test", ollama_base_url="https://example.invalid",
                             ollama_pointer_background_warm=True)
    pointers = []
    monkeypatch.setattr(composition, "wire_optional_features",
                        lambda: pointers.append(item_pointer.register_from_settings(config)))
    monkeypatch.setattr(composition, "build_controller", lambda: pytest.fail("independent initialization built a Team candidate"))
    monkeypatch.setattr(run_sweepers, "_run_web_guard", lambda tenant: {"cleaned": 0})
    run_sweepers._run_once("travel-test", "web_guard")
    first = pointers[0]
    stops = [SimpleNamespace(item_id=str(i), title=title, starts_at=datetime(2030, 1, 1, 10 + i, tzinfo=timezone.utc),
                             seq=i, kind="dining", place={"name": title})
             for i, title in enumerate(("첫째식당", "둘째식당"), 1)]
    assert itinerary_team.mentioned_item(stops, "첫째식당") is stops[0]
    assert first.wait_idle(2)
    assert itinerary_team.mentioned_item(stops, "첫째식당") is stops[1]
    run_sweepers._run_once("travel-test", "web_guard")
    assert len(pointers) == 1 and itinerary_team._POINTER is first
    assert itinerary_team.mentioned_item(stops, "첫째식당") is stops[1]
    assert current_bindings() is None


def test_failed_feature_initialization_retries_and_only_success_is_remembered(monkeypatch):
    from app import composition

    calls = []

    def wire():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("synthetic initialization failure")

    monkeypatch.setattr(composition, "wire_optional_features", wire)
    with pytest.raises(run_sweepers._FeaturesFailed):
        run_sweepers._wire_features()
    assert not run_sweepers._features_ready
    run_sweepers._wire_features()
    run_sweepers._wire_features()
    assert len(calls) == 2 and run_sweepers._features_ready


def table(*, enabled=(), disabled=(), revision="old", planners=None):
    registry = TeamRegistry()
    for kind in disabled:
        registry.declare_unavailable(kind, "disabled")
    from app.domains.travel_ops.instances.activity import ActivityTeam
    from app.domains.travel_ops.instances.dining import DiningTeam
    from app.domains.travel_ops.instances.mobility import MobilityTeam
    manifests = {"activity": ActivityTeam.manifest, "dining": DiningTeam.manifest, "mobility": MobilityTeam.manifest}
    values = {}
    for kind in enabled:
        registry.register(SimpleNamespace(manifest=manifests[kind].model_copy(deep=True)))
        values[("watch_planners", kind)] = (planners or {}).get(kind, lambda *a: NoChange("clear"))
    return BindingTable(values, registry, revision)


def item(kind):
    return SimpleNamespace(kind=kind, title=f"서울 {kind} 일정", item_id=uuid4(), detail={},
                           place={"name": "서울 방문지"}, starts_at=datetime.now(timezone.utc))


def fake_store(items):
    return SimpleNamespace(tenant_id="travel-test", due=lambda *a, **k: items,
                           pending_departures=lambda *a, **k: [], places=lambda *a, **k: [])


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return nullcontext()


@pytest.mark.parametrize("watcher_module, watcher_type", [
    (trip_watch_cases, trip_watch_cases.TripWatchCaseOpener), (trip_watch, trip_watch.TripWatcher)])
def test_disabled_kind_not_checked_while_independent_kind_continues(monkeypatch, caplog, watcher_module, watcher_type):
    trip_id = uuid4()
    disabled, enabled = item("dining"), item("activity")
    calls = []
    monkeypatch.setattr(watcher_module.PendingStore, "expire", lambda *a, **k: [])
    monkeypatch.setattr(watcher_module, "forecast_attention", lambda *a, **k: None)
    kwargs = dict(store=fake_store([(trip_id, disabled), (trip_id, enabled)]),
                  check=lambda **kw: calls.append(kw) or {"verdict": "clear"},
                  connection_factory=Connection, clock=lambda: datetime.now(timezone.utc))
    if watcher_type is trip_watch_cases.TripWatchCaseOpener:
        kwargs.update(repository=None, run_case=None)
    watcher = watcher_type(**kwargs)
    with bind_services(table(enabled=["activity"], disabled=["dining"])):
        result = watcher.tick()
    assert result.checked == 1 and len(calls) == 1
    assert len(result.unavailable) == 1 and result.unavailable[0]["reason"] == "disabled"
    assert "composition_revision=old" in caplog.text
    assert "kind=dining reason=disabled" in caplog.text
    assert not result.fatal


def test_all_watch_kinds_off_do_not_call_data_or_open_cases(monkeypatch):
    monkeypatch.setattr(trip_watch_cases.PendingStore, "expire", lambda *a, **k: [])
    kinds = ["activity", "dining", "mobility"]
    watcher = trip_watch_cases.TripWatchCaseOpener(
        store=fake_store([(uuid4(), item(kind)) for kind in kinds]),
        check=lambda **kw: pytest.fail("disabled kind called data source"), connection_factory=Connection,
        clock=lambda: datetime.now(timezone.utc), repository=None,
        run_case=lambda **kw: pytest.fail("disabled kind opened a Case"))
    with bind_services(table(disabled=kinds)):
        result = watcher.tick()
    assert result.checked == 0 and len(result.unavailable) == 3
    assert not result.opened and not result.ran


def test_batch_does_not_use_legacy_disabled_planner(monkeypatch):
    monkeypatch.setattr(trip_watch_batch, "_planner", lambda kind: pytest.fail("legacy planner used"))
    work = trip_watch_batch.WatchBatch(None, None, {})
    dining = item("dining")
    with bind_services(table(disabled=["dining"])):
        got = work._one(dining, {"trip_id": str(uuid4())}, {})
    assert got.kind == "unavailable" and got.reasons == ["disabled"]


def test_batch_continues_independent_kind_and_cannot_clear_all_unavailable(monkeypatch):
    work = trip_watch_batch.WatchBatch(None, None, {})
    # 이 부품 시험의 registry 대역은 manifest만 제공한다. 실제 계획·소유 팀 실행은
    # test_classification_execution_plan.py에서 검증하고 여기서는 계산 경계를 주입한다.
    scoped = []
    monkeypatch.setattr(work, "_scoped_work", lambda step: scoped.append(step) or
                        (SimpleNamespace(_guard=lambda task: None), None))
    dining, activity = item("dining"), item("activity")
    with bind_services(table(enabled=["activity"], disabled=["dining"])):
        off = work._one(dining, {"trip_id": "travel"}, {})
        on = work._one(activity, {"trip_id": "travel"}, {})
        work.ctx["evidence"] = []
        with pytest.raises(TeamUnavailable) as raised:
            work._result({}, [], [off, on])
    assert on.kind == "nothing"
    assert len(scoped) == 1  # 비활성 Dining은 계산 경계에도 진입하지 않는다.
    assert raised.value.team_id == "dining" and raised.value.reason == "disabled"


def test_disabled_activity_does_not_block_dining_mobility_batch(monkeypatch):
    trip_id = uuid4()
    issues = [trip_watch_cases.Issue(trip_id, item(kind), [], f"{kind}_other", "place")
              for kind in ("dining", "mobility")]
    customer_id, case_id = uuid4(), uuid4()

    class Cursor(Connection):
        def execute(self, *args):
            pass

        def fetchone(self):
            return (0,)

    class CaseConnection(Connection):
        def cursor(self):
            return Cursor()

    watcher = trip_watch_cases.TripWatchCaseOpener(store=SimpleNamespace(tenant_id="travel-test",
        latest=lambda *a: ({"customer_id": customer_id}, [])),
        check=None, connection_factory=CaseConnection, clock=lambda: datetime.now(timezone.utc),
        repository=None, run_case=None)
    monkeypatch.setattr(watcher, "_attempt", lambda *a: (0, None))
    opened_payloads = []
    watcher._contexts = {}  # tick이 준비하는 회차 상태를 이 부품 시험에서 명시한다.
    monkeypatch.setattr(watcher, "_open_single", lambda *a: pytest.fail("one trip was split into single cases"))
    monkeypatch.setattr(trip_watch_cases, "open_case", lambda *a, **kw:
                        opened_payloads.append(kw) or SimpleNamespace(case_id=case_id, created=True))
    guard = SimpleNamespace(get=lambda name: True if name.endswith("enabled") else 4)
    monkeypatch.setattr("app.core.settings.get_guardrails", lambda: guard)
    with bind_services(table(enabled=["dining", "mobility"], disabled=["activity"])):
        watcher._open_issues(issues, datetime.now(timezone.utc), trip_watch_cases.CaseTickResult(), [])
    assert len(opened_payloads) == 1
    assert opened_payloads[0]["labels"]["issue_code"] == "dining_other"
    assert len(opened_payloads[0]["trigger"]["batch"]) == 2
    assert watcher._contexts[case_id]["batch"] == issues


def test_nested_jobs_hold_one_controller_and_new_round_sees_new_generation(monkeypatch):
    from app import composition
    old, new = table(revision="old"), table(revision="new")
    builds, seen = [], []
    candidate = SimpleNamespace(service_bindings=old)
    monkeypatch.setattr(composition, "build_controller", lambda: builds.append(candidate) or candidate)
    monkeypatch.setattr(composition, "wire_optional_features", lambda: None)

    @run_sweepers._in_round
    def nested():
        seen.append((current_bindings().revision, run_sweepers._round_controller.get()))

    def jobs(*args):
        nonlocal candidate
        nested()
        candidate = SimpleNamespace(service_bindings=new)
        nested()
        return {}

    monkeypatch.setattr(run_sweepers, "_run_jobs", jobs)
    run_sweepers._run_once("travel-test", "trip_cases")
    assert len(builds) == 1 and [r for r, _ in seen] == ["old", "old"]
    assert seen[0][1] is seen[1][1]
    run_sweepers._run_once("travel-test", "trip_cases")
    assert len(builds) == 2 and [r for r, _ in seen] == ["old", "old", "new", "new"]
    assert current_bindings() is None and run_sweepers._round_controller.get() is None


def test_independent_only_job_does_not_require_team_assembly(monkeypatch):
    from app import composition
    monkeypatch.setattr(composition, "build_controller", lambda: pytest.fail("independent job requires Team"))
    monkeypatch.setattr(composition, "wire_optional_features", lambda: None)
    monkeypatch.setattr(run_sweepers, "_run_jobs", lambda *a: {"web_guard": {"scanned": 3}})
    assert run_sweepers._run_once("travel-test", "web_guard") == {"web_guard": {"scanned": 3}}


def test_unavailable_job_reports_skip_and_independent_following_job_can_run(caplog):
    called = []

    @run_sweepers._team_job
    def unavailable():
        raise TeamUnavailable("dining", "disabled")

    with bind_services(table(disabled=["dining"])):
        result = unavailable()
        called.append("independent")
    assert result == {"team_unavailable": 1, "skipped": 1}
    assert called == ["independent"] and "reason=disabled" in caplog.text


def test_active_engine_failure_remains_fatal():
    @run_sweepers._team_job
    def unavailable():
        raise TeamUnavailable("mobility", "engine_unavailable")

    with bind_services(table(enabled=["mobility"])):
        assert unavailable() == {"team_unavailable": 1, "skipped": 1, "fatal": 1}


def test_watch_does_not_close_controller_preserved_case_on_unavailable(monkeypatch):
    monkeypatch.setattr(trip_watch_cases.PendingStore, "expire", lambda *a, **k: [])
    watcher = trip_watch_cases.TripWatchCaseOpener(store=fake_store([]), check=None,
        connection_factory=Connection, clock=lambda: datetime.now(timezone.utc), repository=None,
        run_case=lambda **kw: (_ for _ in ()).throw(TeamUnavailable("mobility", "disabled")))
    case_id = uuid4()
    monkeypatch.setattr(watcher, "_open_issues", lambda issues, now, result, opened: opened.append(case_id))
    monkeypatch.setattr(watcher, "_close_failed", lambda *a: pytest.fail("unavailable Case was closed"))
    with bind_services(table(disabled=["mobility"])):
        result = watcher.tick()
    assert result.unavailable == [{"case_id": str(case_id), "kind": "mobility", "reason": "disabled"}]
    assert not result.failed and not result.ran


def test_all_teams_off_default_round_keeps_independent_cleanup(monkeypatch):
    from app import composition
    empty = table(disabled=["activity", "dining", "mobility"])
    monkeypatch.setattr(composition, "build_controller", lambda: SimpleNamespace(service_bindings=empty))
    monkeypatch.setattr(composition, "wire_optional_features", lambda: None)
    monkeypatch.setattr(composition, "build_classifier", lambda: object())
    monkeypatch.setattr(run_sweepers, "get_connection", Connection)
    monkeypatch.setattr(run_sweepers, "sweep_stuck_classifying", lambda *a, **kw: {"classified": 1})
    monkeypatch.setattr(run_sweepers, "sweep_stuck_routing", lambda *a, **kw: {"started": 0})
    monkeypatch.setattr(run_sweepers, "_watch_if_due", lambda *a, **kw: {"team_unavailable": 3})
    monkeypatch.setattr(run_sweepers, "_run_trip_reminders", lambda *a: {"team_unavailable": 1})
    for name in ("_run_place_facts", "_run_catalog_hours", "_run_trip_places", "_run_web_guard"):
        monkeypatch.setattr(run_sweepers, name, lambda *a: {"scanned": 1})
    result = run_sweepers._run_once("travel-test", None)
    assert result["trip_dawn"] == {"team_unavailable": 1, "skipped": 1}
    assert result["classifying"] == {"classified": 1}
    assert all(result[key] == {"scanned": 1} for key in ("place_facts", "catalog_hours", "trip_places", "web_guard"))


def test_watch_without_explicit_composition_refuses_legacy_globals():
    with standalone_services(False), pytest.raises(TeamUnavailable) as raised:
        trip_watch_batch.unavailable_reason("mobility")
    assert raised.value.reason == "composition_unbound"


@pytest.mark.parametrize("failure", [RuntimeError("private source detail"), ImportError("private plugin path")])
def test_failed_composition_skips_team_jobs_but_keeps_independent_work(monkeypatch, caplog, failure):
    from app import composition
    calls = []

    def fail():
        raise failure

    monkeypatch.setattr(composition, "build_controller", fail)
    monkeypatch.setattr(composition, "wire_optional_features", lambda: None)
    monkeypatch.setattr(composition, "build_classifier", lambda: object())
    monkeypatch.setattr(run_sweepers, "get_connection", Connection)
    monkeypatch.setattr(run_sweepers, "sweep_stuck_classifying", lambda *a, **k: {"classified": 1})
    for name in ("sweep_stuck_routing", "_run_trip_dawn", "_run_trip_reminders"):
        monkeypatch.setattr(run_sweepers, name, lambda *a, **k: pytest.fail("failed composition ran Team work"))
    monkeypatch.setattr(run_sweepers, "_watch_if_due", lambda *a, **k: (
        {"composition_unavailable": 1, "fatal": 1} if k["composition_failed"] else pytest.fail("lost failure")))
    for name in ("_run_place_facts", "_run_catalog_hours", "_run_trip_places", "_run_web_guard"):
        monkeypatch.setattr(run_sweepers, name, lambda *a, name=name: calls.append(name) or {"scanned": 1})
    result = run_sweepers._run_once("travel-test", None)
    assert result["composition"] == {"fatal": 1}
    assert result["classifying"] == {"classified": 1}
    assert len(calls) == 4
    assert all(result[name]["fatal"] == 1 and result[name]["skipped"] == 1
               for name in ("routing", "trip_dawn", "trip_reminders"))
    assert current_bindings() is None and run_sweepers._round_controller.get() is None
    assert type(failure).__name__ in caplog.text and str(failure) not in caplog.text


def test_one_job_exception_keeps_the_same_round_and_runs_later_jobs(monkeypatch, caplog):
    from app import composition
    bound = table(revision="stable")
    monkeypatch.setattr(composition, "build_controller", lambda: SimpleNamespace(service_bindings=bound))
    monkeypatch.setattr(composition, "wire_optional_features", lambda: None)
    monkeypatch.setattr(composition, "build_classifier", lambda: object())
    monkeypatch.setattr(run_sweepers, "get_connection", Connection)
    monkeypatch.setattr(run_sweepers, "sweep_stuck_classifying", lambda *a, **k: {})
    monkeypatch.setattr(run_sweepers, "sweep_stuck_routing", lambda *a, **k: {})

    def fail(*args, **kwargs):
        raise RuntimeError("private customer text")

    monkeypatch.setattr(run_sweepers, "_watch_if_due", fail)
    observed = []
    for name in ("_run_trip_dawn", "_run_trip_reminders", "_run_place_facts", "_run_catalog_hours",
                 "_run_trip_places", "_run_web_guard"):
        monkeypatch.setattr(run_sweepers, name, lambda *a: observed.append(current_bindings()) or {"scanned": 1})
    result = run_sweepers._run_once("travel-test", None)
    assert result["trip_cases"] == {"fatal": 1}
    assert len(observed) == 6 and all(got is bound for got in observed)
    assert "job=trip_cases error_type=RuntimeError" in caplog.text
    assert "private customer text" not in caplog.text


@pytest.mark.parametrize("due", [False, True])
def test_composition_failure_keeps_safety_inside_the_existing_watch_gate(monkeypatch, due):
    from app.application import job_gate
    from app.domains.travel_ops.components.watch import monitoring
    calls = []
    monkeypatch.setattr(job_gate, "interval_seconds", lambda *a: (180, 180))
    monkeypatch.setattr(job_gate, "claim", lambda *a, **k: due)
    monkeypatch.setattr(run_sweepers, "get_connection", Connection)
    monkeypatch.setattr(monitoring, "execute", lambda *a, work, **k: work())
    monkeypatch.setattr(run_sweepers, "_run_trip_safety", lambda *a: calls.append("safety") or {"checked": 2})
    monkeypatch.setattr(run_sweepers, "_run_trip_watch_cases", lambda *a: pytest.fail("Team watch executed"))
    result = run_sweepers._watch_if_due("travel-test", forced=False, composition_failed=True)
    if due:
        assert result == {"composition_unavailable": 1, "skipped": 1, "fatal": 1, "safety_checked": 2}
        assert calls == ["safety"]
    else:
        assert result == {"skipped_until_due": 1} and calls == []


def test_resident_round_exception_is_reported_and_next_round_runs(monkeypatch, capsys, caplog):
    calls = []

    def run(*args):
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("private input")
        return {"web_guard": {"scanned": 1}}

    def sleep(*args):
        if len(calls) == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(run_sweepers, "get_settings", lambda: SimpleNamespace(tenant_id="travel-test"))
    monkeypatch.setattr(run_sweepers, "_run_once", run)
    monkeypatch.setattr(run_sweepers.time, "sleep", sleep)
    monkeypatch.setattr("sys.argv", ["run_sweepers", "--interval", "1"])
    with pytest.raises(KeyboardInterrupt):
        run_sweepers.main()
    output = capsys.readouterr()
    assert len(calls) == 3 and len(output.out.strip().splitlines()) == 3
    assert "errored=1" in output.err and "private input" not in caplog.text


def test_once_round_exception_returns_a_failed_exit(monkeypatch, capsys):
    def fail(*args):
        raise RuntimeError("private input")

    monkeypatch.setattr(run_sweepers, "get_settings", lambda: SimpleNamespace(tenant_id="travel-test"))
    monkeypatch.setattr(run_sweepers, "_run_once", fail)
    monkeypatch.setattr("sys.argv", ["run_sweepers"])
    assert run_sweepers.main() == 1
    output = capsys.readouterr()
    assert '"round": {"errored": 1}' in output.out and "errored=1" in output.err


@pytest.mark.parametrize("mode", ["features", "composition_and_features", "independent_only", "independent_safety"])
def test_feature_wiring_failure_keeps_cleanup_but_never_broadens_watch_scope(monkeypatch, mode, caplog):
    from app import composition
    calls = []

    def build():
        if mode == "composition_and_features":
            raise ImportError("private plugin path")
        if mode in ("independent_only", "independent_safety"):
            pytest.fail("independent cleanup requires Team assembly")
        return SimpleNamespace(service_bindings=table())

    def wire():
        raise ImportError("private feature path")

    monkeypatch.setattr(composition, "build_controller", build)
    monkeypatch.setattr(composition, "wire_optional_features", wire)
    monkeypatch.setattr(composition, "build_classifier", lambda: object())
    monkeypatch.setattr(run_sweepers, "get_connection", Connection)
    monkeypatch.setattr(run_sweepers, "sweep_stuck_classifying", lambda *a, **k: {"classified": 1})
    for name in ("sweep_stuck_routing", "_watch_if_due", "_run_trip_safety", "_run_trip_dawn", "_run_trip_reminders"):
        monkeypatch.setattr(run_sweepers, name, lambda *a, **k: pytest.fail("unsafe scope-dependent work executed"))
    for name in ("_run_place_facts", "_run_catalog_hours", "_run_trip_places", "_run_web_guard"):
        monkeypatch.setattr(run_sweepers, name, lambda *a, name=name: calls.append(name) or {"scanned": 1})
    only = {"independent_only": "web_guard", "independent_safety": "trip_safety"}.get(mode)
    result = run_sweepers._run_once("travel-test", only)
    assert result["features"] == {"fatal": 1}
    if mode == "independent_only":
        assert calls == ["_run_web_guard"]
    elif mode == "independent_safety":
        assert calls == [] and result["trip_safety"]["features_unavailable"] == 1
    else:
        assert len(calls) == 4 and result["classifying"] == {"classified": 1}
        assert all(result[name]["features_unavailable"] == 1 for name in
                   ("routing", "trip_cases", "trip_dawn", "trip_reminders"))
    assert ("composition" in result) == (mode == "composition_and_features")
    assert "sweeper_features_failed error_type=ImportError" in caplog.text
    assert "private feature path" not in caplog.text
    assert current_bindings() is None and run_sweepers._round_controller.get() is None
