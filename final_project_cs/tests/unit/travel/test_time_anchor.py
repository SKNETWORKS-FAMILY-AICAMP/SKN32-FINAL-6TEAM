"""고객이 말한 날 · 시각 · 앞뒤로 서버가 답할 일정을 고른다(`time_anchor.py`) — 2026-10-14 x600 재시험의 오답을 그대로 시험으로 옮겼다."""
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


def _pick(now=NOON, target=None, **read):
    item, _basis = time_anchor.resolve({"at_day": "none", "at_time": "", "relation": "at", "steps": 1, **read},
                                       items=TRIP, target=target, now=now)
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


def test_a_model_target_is_kept_and_never_moved_again_by_the_relation():
    """모델은 「바로 앞」을 반영해 고르면서 관계까지 적는다 — 또 옮기면 두 칸을 넘어간다(재생 v1)."""
    assert time_anchor.resolve({"at_time": "", "relation": "before", "steps": 1}, items=TRIP, target=TRIP[2], now=NOON) == (None, None)
    assert time_anchor.resolve({"at_time": "", "relation": "after", "steps": 2}, items=TRIP, target=TRIP[1], now=NOON) == (None, None)


def test_next_and_previous_without_a_target_count_from_now():
    assert _pick(relation="after") == "토속촌 삼계탕"               # 11:10 기준 다음 일정
    assert _pick(relation="after", steps=2) == "국립현대미술관 서울"
    assert _pick(relation="before") == "서울역 도착"               # 지금 전에 끝난 마지막 일정


def test_nothing_named_keeps_the_model_target_and_out_of_range_gives_up():
    assert time_anchor.resolve({"at_day": "none", "at_time": "", "relation": "at", "steps": 1}, items=TRIP, target=TRIP[2], now=NOON) == (None, None)
    assert _pick(at_time="23:00") is None                             # 그날 그 뒤 일정 없음 — 지어내지 않는다
    assert _pick(relation="before", now=DAY1.replace(hour=8)) is None    # 첫 일정 전 — 앞 일정이 없다


def test_bad_fields_are_emptied_instead_of_failing_the_whole_reading():
    got = time_anchor.clean({"at_time": "3pm", "at_day": "friday", "relation": "around", "steps": 9}, ["all", "today", "tomorrow", "d1", "d2", "none"])
    assert (got["at_time"], got["at_day"], got["relation"], got["steps"]) == ("", "none", "at", 1)


def test_the_reply_answers_the_computed_stop_not_the_model_guess():
    read = dict(fact="time", target_item="i8", reference="explicit", origin_item="none", query=None, text="오후 3시에 뭐 해?", advice="",
                at_day="none", at_time="15:00", relation="at", steps=1)
    decision = du.Decision("answer_fact", None, None, "time", None, "", reads=[read])
    result, basis, focus = read_requests.reply(decision, items=TRIP, message="오후 3시에 뭐 해?", selected=None, turns=(), version=1,
                                               now=NOON, context_now=NOON, ttl_seconds=1800, place_source=None)
    assert "국립현대미술관" in result["text"] and "롯데월드타워" not in result["text"], result
    assert basis["questions"][0]["time_anchor"]["time_anchor"] == "resolved"
    assert focus["item_id"] == str(TRIP[3].item_id)


def test_the_answer_schema_requires_the_new_fields():
    stops = [du.Stop(f"i{n}", item) for n, item in enumerate(TRIP, 1)]
    read = du._schema(stops, [])["properties"]["reads"]["items"]
    assert {"at_day", "at_time", "relation", "steps"} <= set(read["required"])
    assert "tomorrow" in read["properties"]["at_day"]["enum"] and "none" in read["properties"]["at_day"]["enum"]


def _decide(**top):
    stops = [du.Stop(f"i{n}", item) for n, item in enumerate(TRIP, 1)]
    answer = {"action": "answer_fact", "target_item": "none", "target_change": "none", "fact": "time", "minutes": 0, "choices": [],
              "reads": [], "social": "", "general_requests": [], "change_scope": "none", "destination_text": "", "condition_text": "",
              "at_day": "none", "at_time": "", "relation": "at", "steps": 1, **top}
    chat = SimpleNamespace(structured=lambda system, user, schema, num_predict=160: answer)
    return du.decide(chat, stops=stops, changes=[], history=[], selected_item_id=None, message="오늘 18시 30분에 뭐 해?", now=NOON)


def test_a_top_level_time_answer_is_moved_into_a_read_so_the_server_computes_the_stop():
    decision = _decide(at_time="18:30")
    assert len(decision.reads) == 1 and decision.reads[0]["at_time"] == "18:30" and decision.reads[0]["from_top_level"]


def test_a_top_level_answer_without_time_words_keeps_its_old_path():
    assert _decide(target_item="i3").reads == []
