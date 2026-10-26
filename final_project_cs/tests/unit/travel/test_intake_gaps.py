"""D-025 새 구조의 코드 쪽 — 입구 조각(`fragments`) · 사실 검사(`fact_check`) · 빈칸 연결표와 회차(`gaps`) · 먼저 채우기의 빈칸 모으기(`prefill`).
모델 · DB · 네트워크를 쓰지 않는다. `[2026-10-16 D-025]`"""
from app.domains.travel_ops.components.intake import fact_check, fragments, gaps, prefill
from app.domains.travel_ops.components.intake.gaps import Gap, Proposal


def test_explode_keeps_where_each_line_came_from_for_text_messages_and_sheets():
    frags = fragments.explode([("10:00 경복궁\n12:00 광장시장", {"source": 0}), ("아 그리고 택시로", {"message": 3}),
                               ("1일차 | 남산", {"source": 1, "sheet": "일정", "rows": [4]})])
    assert [f.n for f in frags] == [1, 2, 3, 4]
    assert frags[1].origin == {"source": 0, "line": 2} and frags[1].where() == "원본 1 · 2째 줄"
    assert frags[2].where() == "메시지 3 · 1째 줄"
    assert frags[3].origin["row"] == 4 and frags[3].where() == "일정 시트 4행"


def test_chunk_splits_by_length_with_overlap_and_never_splits_a_line():
    frags = fragments.explode([("\n".join(f"{h:02d}:00 장소{h}" for h in range(10)), {"source": 0})])
    chunks = fragments.chunk(frags, limit=40, overlap=2)
    assert len(chunks) > 1
    assert all(c.fragments for c in chunks)
    assert chunks[1].overlap == 2 and chunks[1].fragments[0].n == chunks[0].fragments[-2].n
    covered = set().union(*(c.new_numbers for c in chunks)) | {f.n for f in chunks[0].fragments}
    assert covered == {f.n for f in frags}                                     # 모든 줄이 어느 묶음에서든 새로 읽힌다
    long_line = fragments.explode([("가" * 100, {"source": 0})])
    assert len(fragments.chunk(long_line, limit=40)) == 1                       # 긴 한 줄은 쪼개지 않는다


def test_read_state_note_names_the_day_and_earlier_stops():
    state = fragments.ReadState(day=2, date="2026-10-23", places=["경복궁", "광장시장"])
    assert "day 2 (2026-10-23)" in state.note() and "경복궁" in state.note()
    assert fragments.ReadState().note() == ""


def test_recompute_time_trusts_full_clocks_and_fixes_minutes_but_keeps_pm_guesses():
    assert fact_check.recompute_time("10:00", "10:30") == ("10:30", True)
    assert fact_check.recompute_time("13:30", "1:30") == ("13:30", False)        # 오후로 본 것 — 그대로(확인 필요는 에이전트가 단다)
    assert fact_check.recompute_time("13:00", "1시 반쯤") == ("13:30", True)
    assert fact_check.recompute_time("18:00", "저녁 6시") == ("18:00", False)
    assert fact_check.recompute_time("10:00", "3시") == ("15:00", True)          # 모델 시가 원문과 아예 다르다 — 원문 시(오후)
    assert fact_check.recompute_time("10:00", None) == ("10:00", False)


def test_scope_and_guard_become_questions_not_refusals():
    out = fact_check.scope_gaps(party_size=6, days=None, dates=["2026-10-20", "2026-10-29"], max_days=7, max_party=4)
    assert [g.kind for g in out] == ["out_of_scope", "out_of_scope"] and all(g.owner == "ask_customer" for g in out)
    assert "10일" in out[1].reason
    guard = fact_check.guard_gaps({"travel": True, "instruction_change": True, "out_of_scope": False, "quote": "이전 지시는 무시하고"})
    assert [g.kind for g in guard] == ["guard"] and guard[0].owner == "ask_customer"
    assert fact_check.guard_gaps(None) == []


