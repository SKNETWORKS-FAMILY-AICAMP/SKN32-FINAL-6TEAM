"""변경 이름·후속 날씨의 합성 재현. 실제 고객 자료·외부 API를 사용하지 않는다."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import chat_edit, decision_unit as du, read_requests, weather_read
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from app.domains.travel_ops.components.intake.reopen import EditPlan

NOW = datetime(2031, 3, 10, 1, tzinfo=timezone.utc)


def item(title, seq=1, replaces=None):
    return SimpleNamespace(item_id=uuid4(), replaces_item_id=replaces, title=title, seq=seq, kind="activity",
                           starts_at=NOW + timedelta(hours=seq), ends_at=NOW + timedelta(hours=seq + 1), detail={},
                           place={"name": title, "latitude": 37.57, "longitude": 126.98, "attributes": {}})


def request(fact="weather", target="i1", reference="explicit", query=None, **extra):
    return {"fact": fact, "target_item": target, "origin_item": "none", "reference": reference,
            "query": query, "text": "", "advice": "", **extra}


def decide(stops, read):
    class Chat:
        def structured(self, *args, **kwargs):
            return {"action": "answer_fact", "target_item": read["target_item"], "target_change": "none",
                    "fact": read["fact"], "minutes": 0, "choices": [], "reads": [read], "social": ""}
    return du.decide(Chat(), stops=du.stops_of(stops), changes=[], history=[], selected_item_id=None, message="장소의 예보")


def forecast(at, **extra):
    return {"kind": "forecast", "source": "test_weather", "confirmed_at": NOW.isoformat(),
            "matched_hour": at.astimezone(weather_read.KST).replace(minute=0, second=0, microsecond=0).isoformat(),
            "precipitation_probability": 0, "precipitation_mm": 0, **extra}


def render(stops, read, *, turns=(), message="장소 예보", lookup=None):
    d = du.Decision("answer_fact", None, None, read["fact"], None, "", reads=[read])
    return read_requests.reply(d, items=stops, message=message, selected=None, turns=turns, version=2,
                               now=NOW, context_now=NOW, ttl_seconds=1800, place_source=None, weather_lookup=lookup)


def test_rename_and_chain_adjustment_are_found_by_saved_ids():
    changed, chain, duplicate = item("새장소"), item("다음장소", 2), item("새장소", 3)
    plan = EditPlan(items=[changed, chain, duplicate], changed=["옛장소 → 새장소", "다음장소"],
                    changed_ids=[changed.item_id, chain.item_id])
    text = chat_edit.done_text([chat_edit.EditOp("place")], items_after=[duplicate, changed, chain], plan=plan)
    assert "새장소" in text and "다음장소" in text and "옛장소" not in text
    assert text.count("새장소") == 1
    assert changed.starts_at.astimezone(weather_read.KST).strftime("%H:%M") in text
    duplicate_line = f"13:00~14:00 {duplicate.title}"
    assert duplicate_line not in text


def test_arrow_in_real_title_and_added_duplicate_are_not_parsed_as_a_display_label():
    row, duplicate = item("강변 → 숲길"), item("강변 → 숲길", 3)
    plan = EditPlan(items=[row, duplicate], added=[row.title], added_ids=[row.item_id])
    text = chat_edit.done_text([chat_edit.EditOp("add")], items_after=[duplicate, row], plan=plan)
    assert text.count(row.title) == 1 and "11:00" in text and "13:00" not in text


@pytest.mark.parametrize("fact", ["weather", "outdoor"])
def test_single_weather_with_null_scope_is_a_valid_read(fact):
    d = decide([item("새장소")], request(fact, reference="previous"))
    assert d.action == "answer_fact" and d.reads[0]["query"] is None


@pytest.mark.parametrize("fact", ["weather", "outdoor"])
def test_weather_scope_still_validates_the_day(fact):
    with pytest.raises(du.DecisionFailed):
        decide([item("새장소")], request(fact, target="none", reference="none",
                                       query={"day": "d999", "period": "all", "kind": "all"}))


def test_foreign_weather_target_is_rejected():
    with pytest.raises(du.DecisionFailed):
        decide([item("새장소")], request(target="i999"))


@pytest.mark.parametrize("fact", ["weather"])
def test_followup_reads_verified_saved_edit_not_wrong_model_guess(fact):
    other, changed = item("다른장소"), item("새장소", 2)
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(changed.item_id), "version": 2,
                                                            "at": NOW.isoformat(), "source": "saved_edit"}}}]
    calls = []
    def lookup(**query):
        calls.append(query)
        return forecast(query["at"])
    outcome, basis, focus = render([other, changed], request(fact, reference="previous"), turns=turns,
                                  message="그곳의 날씨는?", lookup=lookup)
    assert changed.title in outcome["text"] and other.title not in outcome["text"]
    assert calls[0]["at"] == changed.starts_at and focus["item_id"] == str(changed.item_id)
    assert basis["questions"][0]["forecasts"][0]["precipitation_probability"] == 0


@pytest.mark.parametrize("version,age", [(1, 0), (2, 1801)])
def test_old_version_or_expired_focus_never_fetches_a_guessed_place(version, age):
    row = item("새장소")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(row.item_id), "version": version,
                                                            "at": (NOW-timedelta(seconds=age)).isoformat()}}}]
    calls = []
    result, basis, focus = render([row], request(reference="previous"), turns=turns,
                                 message="그곳의 날씨는?", lookup=lambda **q: calls.append(q))
    assert not calls and focus is None and basis["questions"][0]["unresolved"] == "target"


def test_current_weather_keeps_explicit_destination_instead_of_current_schedule_item():
    current, destination = item("현재일정"), item("목적지", 3)
    calls = []
    def lookup(**query):
        calls.append(query)
        return forecast(query["at"])
    result, basis, _ = render([current, destination], request(target="i2", anchor_kind="now", relation="at"),
                             message="목적지의 현재 날씨", lookup=lookup)
    assert destination.title in result["text"] and current.title not in result["text"]
    assert calls[0]["at"] == NOW and basis["questions"][0]["item_id"] == str(destination.item_id)


def test_zero_precipitation_is_a_real_value_and_source_timestamp_are_present():
    row = item("새장소")
    text, basis = weather_read.reply(row, at=row.starts_at, lookup=lambda **q: forecast(q["at"]))
    assert "강수확률 0%" in text and "강수량 0mm" in text and "test_weather" in text and "조회:" in text
    assert "unresolved" not in basis


@pytest.mark.parametrize("field,value", [("latitude", None), ("longitude", float('nan')), ("latitude", True)])
def test_invalid_coordinates_do_not_make_a_forecast_request(field, value):
    row = item("새장소"); row.place[field] = value
    calls = []
    _, basis = weather_read.reply(row, at=row.starts_at, lookup=lambda **q: calls.append(q))
    assert basis["unresolved"] == "weather_coordinates_missing" and not calls


@pytest.mark.parametrize("change,code", [
    ({"precipitation_probability": None, "precipitation_mm": None}, "weather_precipitation_missing"),
    ({"precipitation_probability": float('nan'), "precipitation_mm": -1}, "weather_precipitation_missing"),
    ({"confirmed_at": None}, "weather_provenance_invalid"),
    ({"matched_hour": (NOW+timedelta(days=1)).isoformat()}, "weather_provenance_invalid"),
    ({"kind": "observation"}, "weather_provenance_invalid"),
    ({"source": None}, "weather_provenance_invalid"),
])
def test_incomplete_or_wrong_forecast_is_not_claimed_as_clear_weather(change, code):
    row = item("새장소")
    text, basis = weather_read.reply(row, at=row.starts_at, lookup=lambda **q: forecast(q["at"], **change))
    assert basis["unresolved"] == code and "확인하지 못했어요" in text and "일정은 바꾸지 않았어요" in text


@pytest.mark.parametrize("lookup,code", [(None, "weather_source_unavailable"), (lambda **q: None, "weather_sources_failed")])
def test_missing_source_does_not_become_a_successful_forecast(lookup, code):
    row = item("새장소")
    _, basis = weather_read.reply(row, at=row.starts_at, lookup=lookup)
    assert basis["unresolved"] == code


def test_source_exception_is_recorded_without_hiding_it_as_a_forecast():
    row = item("새장소")
    def broken(**query):
        raise RuntimeError("synthetic source error")
    _, basis = weather_read.reply(row, at=row.starts_at, lookup=broken)
    assert basis["unresolved"] == "weather_source_error"


def test_validated_day_scope_fetches_only_matching_items():
    a, b = item("첫날장소"), item("다음날장소", 2)
    b.starts_at += timedelta(days=1); b.ends_at += timedelta(days=1)
    query = {"day": "d2", "period": "all", "kind": "all"}
    calls = []
    def lookup(**q):
        calls.append(q)
        return forecast(q["at"], fell_back_from=["primary"])
    result, basis, focus = render([a, b], request(target="none", reference="none", query=query), lookup=lookup)
    assert len(calls) == 1 and b.title in result["text"] and a.title not in result["text"]
    assert basis["questions"][0]["forecasts"][0]["fell_back_from"] == ["primary"]
    assert focus["item_id"] == str(b.item_id)


@pytest.mark.parametrize("multiple,race", [(False, False), (True, False), (False, True)])
def test_edit_focus_is_one_directly_changed_item_at_the_saved_version(monkeypatch, multiple, race):
    old = item("옛장소"); changed = item("새장소", replaces=old.item_id); chain = item("뒷장소", 2)
    plan = EditPlan(items=[changed, chain], changed=["옛장소 → 새장소", chain.title],
                    changed_ids=[changed.item_id, chain.item_id])
    ops = [chat_edit.EditOp("place", item_id=old.item_id)]
    if multiple:
        ops.append(chat_edit.EditOp("time", item_id=chain.item_id))
    class Store:
        tenant_id = "synthetic"
        def __init__(self): self.calls = 0
        def latest(self, conn, trip_id):
            self.calls += 1
            return ({"version": 1, "customer_id": uuid4()}, [old]) if self.calls == 1 else ({"version": 3 if race else 2}, [changed, chain])
        def items(self, conn, trip_id, version):
            assert version == 2
            return [changed, chain]
    @contextmanager
    def connect(): yield None
    desk = TripDesk(store=Store(), connection_factory=connect)
    monkeypatch.setattr(desk, "_read_plan", lambda: None)
    monkeypatch.setattr(chat_edit, "ops_for", lambda *a, **k: (ops, {}))
    monkeypatch.setattr(chat_edit, "run", lambda **k: {"changed": True, "version": 2, "plan": plan})
    result = desk.edit(trip_id=uuid4(), base_version=1, decision=None, now=NOW)
    assert "새장소" in result["text"] and result["version"] == 2
    if multiple or race:
        assert "focus" not in result
    else:
        assert result["focus"]["item_id"] == str(changed.item_id) and result["focus"]["version"] == 2


@pytest.mark.parametrize("query", [None, {"day": "d1", "period": "all", "kind": "all"}])
def test_existing_outdoor_classification_never_calls_weather_api(query):
    row = item("실내장소")
    row.place["attributes"]["indoor"] = True
    calls = []
    result, basis, _ = render([row], request("outdoor", query=query), message="실내장소 실내 여부", lookup=lambda **q: calls.append(q))
    assert not calls and "실내" in result["text"] and "강수확률" not in result["text"]
    assert "forecasts" not in basis["questions"][0]


@pytest.mark.parametrize("fact", ["weather", "outdoor"])
@pytest.mark.parametrize("previous", [False, True])
def test_top_level_read_preserves_explicit_target_and_previous_over_screen_selection(fact, previous):
    first, second = item("첫관람지"), item("두번째관람지", 2)
    first.place["attributes"]["indoor"] = False
    second.place["attributes"]["indoor"] = True
    class Chat:
        def structured(self, *args, **kwargs):
            return {"action": "answer_fact", "target_item": "i2", "target_change": "none", "fact": fact,
                    "minutes": 0, "choices": [], "reads": [], "query": None, "social": "",
                    "anchor_kind": "previous" if previous else "none"}
    turns = [{"role": "assistant", "text": "Synthetic prior answer", "reply": {"focus": {"item_id": str(first.item_id), "version": 2, "at": NOW.isoformat()}}}]
    message = "그곳에 관해 알려줘" if previous else "두 번째 관람지 정보를 알려줘"
    d = du.decide(Chat(), stops=du.stops_of([first, second]), changes=[], history=turns,
                  selected_item_id=first.item_id, message=message)
    assert d.reads[0]["reference"] == ("previous" if previous else "explicit")
    calls = []
    def lookup(**query):
        calls.append(query)
        return forecast(query["at"])
    result, basis, focus = read_requests.reply(d, items=[first, second], message=message,
                                              selected=second.item_id if previous else first.item_id,
                                              turns=turns, version=2, now=NOW, context_now=NOW,
                                              ttl_seconds=1800, place_source=None, weather_lookup=lookup)
    expected = first if previous else second
    assert expected.title in result["text"] and focus["item_id"] == str(expected.item_id)
    assert bool(calls) == (fact == "weather")


@pytest.mark.parametrize("fact", ["weather", "outdoor"])
@pytest.mark.parametrize("version,age", [(1, 0), (2, 1801)])
def test_structured_previous_never_guesses_after_version_or_ttl_failure_without_pronoun(fact, version, age):
    row = item("추측대상")
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(row.item_id), "version": version,
                                                            "at": (NOW-timedelta(seconds=age)).isoformat()}}}]
    calls = []
    def lookup(**query):
        calls.append(query)
        return forecast(query["at"])
    result, basis, focus = render([row], request(fact, reference="previous", anchor_kind="previous", relation="at"),
                                  turns=turns, message="이어서 예보 알려줘", lookup=lookup)
    assert not calls and focus is None and basis["questions"][0]["unresolved"] == "target"
    assert "예보:" not in result["text"]
