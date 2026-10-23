"""원래 식당의 영업을 모를 때 채팅도 일정을 유지한 완료 응답을 준다."""
from types import SimpleNamespace
from uuid import uuid4

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from app.domains.travel_ops.components.conversation.trip_messages import handle_trip_message
from app import composition
from app.tools.read_tools import ReadToolbox

from .test_case_version_day import REPORTS, _at, _classifier, _seed
from .test_case_version_day import SCENARIO, Clock, _sources
from app.domains.travel_ops.scenarios.case_engine import CaseEngine
from app.domains.travel_ops.scenarios.replay_services import replay_leg_services
from app.core.service_bindings import bind_services
from app.tools.read_tools import ReadToolbox


def test_dining_unknown_is_answered_without_escalation_or_a_new_itinerary(monkeypatch):
    tenant = "dining_unknown_" + uuid4().hex[:10]
    store, _, trip_id = _seed(tenant)
    desk = TripDesk(store=store, connection_factory=get_connection)
    monkeypatch.setattr(ReadToolbox, "dining_states", lambda self, scope, *, slots, **kwargs: {
        s["place_id"]: {"linked": True, "open_at_slot": None} for s in slots})
    controller = composition.build_controller(tools=ReadToolbox(get_connection, dining_ledger=False), llm=None)
    report = REPORTS["delay"]
    clock=Clock(_at(report['at']))
    check,events=_sources(clock)
    engine=CaseEngine(tenant_id=tenant,check=check,route_events=events,classifier=_classifier,
        report_extractor=None,clock=clock,service_overrides=replay_leg_services(SCENARIO))
    monkeypatch.setattr(ReadToolbox,'dining_states',lambda self,scope,*,slots,**kwargs: {
        s['place_id']:{'linked':True,'open_at_slot':None} for s in slots})
    try:
        arguments = {"tenant": tenant, "trip_id": trip_id, "request_id": "unknown-hours",
                     "message": report["message"], "at": _at(report["at"]), "classifier": _classifier,
                     "chat": SimpleNamespace(json=lambda *_: {"type": "delay", "minutes": report["minutes"]}),
                     "desk": desk, "actor_id": "test", "controller": controller}
        outcome = handle_trip_message(**arguments)
        assert outcome["status"] == "needs_check" and outcome["case_status"] == "resolved"
        assert outcome["answer"] == outcome["outcome"]["message"]
        assert "확인" in outcome["answer"] and "바꾸지" in outcome["answer"]
        with get_connection() as conn:
            assert store.latest(conn, trip_id)[0]["version"] == 1
        with bind_services(engine.controller.service_bindings):
            repeated = handle_trip_message(**arguments)
        assert repeated["status"] == "duplicate" and repeated["case_status"] == "resolved"
        assert outcome["answer"] in repeated["answer"]
    finally:
        cleanup_tenant(tenant)
