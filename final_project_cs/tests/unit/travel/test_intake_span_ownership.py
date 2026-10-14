"""장소별 원문 단서의 소유권 — 2026-10-14 접수 읽기 결함 회귀.

모델 응답만 고정하고 실제 label_lines와 meal_mention을 실행한다.
외부 모델·API·DB를 호출하지 않는다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake.llm_spans import label_lines
from app.domains.travel_ops.components.intake.rules import meal_mention


class Chat:
    def __init__(self, spans):
        self.spans = spans

    def json(self, system, user):
        return {"spans": self.spans}


def test_the_next_places_lunch_does_not_make_seochon_a_meal():
    text = "서촌 걷다가 점심은 통인시장 근처에서 해결하고 싶어요"
    spans = [{"line": 1, "quote": "서촌", "role": "place"},
             {"line": 1, "quote": "통인시장", "role": "place"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.meal) for item in items] == [
        ("서촌", None), ("통인시장", "lunch")]


@pytest.mark.parametrize("model_marks_meal", [False, True])
def test_a_meal_at_the_market_survives_the_move_to_gyeongbokgung(model_marks_meal):
    text = "광장시장에서 점심 먹고 경복궁 가자"
    spans = [{"line": 1, "quote": "광장시장", "role": "place"},
             {"line": 1, "quote": "경복궁", "role": "place"}]
    if model_marks_meal:
        spans.append({"line": 1, "quote": "점심", "role": "meal"})

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.meal) for item in items] == [
        ("광장시장", "lunch"), ("경복궁", None)]


def test_two_visits_to_the_same_place_keep_both_original_occurrences():
    text = "아침에 경복궁 둘러보고 저녁엔 경복궁 야경 보고 싶어요"
    spans = [{"line": 1, "quote": "경복궁", "role": "place"},
             {"line": 1, "quote": "경복궁", "role": "place"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.title.start, item.title.end) for item in items] == [
        ("경복궁", 4, 7), ("경복궁", 17, 20)]


def test_duplicate_model_labels_cannot_invent_a_second_visit():
    text = "경복궁 둘러보고 싶어요"
    spans = [{"line": 1, "quote": "경복궁", "role": "place"},
             {"line": 1, "quote": "경복궁", "role": "place"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [item.title.text for item in items] == ["경복궁"]


def test_now_after_seochon_belongs_to_seochon_rather_than_namsan_tower():
    text = "서촌은 지금 방문하고 저녁 무렵 남산타워 올라가자"
    spans = [{"line": 1, "quote": "서촌", "role": "place"},
             {"line": 1, "quote": "남산타워", "role": "place"},
             {"line": 1, "quote": "지금", "role": "time"}]
    anchor = datetime(2026, 10, 14, 13, 7, tzinfo=ZoneInfo("Asia/Seoul"))

    _, items, _ = label_lines([text], [1], Chat(spans), now=anchor)

    assert [(item.title.text, item.start, item.date) for item in items] == [
        ("서촌", "13:07", "2026-10-14"), ("남산타워", None, None)]
    assert [(item.title.text, item.time_claim.value if item.time_claim else None)
            for item in items] == [("서촌", "13:07"), ("남산타워", None)]


def test_times_before_two_places_keep_their_respective_values():
    text = "오후 2시 서촌 걷고 오후 6시 남산타워"
    spans = [{"line": 1, "quote": "서촌", "role": "place"},
             {"line": 1, "quote": "남산타워", "role": "place"},
             {"line": 1, "quote": "오후 2시", "role": "time"},
             {"line": 1, "quote": "오후 6시", "role": "time"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.start, item.time_claim.value) for item in items] == [
        ("서촌", "14:00", "14:00"), ("남산타워", "18:00", "18:00")]


def test_breakfast_finished_before_leaving_does_not_become_gyeongbokgungs_meal():
    text = "아침 먹고 느긋하게 나와서 경복궁부터 한 바퀴 둘러보고"
    spans = [{"line": 1, "quote": "경복궁", "role": "place"},
             {"line": 1, "quote": "아침", "role": "meal"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.meal, item.start) for item in items] == [
        ("경복궁", None, None)]
    assert meal_mention(text) is None


def test_model_marking_the_meal_word_as_a_time_keeps_the_market_a_visit():
    text = "저녁엔 광장시장 가 보고 싶어"
    marked_time = [{"line": 1, "quote": "저녁", "role": "time"}, {"line": 1, "quote": "광장시장", "role": "place"}]
    unmarked = [{"line": 1, "quote": "광장시장", "role": "place"}]

    _, as_time, _ = label_lines([text], [1], Chat(marked_time))
    _, by_rule, _ = label_lines([text], [1], Chat(unmarked))

    assert [(i.title.text, i.meal) for i in as_time] == [("광장시장", None)]
    assert [(i.title.text, i.meal) for i in by_rule] == [("광장시장", "dinner")]


def test_evening_as_a_time_of_day_does_not_make_namsan_tower_a_meal():
    text = "저녁 무렵 남산타워 올라가자"
    spans = [{"line": 1, "quote": "남산타워", "role": "place"},
             {"line": 1, "quote": "저녁", "role": "meal"},
             {"line": 1, "quote": "저녁 무렵", "role": "time"}]

    _, items, _ = label_lines([text], [1], Chat(spans))

    assert [(item.title.text, item.meal) for item in items] == [("남산타워", None)]
    assert meal_mention(text) == ("저녁", "dinner", False)