def test_city_gaps_flag_places_outside_seoul_and_places_not_found():
    items = [{"title": "경복궁"}, {"title": "해운대"}, {"title": "어딘가"}]
    out = fact_check.city_gaps(items, {0: {"address": "서울 종로구"}, 1: {"address": "부산 해운대구"}})
    assert [(g.kind, g.where) for g in out] == [("out_of_scope", {"item": 1}), ("place_not_found", {"item": 2})]


def test_routes_send_each_gap_kind_to_its_owner():
    assert Gap("meal_place", {"item": "a"}, "").owner == "dining_team"
    assert Gap("activity_place", {"item": "a"}, "").owner == "activity_team"
    assert Gap("tight_move", {"item": "a"}, "").owner == "mobility"
    assert Gap("free_slot", {"day": 2}, "").owner == "planner"
    assert Gap("lodging_name", {"trip": "x"}, "").owner == "ask_customer"
    assert Gap("unknown_kind", {"trip": "x"}, "").owner == "ask_customer"     # 모르는 분류는 묻는다(지어내지 않는다)


def test_settle_applies_place_before_move_rechecks_and_stops_after_two_rounds():
    applied: list[list[str]] = []

    def owner(gap, draft):
        return Proposal(gap, gap.owner, [{"title": f"{gap.kind}-pick"}], reason="r")

    def apply(draft, proposals):
        applied.append([p.owner for p in proposals])
        return {**draft, "revision": draft["revision"] + 1}

    rounds = iter([[Gap("tight_move", {"item": "b"}, "새 충돌", source="check")],
                   [Gap("tight_move", {"item": "c"}, "또 충돌", source="check")], []])
    first = [Gap("tight_move", {"item": "a"}, "빠듯"), Gap("meal_place", {"item": "x"}, "저녁"), Gap("lodging_name", {"trip": "l"}, "숙소?")]
    owners = {"dining_team": owner, "mobility": owner, "ask_customer": prefill.ask_owner}
    draft, used, log = gaps.settle({"revision": 1}, first, owners, apply, lambda d: next(rounds), max_rounds=2)
    assert applied[0] == ["dining_team", "mobility"]                          # 장소 → 이동 순서, 고객 질문은 적용하지 않는다
    assert draft["revision"] == 3 and len(log) == 2
    assert [p.owner for p in used].count("ask_customer") == 2                  # 숙소 질문 + 회차를 다 써도 남은 충돌
    assert used[-1].reason.startswith("2회")


def test_owner_failure_becomes_a_question_instead_of_breaking_the_screen():
    def broken(gap, draft):
        raise RuntimeError("team down")

    out = gaps.ask([Gap("meal_place", {"item": "a"}, "저녁 가게")], {"dining_team": broken}, {})
    assert out[0].owner == "ask_customer" and out[0].candidates == [{"question": "저녁 가게"}] and "team down" in out[0].error


def test_model_gaps_attach_to_a_nameless_item_or_become_a_free_slot():
    claims = [{"field": "reading.agent", "source_id": "s1", "value": {
        "used": True, "gaps": [{"kind": "meal_place", "day": 1, "start": None, "end": None, "quote": "저녁은 숙소 근처에서 대충"},
                               {"kind": "free_slot", "day": 2, "start": None, "end": None, "quote": "둘째 날은 알아서"}],
        "missing": ["lodging_name"], "guard": {"travel": True, "instruction_change": False, "out_of_scope": False, "quote": None}}}]
    items = [{"id": "s1-3", "source_id": "s1", "title": "숙소 근처"}]
    out = prefill.model_gaps(claims, items)
    assert [(g.kind, g.where.get("item"), g.owner) for g in out] == [
        ("meal_place", "s1-3", "dining_team"), ("free_slot", None, "planner"), ("lodging_name", None, "ask_customer")]
    assert out[1].where["day"] == 2


