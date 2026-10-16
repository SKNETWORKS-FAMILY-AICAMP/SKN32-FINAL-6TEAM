"""접수 읽기 — 끼니 말(아침 · 점심 · 저녁) 없이 「먹는다」고 말한 장소도 식사다. `[2026-10-15]`

세 방식 비교(eval/reports/2026-10-15_intake_meal_kind.md)에서 규칙만으로는 「뭐 좀 먹고」 · 「한잔하고」 · 「맛집」을 0/7 잡았다.
사용자 결정 (가) — LLM 호출을 늘리지 않고 규칙에 「먹는다」 말을 더한다. 시각 있는 줄은 규칙만 읽으므로(모델에 가지 않는다) 규칙이 잡아야 한다.
"""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake.llm_spans import label_lines
from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.rules import eat_mention


@pytest.mark.parametrize("text, place", [
    ("통인시장에서 뭐 좀 먹고 가자", "통인시장"),
    ("을지로 노가리골목에서 한잔하고 싶어요", "을지로 노가리골목"),
    ("익선동에서 밥 먹고 산책할래요", "익선동"),
    ("성수동 맛집 한 군데 들르고", "성수동"),
    ("광장시장 빈대떡 꼭 먹어보고 싶어요", "광장시장"),
    ("연남동에서 커피 한 잔 마시고", "연남동"),
    ("남대문시장에서 갈치조림으로 한 끼 때우고", "남대문시장"),
    ("삼청동에서 수제비 먹기", "삼청동"),
    ("연남동 카페 가기", "연남동"),
    ("망원시장에서 간단히 요기하고", "망원시장"),
])
def test_eating_after_the_place_name_is_a_meal_there(text, place):
    assert eat_mention(text, place_end=text.index(place) + len(place)) is not None


@pytest.mark.parametrize("text, place", [
    ("밥 먹고 나서 창덕궁 후원 관람", "창덕궁"),            # 먹은 뒤 출발 — 장소 앞
    ("아침 먹고 느긋하게 나와서 경복궁부터 한 바퀴 둘러보고", "경복궁"),
    ("오후엔 서촌 가 보고", "서촌"),
    ("연남동 카페거리 구경하고", "연남동"),                # 이름의 일부
    ("커피박물관 관람", "커피박물관"),
    ("국립중앙박물관 관람", "국립중앙박물관"),
    ("저녁에 청계천 야경 보러 가요", "청계천"),
])
def test_no_eating_for_this_place(text, place):
    assert eat_mention(text, place_end=text.index(place) + len(place)) is None


class _Chat:
    def __init__(self, spans):
        self.spans = spans

    def json(self, system, user):
        return {"spans": self.spans}


def test_a_model_read_line_with_eating_words_becomes_a_meal():
    lines = ["통인시장에서 뭐 좀 먹고 가자"]
    _, items, _ = label_lines(lines, [1], _Chat([{"line": 1, "quote": "통인시장", "role": "place"}]))
    assert items[0].meal is not None


def _kinds(text):
    rows = read_source(text, chat=None, today=date(2026, 10, 15), our_places=[])
    titles = {r["field"][6:r["field"].index("]")]: r["value"] for r in rows if r["field"].endswith(".title")}
    kinds = {r["field"][6:r["field"].index("]")]: r["value"] for r in rows if r["field"].endswith(".kind")}
    return {titles[i]: kinds.get(i) for i in titles}


def test_a_timed_line_with_eating_words_becomes_a_meal_without_the_model():
    """시각 있는 줄은 규칙이 읽어 모델에 가지 않는다 — 규칙이 잡아야 한다."""
    kinds = _kinds("2026-10-21\n12:00 통인시장에서 뭐 좀 먹고\n13:00 익선동 맛집\n15:00 국립중앙박물관 관람")
    assert kinds == {"통인시장": "dining", "익선동": "dining", "국립중앙박물관 관람": None}


def test_a_place_quote_carrying_the_eating_word_is_cut_and_becomes_a_meal():
    """모델이 「성수동 맛집」처럼 「먹는다」 말까지 장소로 가리켜도 이름은 「성수동」이고 식사다(실제 접수 모양 측정)."""
    _, items, _ = label_lines(["성수동 맛집 한 군데 들르고"], [1], _Chat([{"line": 1, "quote": "성수동 맛집", "role": "place"}]))
    assert [(i.title.text, bool(i.meal)) for i in items] == [("성수동", True)]


def test_the_models_eat_span_counts_only_after_the_place():
    """「밥 먹고 나서 창덕궁」 — 모델이 「밥 먹고」를 eat 로 짚어도 장소 앞이라 받지 않는다. 장소 뒤의 「칼국수」는 받는다."""
    _, before, _ = label_lines(["밥 먹고 나서 창덕궁 후원 관람"], [1], _Chat([
        {"line": 1, "quote": "창덕궁 후원", "role": "place"}, {"line": 1, "quote": "밥 먹고", "role": "eat"}]))
    _, after, _ = label_lines(["명동교자 가서 칼국수"], [1], _Chat([
        {"line": 1, "quote": "명동교자", "role": "place"}, {"line": 1, "quote": "칼국수", "role": "eat"}]))
    assert [bool(i.meal) for i in before] == [False]
    assert [bool(i.meal) for i in after] == [True]


@pytest.mark.parametrize("line, title", [
    ("16:00 통인시장에서 뭐 좀 먹고", "통인시장"),        # ☆「통인시장에서 뭐 좀」이 이름으로 남아 장소를 못 찾았다(2026-10-15 로컬 접수)
    ("12:00 광장시장에서 빈대떡 먹기", "광장시장"),
    ("12:00 통인시장 가서 뭐 좀 먹고", "통인시장"),
    ("12:00 통인시장에 가서 요기하고", "통인시장"),
    ("12:00 망원시장 들러서 간단히 요기", "망원시장"),
    ("21:00 을지로 노가리골목에서 한잔", "을지로 노가리골목"),
    ("12:00 명동교자 본점에서 칼국수 먹기", "명동교자 본점"),
    ("13:00 익선동 맛집", "익선동"),
])
def test_the_place_name_ends_where_the_place_ends_not_where_eating_starts(line, title):
    assert _kinds("2026-10-31"+chr(10)+line) == {title: "dining"}
