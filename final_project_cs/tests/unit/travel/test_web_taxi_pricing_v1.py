"""웹 상품 저장·후보·등록 조건 경계. 실제 DB·택시 호출 없이 실행한다."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from app.domains.travel_ops.components.intake import assemble, move_options, pipeline, registered_moves, review, taxi_pricing
from app.domains.travel_ops.components.intake.hours import HoursFacts
from app.domains.travel_ops.components.team_hooks import legs
from tests.unit.travel.test_registered_moves import example


def pricing(product="km_blue_immediate"):
    return {"product": product, "quotes": []}


@pytest.mark.parametrize("product", sorted(taxi_pricing.PRODUCTS))
def test_web_accepts_only_the_five_official_range_products(product):
    value = pricing(product)
    saved, evidence, note = pipeline._checked("trip.taxi_pricing", value)
    assert saved == value and saved is not value and saved["quotes"] is not value["quotes"]
    assert evidence == {"source": "customer"} and note is None


@pytest.mark.parametrize("value", [None, [], "km_blue_immediate", {}, {"product": "km_blue_immediate"},
    {"product": "km_blue_immediate", "quotes": [], "other": 0}, pricing("mycap_reserved"),
    pricing("blue_partners_immediate"), pricing("KM_BLUE"), {"product": True, "quotes": []},
    {"product": "capsi_immediate", "quotes": {}}, {"product": "capsi_immediate", "quotes": [0]}])
def test_bad_or_quote_only_input_is_rejected_without_general_fallback(value):
    with pytest.raises(pipeline.IntakeRejected) as error:
        pipeline._checked("trip.taxi_pricing", value)
    assert error.value.code == "invalid_taxi_pricing"


def test_existing_constraints_are_preserved_and_legacy_fees_cannot_be_double_counted():
    base = {"survey": {"v": 1}, "avoid_districts": ["종로구"], "lighter_day": True}
    before = deepcopy(base)
    result = taxi_pricing.constraints(pricing(), base)
    assert result == {**base, "taxi_call_product": "km_blue_immediate", "taxi_call_quotes": []}
    assert base == before and result["survey"] is not base["survey"]
    with pytest.raises(ValueError, match="함께"):
        taxi_pricing.constraints(pricing(), {"taxi_option_fees": []})


class RecordingConnection:
    def __init__(self, row=("review", 3)):
        self.row, self.calls = row, []

    def transaction(self):
        return nullcontext()

    def cursor(self):
        return nullcontext(self)

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.row


def test_revision_edit_stores_one_structured_claim_and_rechecks_atomically(monkeypatch):
    conn = RecordingConnection()
    monkeypatch.setattr(pipeline, "_sources", lambda *args: [])
    monkeypatch.setattr(pipeline, "_claims", lambda *args: [])
    checks = []
    monkeypatch.setattr(pipeline, "_review_of", lambda *args, **kwargs: (checks.append(args[3]) or {}, None))
    assert pipeline.edit(conn, tenant_id="t", customer_id="c", intake_id="i", revision=3,
                         edits=[{"field": "trip.taxi_pricing", "value": pricing()}]) == 4
    writes = [params for sql, params in conn.calls if "VALUES" in sql]
    assert len(writes) == 1 and writes[0][2:5] == (4, None, "trip.taxi_pricing")
    assert json.loads(writes[0][5]) == pricing() and checks == [4]
    assert "customer_id=%s" in conn.calls[0][0] and conn.calls[0][1] == ("t", "i", "c")


@pytest.mark.parametrize("row,revision,error", [(None, 3, LookupError), (("confirmed", 3), 3, pipeline.IntakeConflict),
                                              (("review", 4), 3, pipeline.IntakeConflict)])
def test_missing_customer_closed_intake_and_stale_revision_write_nothing(row, revision, error):
    conn = RecordingConnection(row)
    with pytest.raises(error):
        pipeline.edit(conn, tenant_id="t", customer_id="c", intake_id="i", revision=revision,
                      edits=[{"field": "trip.taxi_pricing", "value": pricing()}])
    assert not any(sql.startswith(("INSERT", "UPDATE")) for sql, _ in conn.calls)


def inputs(product=None):
    sources = [{"source_id": "s", "position": 0, "kind": "text", "filename": None, "transcript": "경복궁\n광장시장"}]
    claims = []
    for i, (title, start, end, lat, lon) in enumerate([
        ("경복궁", "09:00", "10:00", 37.5796, 126.9770), ("광장시장", "11:00", "12:00", 37.5700, 126.9996)]):
        values = {"title": title, "date": "2026-10-18", "starts_at": start, "ends_at": end, "kind": "activity",
                  "place": {"name": title, "latitude": lat, "longitude": lon, "source": "customer_pick"}}
        claims.extend({"source_id": "s", "field": f"items[{i}].{field}", "value": value, "method": "customer",
                       "evidence": {"line": i + 1}, "needs_review": False, "note": None} for field, value in values.items())
    if product:
        claims.append({"source_id": None, "field": "trip.taxi_pricing", "value": pricing(product),
                       "method": "customer", "evidence": {}, "needs_review": False, "note": None})
    return sources, claims


def engine(fare=10000):
    def run(a, b, arrive, not_before=None):
        start = not_before or arrive - timedelta(minutes=20)
        option = {"id": "taxi", "label": "택시", "eta_min": 20, "uses": [], "fare_krw": fare}
        return {"route": {"options": [option], "planned": "taxi"}, "starts_at": start,
                "ends_at": start + timedelta(minutes=20), "eta_min": 20, "left_out": []}, None
    return run


def test_default_engine_delivers_saved_constraints_through_the_existing_team_hook(monkeypatch):
    calls = []
    monkeypatch.setattr(legs, "leg_planner", lambda party, constraints, **kw: calls.append((party, constraints, kw)) or engine())
    constraints = taxi_pricing.constraints(pricing("capsi_immediate"))
    review.default_engine(2, ["taxi"], constraints=constraints)
    assert calls == [(2, constraints, {"modes": ["taxi"]})]


def test_candidate_factory_uses_the_same_saved_product_for_each_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(review, "default_engine", lambda party, modes=None, **kw: calls.append((party, modes, kw)) or engine())
    factory = move_options._default_factory(2, pricing("turu_blue_immediate"))
    for mode in move_options.MOVE_MODES:
        assert factory(mode) is not None
    assert [modes for _, modes, _ in calls] == [None, ["subway"], ["bus"], ["taxi"], ["walk"]]
    assert all(kwargs["constraints"]["taxi_call_product"] == "turu_blue_immediate" for _, _, kwargs in calls)


def test_product_change_invalidates_previous_fare_and_new_review_returns_saved_value(monkeypatch):
    monkeypatch.setattr(review, "facts_for", lambda *args: HoursFacts(True, {"hours": ["00:00", "23:59"]}))
    seen = []
    def factory(party, modes=None, *, constraints=None):
        selected = (constraints or {}).get("taxi_call_product", "kakao_general")
        seen.append(selected)
        return engine(10000 if selected == "kakao_general" else 13000)
    monkeypatch.setattr(review, "default_engine", factory)
    sources, claims = inputs()
    original = review.build(None, tenant_id="t", intake_id="i", revision=1, sources=sources, claims=claims)
    assert original["taxi_pricing"] == taxi_pricing.default() and original["moves"][0]["fare_krw"] == 10000
    sources, claims = inputs("km_blue_immediate")
    changed = review.build(None, tenant_id="t", intake_id="i", revision=2, sources=sources, claims=claims, previous=original)
    assert changed["taxi_pricing"] == pricing() and changed["moves"][0]["fare_krw"] == 13000
    assert changed["moves"][0]["sig"] != original["moves"][0]["sig"] and "km_blue_immediate" in seen
    public = review.public(changed)
    assert public["taxi_pricing"] == pricing() and "sig" not in public["moves"][0]


def test_assemble_carries_the_same_product_into_confirmation_constraints():
    sources, claims = inputs("capsi_immediate")
    result = assemble.assemble(intake_id="i", revision=4, sources=sources, claims=claims)
    assert result.body["constraints"] == {"taxi_call_product": "capsi_immediate", "taxi_call_quotes": []}
    assert [p["key"] for p in result.body["places"]] == ["p1", "p2"]


def test_registration_remaps_saved_context_keys_without_changing_money_product_or_inputs():
    body, checked = example()
    body["constraints"] = taxi_pricing.constraints(pricing())
    move = checked["moves"][0]
    move.update(mode="taxi", selected_option_id="taxi", departure_context={"schema_version": 1,
        "from_place": {"key": "0-0", "name": "경복궁", "lat": 37.5, "lon": 127.0},
        "to_place": {"key": "0-1", "name": "광장시장", "lat": 37.6, "lon": 127.1},
        "options": {"taxi": {"option_id": "taxi", "path_kind": "direct_taxi", "taxi_call_product": "km_blue_immediate",
                             "check": {"taxi": {"fare_won": 13000}}}}})
    before = deepcopy((body, checked))
    registered = registered_moves.with_review_moves(body, checked)
    context = registered["items"][1]["detail"]["departure_context"]
    assert context["from_place"]["key"] == "p1" and context["to_place"]["key"] == "p2"
    assert context["options"] == move["departure_context"]["options"]
    assert registered["constraints"] == body["constraints"] and (body, checked) == before