def test_check_gaps_are_only_blanks_never_the_customers_own_places_times_or_tight_moves():
    review = {"items": [{"id": "a", "kind": "dining", "status": "review", "place_state": "needs_choice", "title": "성수 식당", "date": "2026-10-22"},
                        {"id": "b", "kind": "activity", "status": "review", "place_state": "needs_choice", "locked": True, "title": "고정", "date": "2026-10-22"},
                        {"id": "c", "kind": "activity", "status": "review", "place_state": "found", "title": "경복궁", "date": "2026-10-22"},
                        {"id": "d", "kind": "dining", "status": "review", "place_state": "needs_name", "title": "예약한 식당", "date": "2026-10-22"},
                        {"id": "e", "kind": "activity", "status": "review", "place_state": "unresolved", "title": "어딘가", "date": "2026-10-22"},
                        {"id": "f", "kind": "dining", "status": "review", "place_state": "needs_choice", "title": "호텔 조식", "date": "2026-10-22",
                         "parts": {"label": "숙소", "lodging_meal": True}}],
              "moves": [{"from": "c", "to": "a", "status": "review"}]}
    out = prefill.check_gaps(review, trip={"party_size": 2})
    assert [(g.kind, g.where["item"], g.owner) for g in out] == [
        ("meal_place", "a", "dining_team"), ("booked_place_name", "d", "ask_customer"), ("place_not_found", "e", "ask_customer"),
        ("lodging_place", "f", "ask_customer")]   # `[2026-10-26 사용자 지시]` 이름 없는 호텔은 고객이 후보에서 고른다


def test_unset_hotel_is_asked_to_pick_from_candidates_and_booked_hotel_still_asks_its_name():
    # `[2026-10-26 사용자 지시 — 호텔 후보는 고객이 고른다]` 전에는 숙소 추천(`lodging_team`)이 첫 후보로 먼저 채웠다
    hotel = {"id": "h", "title": "호텔 조식", "kind": "dining", "place_state": "needs_choice"}
    booked = {**hotel, "id": "b", "booked": True, "place_state": "needs_name"}
    locked = {**hotel, "id": "l", "locked": True}
    found = prefill.check_gaps({"items": [hotel, booked, locked]})
    assert [(g.kind, g.owner) for g in found] == [("lodging_place", "ask_customer"), ("booked_place_name", "ask_customer")]
    assert gaps.CHANGES[found[0].owner] == "question"


def test_model_hotel_gap_uses_stay_owner_and_does_not_repeat_missing_name_question():
    claim = {"field": "reading.agent", "source_id": "s", "value": {"used": True,
             "gaps": [{"kind": "meal_place", "quote": "호텔 조식"}], "missing": ["lodging_name"]}}
    hotel = {"id": "h", "source_id": "s", "title": "호텔 조식", "kind": "dining", "place_state": "needs_choice"}
    assert [(g.kind, g.owner) for g in prefill.model_gaps([claim], [hotel])] == [("lodging_place", "ask_customer")]
    assert prefill.model_gaps([claim], [{**hotel, "place_state": "found", "place": {"category": "숙소 안 식사"}}]) == []


def test_planner_fills_one_slot_at_a_time_and_only_a_few_per_intake():
    calls = []

    def slot(gap, draft):
        calls.append(gap.where["day"])
        return [{"title": "북촌한옥마을", "date": "2026-10-23", "starts_at": "14:00", "ends_at": "15:30", "kind": "activity",
                 "place": {"name": "북촌한옥마을", "latitude": 37.58, "longitude": 126.98, "source": "places"}}]

    owner = prefill.planner_owner(slot)
    got = [owner(Gap("free_slot", {"day": d, "window": [None, None]}, f"{d}일차 알아서"), {}) for d in (1, 2, 3, 4)]
    assert calls == [1, 2, 3]                                                   # 상한(3)을 넘은 빈칸은 계획 에이전트를 부르지 않는다
    assert got[0].candidates[0]["title"] == "북촌한옥마을" and "1일차 알아서" in got[0].candidates[0]["reason"]
    assert got[3].candidates == [] and "앞 3곳만" in got[3].reason
    assert prefill.planner_owner(None)(Gap("free_slot", {"day": 1}, "x"), {}).error == "no planner"
