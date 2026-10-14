"""모델이 가리킨 줄 — 한 줄에 장소가 여럿이어도 모두 항목이 되고, 끼니 말은 **자기 장소 몫**에만 붙는다.

테스트 서버 2026-10-14 접수 87858b77 에서 실제로 난 결함:
  「점심은 통인시장 근처에서」가 식사가 아니라 활동이 됐다 · 「서촌 … 저녁 무렵 남산타워」에서 남산타워가 빠지고
  서촌이 저녁 18:00 이 됐다.
"""
from app.domains.travel_ops.components.intake.assemble import collect
from app.domains.travel_ops.components.intake.llm_spans import label_lines
from app.domains.travel_ops.components.intake.rules import meal_mention

LINES = ["아침 먹고 느긋하게 나와서 경복궁부터 한 바퀴 둘러보고",
         "점심은 통인시장 근처에서 대충 해결하고",
         "오후엔 서촌 골목 좀 걷다가 저녁 무렵 남산타워 올라가 볼까 해요"]


class Chat:
    def __init__(self, spans):
        self.spans = spans

    def json(self, system, user):
        return {"spans": self.spans}


# 서버에서 본 그대로 — 장소 넷만 가리켰다(끼니 · 시각 조각은 없다)
PLACES_ONLY = [{"line": 1, "quote": "경복궁", "role": "place"},
               {"line": 2, "quote": "통인시장", "role": "place"},
               {"line": 3, "quote": "서촌", "role": "place"},
               {"line": 3, "quote": "남산타워", "role": "place"}]


def test_every_place_on_a_line_becomes_an_item():
    _, items, _ = label_lines(LINES, [1, 2, 3], Chat(PLACES_ONLY))
    assert [(i.line, i.title.text) for i in items] == [(1, "경복궁"), (2, "통인시장"), (3, "서촌"), (3, "남산타워")]


def test_meal_word_marks_its_own_place_even_when_the_model_skipped_it():
    _, items, _ = label_lines(LINES, [1, 2, 3], Chat(PLACES_ONLY))
    assert {i.title.text: i.meal for i in items} == {"경복궁": None, "통인시장": "lunch", "서촌": None, "남산타워": None}


def test_time_span_attaches_to_the_place_it_precedes():
    spans = PLACES_ONLY + [{"line": 3, "quote": "저녁 무렵", "role": "time"},
                           {"line": 3, "quote": "저녁", "role": "meal"}]
    _, items, _ = label_lines(LINES, [1, 2, 3], Chat(spans))
    assert {i.title.text: i.meal for i in items}["서촌"] is None
    assert {i.title.text: i.meal for i in items}["남산타워"] is None   # 「저녁 무렵」은 때를 말한다 — 끼니가 아니다


def test_two_timed_places_on_one_line_keep_their_own_times():
    lines = ["오후 2시 서촌 걷고 오후 6시 남산타워"]
    spans = [{"line": 1, "quote": "서촌", "role": "place"}, {"line": 1, "quote": "남산타워", "role": "place"},
             {"line": 1, "quote": "오후 2시", "role": "time"}, {"line": 1, "quote": "오후 6시", "role": "time"}]
    _, items, _ = label_lines(lines, [1], Chat(spans))
    assert [(i.title.text, i.start) for i in items] == [("서촌", "14:00"), ("남산타워", "18:00")]
    assert [i.time_claim.value for i in items] == ["14:00", "18:00"]


def test_meal_mention_tells_meal_from_time_of_day_and_after_meal():
    assert meal_mention("점심은 통인시장 근처에서") == ("점심", "lunch", True)
    assert meal_mention("저녁엔 광장시장 가 보고 싶어") == ("저녁", "dinner", True)
    assert meal_mention("저녁 무렵 남산타워") == ("저녁", "dinner", False)      # 때 — 시각만 준다
    assert meal_mention("아침 먹고 느긋하게 나와서 경복궁부터") is None          # 먹은 뒤 — 이 장소의 일이 아니다
    assert meal_mention("아침고요수목원") is None                              # 이름의 일부


def _claims(source_id, index, line, start, end, text):
    return [{"source_id": source_id, "field": f"items[{index}].title", "value": text, "method": "llm_span",
             "evidence": {"source": "text", "line": line, "start": start, "end": end, "text": text},
             "needs_review": True, "note": None},
            {"source_id": source_id, "field": f"items[{index}].date", "value": "2026-10-22", "method": "rule",
             "evidence": {"source": "rule", "line": line}, "needs_review": False, "note": None}]


def test_assemble_times_by_each_places_own_part_of_the_line():
    text = "\n".join(LINES)
    claims = []
    for index, (line, name) in enumerate([(1, "경복궁"), (3, "서촌"), (3, "남산타워")]):
        at = LINES[line - 1].index(name)
        claims += _claims("s1", index, line, at, at + len(name), name)
    got = collect(sources=[{"source_id": "s1", "position": 0, "transcript": text}], claims=claims)
    start = {r["title"]: r["start"] for r in got.rows}
    assert start["경복궁"] != "08:00"          # 「아침 먹고」 — 아침 식사 시각이 아니다
    assert start["남산타워"] == "18:00"        # 「저녁 무렵」은 남산타워 몫
    assert start["서촌"] < "18:00"              # 서촌은 앞 일정 뒤
