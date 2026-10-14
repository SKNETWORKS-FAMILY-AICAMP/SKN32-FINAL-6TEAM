"""고객이 말한 기준(일정 · 끼니 · 시각 · 지금 · 앞 답)과 앞뒤로 서버가 답할 일정을 고른다(`time_anchor.py`) — 2026-10-14 x600 재시험의 오답을 그대로 시험으로 옮겼다."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests, time_anchor

KST = timezone(timedelta(hours=9))
DAY1, DAY2 = datetime(2026, 10, 14, tzinfo=KST), datetime(2026, 10, 15, tzinfo=KST)


def _item(title, day, start, end, seq):
    return SimpleNamespace(item_id=uuid4(), title=title, kind="activity", seq=seq, detail={},
                           starts_at=day.replace(hour=start[0], minute=start[1]), ends_at=day.replace(hour=end[0], minute=end[1]),
                           place={"name": title, "attributes": {}, "kind": "activity"})


TRIP = [_item("서울역 도착", DAY1, (9, 0), (10, 25), 1), _item("경복궁 관람", DAY1, (10, 30), (12, 0), 2),
        _item("토속촌 삼계탕", DAY1, (12, 30), (13, 30), 3), _item("국립현대미술관 서울", DAY1, (14, 30), (16, 0), 4),
        _item("북촌한옥마을 산책", DAY1, (17, 0), (18, 30), 5), _item("광장시장", DAY1, (19, 0), (20, 0), 6),
        _item("남산서울타워", DAY2, (10, 0), (11, 30), 7), _item("롯데월드타워 서울스카이", DAY2, (15, 0), (16, 30), 8)]
NOON = DAY1.replace(hour=11, minute=10)


def _pick(now=NOON, anchor=None, previous=None, named=None, **read):
    if "at_time" in read:
        read["anchor_time"] = read.pop("at_time")
    item, _basis = time_anchor.resolve({"anchor_kind": "none", "anchor_item": "none", "at_day": "none", "anchor_time": "", "relation": "at",
                                        "steps": 1, **read}, items=TRIP, anchor=anchor, previous=previous, named=named, now=now)
    return item.title if item else None


def test_a_clock_time_without_a_day_is_today_and_picks_the_stop_in_progress_not_tomorrows_same_hour():
    assert _pick(at_time="15:00") == "국립현대미술관 서울"          # 내일 15:00 롯데월드타워가 아니다
    assert _pick(at_time="14:00") == "국립현대미술관 서울"          # 비는 시각이면 그 뒤에 시작하는 일정
    assert _pick(at_time="11:30") == "경복궁 관람"


def test_a_named_day_wins_and_boundary_times_take_the_stop_starting_or_ending_then():
    assert _pick(at_time="15:00", at_day="tomorrow") == "롯데월드타워 서울스카이"
    assert _pick(at_time="15:00", at_day="d2") == "롯데월드타워 서울스카이"
    assert _pick(at_time="12:00") == "경복궁 관람"                  # 「정오」 — 12:00 에 끝나는 관람(재생 정답)
    assert _pick(at_time="13:30") == "토속촌 삼계탕"                # 「한시 반」 — 13:30 에 끝나는 점심
    assert _pick(at_time="12:30") == "토속촌 삼계탕"                # 그 시각에 시작하는 일정이 먼저


def test_a_named_stop_is_the_anchor_and_the_answer_is_computed_from_it():
    """「국립현대미술관 바로 앞 일정」은 미술관이 기준, 답은 그 앞 — 모델이 기준과 답을 한 칸에 섞던 것(재생 v3)을 칸으로 나눴다."""
    assert _pick(anchor_kind="item", anchor_item="i4", anchor=TRIP[3], relation="before") == "토속촌 삼계탕"
    assert _pick(anchor_kind="item", anchor_item="i3", anchor=TRIP[2], relation="after") == "국립현대미술관 서울"   # 「점심 먹고 나서」
    assert _pick(anchor_kind="item", anchor_item="i3", anchor=TRIP[2], relation="after", steps=2) == "북촌한옥마을 산책"
    assert _pick(anchor_kind="item", anchor_item="i3", anchor=TRIP[2]) == "토속촌 삼계탕"                       # 기준 그 자체
    assert _pick(anchor_kind="item", anchor_item="i6", anchor=TRIP[5], relation="after") == "남산서울타워"        # 날을 넘어 다음 일정


def test_the_previous_answer_is_the_anchor_for_follow_ups_and_missing_one_gives_up():
    assert _pick(anchor_kind="previous", previous=TRIP[4], relation="before") == "국립현대미술관 서울"   # 「그럼 그 전에는?」
    assert _pick(anchor_kind="previous", previous=None, relation="before") is None


def test_a_name_in_the_sentence_that_disagrees_with_the_model_anchor_is_asked_back_not_overwritten():
    item, basis = time_anchor.resolve({"anchor_kind": "item", "anchor_item": "i8", "relation": "before", "steps": 1}, items=TRIP,
                                      anchor=TRIP[7], named=[TRIP[3]], now=NOON)
    assert item is None and basis["time_anchor"] == "anchor_conflict"
    assert _pick(anchor_kind="item", anchor_item="i4", anchor=TRIP[3], named=[TRIP[3]], relation="before") == "토속촌 삼계탕"
    # 문장에 이름이 둘 이상 잡히면 대조하지 않는다(어느 쪽이 기준인지 문장만으로 못 정한다)
    assert _pick(anchor_kind="item", anchor_item="i4", anchor=TRIP[3], named=[TRIP[3], TRIP[2]], relation="before") == "토속촌 삼계탕"


def test_no_anchor_and_no_relation_keeps_the_model_target():
    assert time_anchor.resolve({"anchor_kind": "none", "relation": "at", "steps": 1}, items=TRIP, target=TRIP[2], now=NOON) == (None, None)


def test_next_and_previous_without_an_anchor_count_from_now():
    assert _pick(relation="after") == "토속촌 삼계탕"               # 11:10 기준 다음 일정
    assert _pick(relation="after", steps=2) == "국립현대미술관 서울"
    assert _pick(relation="before") == "서울역 도착"               # 지금 전에 끝난 마지막 일정
    assert _pick(anchor_kind="now", relation="after") == "토속촌 삼계탕"


def test_out_of_range_gives_up():
    assert _pick(anchor_kind="item", anchor_item="i1", anchor=TRIP[0], relation="before") is None
    assert _pick(at_time="23:00") is None                             # 그날 그 뒤 일정 없음 — 지어내지 않는다
    assert _pick(relation="before", now=DAY1.replace(hour=8)) is None    # 첫 일정 전 — 앞 일정이 없다


def test_bad_fields_are_emptied_instead_of_failing_the_whole_reading():
    days = ["all", "today", "tomorrow", "d1", "d2", "none"]
    got = time_anchor.clean({"at_time": "3pm", "at_day": "friday", "relation": "around", "steps": 9}, days)
    assert (got["anchor_kind"], got["anchor_time"], got["at_day"], got["relation"], got["steps"]) == ("none", "", "none", "at", 1)
    # 옛 칸 at_time 만 있어도 시각 기준으로 읽는다 · 없는 별칭을 가리킨 일정 기준은 기준 없음으로
    assert time_anchor.clean({"at_time": "15:00"}, days)["anchor_kind"] == "time"
    assert time_anchor.clean({"anchor_kind": "item", "anchor_item": "i99"}, days, ["i1", "none"])["anchor_kind"] == "none"


def _reply(message, turns=(), **read):
    base = dict(fact="time", target_item="none", reference="none", origin_item="none", query=None, text=message, advice="",
                anchor_kind="none", anchor_item="none", anchor_time="", at_time="", at_day="none", relation="at", steps=1)
    decision = du.Decision("answer_fact", None, None, read.get("fact", "time"), None, "", reads=[{**base, **read}])
    return read_requests.reply(decision, items=TRIP, message=message, selected=None, turns=turns, version=1,
                               now=NOON, context_now=NOON, ttl_seconds=1800, place_source=None)


def test_the_reply_answers_the_computed_stop_not_the_model_guess():
    result, basis, focus = _reply("오후 3시에 뭐 해?", target_item="i8", reference="explicit", anchor_kind="time", anchor_time="15:00")
    assert "국립현대미술관" in result["text"] and "롯데월드타워" not in result["text"], result
    assert basis["questions"][0]["time_anchor"]["time_anchor"] == "resolved"
    assert focus["item_id"] == str(TRIP[3].item_id)


def test_the_stop_right_before_a_named_stop_is_answered_not_the_named_stop_or_the_previous_topic():
    """실서버 10-14: 「국립현대미술관 바로 앞 일정이 뭐야?」가 앞 질문 대상(롯데월드타워)을 이어받아 엉뚱한 일정을 답했다."""
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(TRIP[7].item_id), "version": 1, "at": NOON.isoformat()}}}]
    result, _basis, focus = _reply("국립현대미술관 바로 앞 일정이 뭐야?", turns=turns, anchor_kind="item", anchor_item="i4", relation="before")
    assert "토속촌" in result["text"], result
    assert focus["item_id"] == str(TRIP[2].item_id)


def test_a_follow_up_before_uses_the_previous_answer():
    turns = [{"role": "assistant", "reply": {"focus": {"item_id": str(TRIP[4].item_id), "version": 1, "at": NOON.isoformat()}}}]
    result, _basis, focus = _reply("그럼 그 전에는 뭐 해?", turns=turns, anchor_kind="previous", relation="before")
    assert focus["item_id"] == str(TRIP[3].item_id), result


def test_a_next_fact_without_a_relation_means_right_after_the_anchor():
    _result, _basis, focus = _reply("점심 다음 일정은?", fact="next", anchor_kind="item", anchor_item="i3")
    assert focus["item_id"] == str(TRIP[3].item_id)


def test_a_conflicting_anchor_is_asked_back():
    # 이름 대조는 일정 이름 전체가 문장에 있을 때만 잡힌다(`fact_context.named_items`) — 줄인 이름은 모델 기준을 그대로 쓴다
    result, basis, focus = _reply("국립현대미술관 서울 바로 앞 일정이 뭐야?", anchor_kind="item", anchor_item="i8", relation="before")
    assert "기준" in result["text"], result
    assert focus is None or focus.get("item_id") is None


def test_the_answer_schema_requires_the_new_fields():
    stops = [du.Stop(f"i{n}", item) for n, item in enumerate(TRIP, 1)]
    read = du._schema(stops, [])["properties"]["reads"]["items"]
    assert {"anchor_kind", "anchor_item", "anchor_time", "at_day", "relation", "steps"} <= set(read["required"])
    assert "previous" in read["properties"]["anchor_kind"]["enum"] and "i4" in read["properties"]["anchor_item"]["enum"]
    assert "tomorrow" in read["properties"]["at_day"]["enum"] and "none" in read["properties"]["at_day"]["enum"]


def _decide(**top):
    stops = [du.Stop(f"i{n}", item) for n, item in enumerate(TRIP, 1)]
    answer = {"action": "answer_fact", "target_item": "none", "target_change": "none", "fact": "time", "minutes": 0, "choices": [],
              "reads": [], "social": "", "general_requests": [], "change_scope": "none", "destination_text": "", "condition_text": "",
              "anchor_kind": "none", "anchor_item": "none", "anchor_time": "", "at_day": "none", "relation": "at", "steps": 1, **top}
    chat = SimpleNamespace(structured=lambda system, user, schema, num_predict=160: answer)
    return du.decide(chat, stops=stops, changes=[], history=[], selected_item_id=None, message="오늘 18시 30분에 뭐 해?", now=NOON)


def test_a_top_level_time_answer_is_moved_into_a_read_so_the_server_computes_the_stop():
    decision = _decide(anchor_kind="time", anchor_time="18:30")
    assert len(decision.reads) == 1 and decision.reads[0]["anchor_time"] == "18:30" and decision.reads[0]["from_top_level"]
    decision = _decide(anchor_kind="item", anchor_item="i3", relation="after")
    assert decision.reads[0]["anchor_item"] == "i3" and decision.reads[0]["relation"] == "after"


def test_a_top_level_answer_without_time_words_keeps_its_old_path():
    assert _decide(target_item="i3").reads == []


def test_now_on_another_named_day_counts_from_that_day_not_from_now():
    """재생 v4: 「내일 첫 일정 몇 시야?」를 now · after · tomorrow 로 적으면 지금 다음 일정이 아니라 내일 첫 일정이다."""
    assert _pick(anchor_kind="now", at_day="tomorrow", relation="after") == "남산서울타워"
    assert _pick(anchor_kind="now", at_day="d1", relation="before", now=DAY2.replace(hour=9)) == "광장시장"   # 첫날 마지막 일정
    assert _pick(anchor_kind="now", at_day="today", relation="after") == "토속촌 삼계탕"                     # 오늘은 지금 기준 그대로


def test_a_written_anchor_item_beats_the_previous_kind():
    """재생 v4: 「점심 먹고 나서」를 previous + 점심 별칭으로 적었다 — 적힌 일정이 기준이다."""
    cleaned = time_anchor.clean({"anchor_kind": "previous", "anchor_item": "i3", "relation": "after"}, ["none"], ["i3", "none"])
    assert cleaned["anchor_kind"] == "item"
    assert _pick(anchor_kind="item", anchor_item="i3", anchor=TRIP[2], previous=TRIP[7], relation="after") == "국립현대미술관 서울"



def test_a_model_answer_on_the_anchor_day_beats_a_mistaken_anchor_but_not_another_days_topic():
    """재생 v4: 「저녁 직전에 뭐 해?」에 기준을 미술관으로 잘못 적고 답은 북촌(맞음)을 적었다 → 같은 날 답이면 모델 답.
    실서버 10-14: 「국립현대미술관 바로 앞 일정」에 앞 대화의 롯데월드타워(다음 날)를 이어받으면 → 계산(토속촌)."""
    read = {"anchor_kind": "item", "anchor_item": "i4", "relation": "before", "steps": 1}
    item, basis = time_anchor.resolve(read, items=TRIP, anchor=TRIP[3], target=TRIP[4], now=NOON)
    assert item.title == "북촌한옥마을 산책" and basis["cross_check"]["model"] == str(TRIP[4].item_id)
    item, _ = time_anchor.resolve(read, items=TRIP, anchor=TRIP[3], target=TRIP[7], now=NOON)
    assert item.title == "토속촌 삼계탕"
    item, _ = time_anchor.resolve(read, items=TRIP, anchor=TRIP[3], target=TRIP[3], now=NOON)   # 답 = 기준 → 계산
    assert item.title == "토속촌 삼계탕"


def test_a_model_answer_covering_the_said_time_beats_a_stray_relation():
    item, _ = time_anchor.resolve({"anchor_kind": "time", "anchor_time": "11:30", "at_day": "today", "relation": "after", "steps": 1},
                                  items=TRIP, target=TRIP[1], now=NOON)
    assert item.title == "경복궁 관람"                                   # 11:30 에 걸친 관람 — 「뒤」는 덧붙인 칸
    item, _ = time_anchor.resolve({"anchor_kind": "time", "anchor_time": "15:00", "at_day": "today", "relation": "at", "steps": 1},
                                  items=TRIP, target=TRIP[7], now=NOON)
    assert item.title == "국립현대미술관 서울"                           # 내일 같은 시각 일정은 대조에서도 안 받는다


def test_now_on_another_day_takes_the_model_answer_inside_that_day():
    item, _ = time_anchor.resolve({"anchor_kind": "now", "at_day": "tomorrow", "relation": "after", "steps": 1}, items=TRIP, target=TRIP[7], now=NOON)
    assert item.title == "롯데월드타워 서울스카이"                       # 「내일 롯데월드타워 몇 시야」식 — 그날 안의 모델 답
    item, _ = time_anchor.resolve({"anchor_kind": "now", "relation": "after", "steps": 1}, items=TRIP, target=TRIP[5], now=NOON)
    assert item.title == "토속촌 삼계탕"                                 # 오늘 「다음 일정」은 계산(모델은 지금 시각을 잘 못 센다)
