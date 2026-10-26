"""긴 계획에서 읽기 에이전트가 빠뜨린 시각 있는 줄을 같은 모델이 한 번 더 읽는다 — 고정 요청(locked)을 놓치지 않게.

근거: x600 74b2b232 실서버(2026-10-26 10:46 KST) 17항목 3일 계획 접수 14282da3 — `reading.agent` 가 로컬 E4B 경로 · items 6
(1일차만) · dropped.locked 0. 나머지 11항목은 「에이전트가 빠뜨린 줄은 규칙 항목」으로 채워져 2일차
「09:30~11:00 국립중앙박물관 관람 (이 일정은 고정해 주세요)」가 locked 없이 등록됐다(검토 `locked:false`).
로컬 실E4B 재현(같은 원문 · num_ctx 12288): raw items 6개, 모두 1일차, locked null — 모델이 1일차 뒤를 통째로 놓쳤다.
아래 첫 답(FIRST)은 그 원출력의 모양을 그대로 옮긴 대역이다(날짜만 시험 날짜). 모델 · DB · 네트워크 없음.
계약: D-025 — 모델이 읽고(고정 여부 포함), 코드는 원문 인용 확인과 줄 번호 덮임 검사만 한다(낱말 규칙 없음).
"""
from __future__ import annotations

from datetime import date

from app.domains.travel_ops.components.intake import agent_read
from app.domains.travel_ops.components.intake.pipeline import read_plan, read_source

TODAY = date(2029, 12, 20)
D1, D2, D3 = "2030-01-02", "2030-01-03", "2030-01-04"
BIG = (f"서울 3일 여행 · 2명\n\n1일차 · {D1}\n09:00~10:30 경복궁 관람\n11:00~12:00 북촌한옥마을 산책\n12:30~13:30 인사동 점심\n"
       f"14:00~15:30 창덕궁 관람\n16:00~17:00 청계천 산책\n18:00~19:00 광장시장 저녁\n\n"
       f"2일차 · {D2}\n09:30~11:00 국립중앙박물관 관람 (이 일정은 고정해 주세요)\n11:30~12:30 이태원 점심\n13:30~14:30 남산공원 산책\n15:30~16:30 N서울타워 관람\n"
       f"18:00~19:00 명동 저녁\n\n3일차 · {D3}\n09:30~11:00 덕수궁 관람\n11:30~12:30 서울시립미술관 관람\n13:00~14:00 남대문시장 점심\n"
       f"15:00~16:30 동대문디자인플라자 관람\n17:30~18:30 낙산공원 산책\n19:00~20:00 대학로 저녁")
LINES = BIG.splitlines()
LOCKED_LINE = next(n for n, line in enumerate(LINES, start=1) if "국립중앙박물관" in line)
GUARD = {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None}


def _item(place, day, when, start, end, kind="activity", locked=None, locked_quote=None):
    return {"place_quote": place, "day": day, "date": when, "date_quote": f"{day}일차", "start": start, "end": end,
            "time_quote": f"{start}~{end}", "kind": kind, "locked": locked, "locked_quote": locked_quote}


def _answer(items):
    return {"guard": GUARD, "pieces": [], "items": items, "moves": [], "conditions": [], "preferences": [], "gaps": [],
            "missing": [], "trip": {"party_size": 2, "days": 3, "nights": None}}


#: 실E4B 첫 답의 모양 — 1일차 여섯 곳만, 고정 null
FIRST = _answer([_item("경복궁", 1, D1, "09:00", "10:30"), _item("북촌한옥마을", 1, D1, "11:00", "12:00"),
                 _item("인사동", 1, D1, "12:30", "13:30", "dining"), _item("창덕궁", 1, D1, "14:00", "15:30"),
                 _item("청계천", 1, D1, "16:00", "17:00"), _item("광장시장", 1, D1, "18:00", "19:00", "dining")])
#: 이어 읽기의 답 — 받은 줄(2 · 3일차)만, 고정 요청은 모델이 인용과 함께 읽는다
SECOND = _answer([_item("국립중앙박물관", 2, D2, "09:30", "11:00", locked=True, locked_quote="이 일정은 고정해 주세요"),
                  _item("이태원", 2, D2, "11:30", "12:30", "dining"), _item("남산공원", 2, D2, "13:30", "14:30"),
                  _item("N서울타워", 2, D2, "15:30", "16:30"), _item("명동", 2, D2, "18:00", "19:00", "dining"),
                  _item("덕수궁", 3, D3, "09:30", "11:00"), _item("서울시립미술관", 3, D3, "11:30", "12:30"),
                  _item("남대문시장", 3, D3, "13:00", "14:00", "dining"), _item("동대문디자인플라자", 3, D3, "15:00", "16:30"),
                  _item("낙산공원", 3, D3, "17:30", "18:30"), _item("대학로", 3, D3, "19:00", "20:00", "dining")])


class Reader:
    model = "e4b-replay"

    def __init__(self, answers):
        self.answers, self.asked = list(answers), []

    def structured(self, system, user, schema, *, num_predict=160):
        self.asked.append(user)
        return self.answers.pop(0) if self.answers else _answer([])


def _expect():
    read = read_plan(BIG)
    timed = {item.title.line for item in read.items if item.title is not None and item.start}
    heads = {claim.span.line for claim in read.claims if claim.field.endswith(".heading")}
    return timed, heads


def test_missed_timed_lines_are_read_again_by_the_model_with_their_day_heading():
    timed, heads = _expect()
    reader = Reader([FIRST, SECOND])
    out = agent_read.read(BIG, LINES, reader, today=TODAY, expected_lines=timed, anchor_lines=heads, missed_line_passes=1)
    assert len(reader.asked) == 2
    sent = reader.asked[1].splitlines()
    assert LINES[LOCKED_LINE - 1] in sent and f"2일차 · {D2}" in sent and f"3일차 · {D3}" in sent
    assert not any(line in sent for line in LINES[3:9])                       # 1일차 줄은 다시 보내지 않는다
    assert sorted(it.title.line for it in out.items) == sorted(timed)          # 17항목 모두 모델 항목
    locked = [it for it in out.items if it.locked is True]
    assert [(it.title.line, it.locked_quote.line) for it in locked] == [(LOCKED_LINE, LOCKED_LINE)]
    assert out.report["missed_line_passes"] == 1 and out.report["missed_lines"] == len(timed) - 6


def test_no_second_call_when_the_model_covered_every_timed_line():
    timed, heads = _expect()
    reader = Reader([_answer(FIRST["items"] + SECOND["items"])])
    out = agent_read.read(BIG, LINES, reader, today=TODAY, expected_lines=timed, anchor_lines=heads, missed_line_passes=1)
    assert len(reader.asked) == 1 and len(out.items) == 17 and "missed_line_passes" not in out.report


def test_passes_zero_keeps_the_single_read():
    timed, heads = _expect()
    reader = Reader([FIRST, SECOND])
    out = agent_read.read(BIG, LINES, reader, today=TODAY, expected_lines=timed, anchor_lines=heads, missed_line_passes=0)
    assert len(reader.asked) == 1 and len(out.items) == 6


def test_a_failed_second_read_keeps_the_first_answer():
    timed, heads = _expect()

    class Broken(Reader):
        def structured(self, system, user, schema, *, num_predict=160):
            if self.asked:
                self.asked.append(user)
                raise ValueError("broken answer")
            return super().structured(system, user, schema, num_predict=num_predict)

    reader = Broken([FIRST])
    out = agent_read.read(BIG, LINES, reader, today=TODAY, expected_lines=timed, anchor_lines=heads, missed_line_passes=1)
    assert len(reader.asked) == 2 and len(out.items) == 6 and out.report["missed_line_error"].startswith("ValueError")


def test_x600_17_item_plan_keeps_the_pin_through_read_source():
    rows = read_source(BIG, today=TODAY, agent=Reader([FIRST, SECOND]), agent_mode="on", agent_missed_line_passes=1)
    titles = {r["field"].split(".")[0]: r["value"] for r in rows if r["field"].endswith(".title")}
    pinned = [r for r in rows if r["field"].endswith(".locked")]
    assert len(titles) == 17
    assert len(pinned) == 1 and pinned[0]["value"] is True and pinned[0]["method"] == "llm_agent"
    assert pinned[0]["evidence"]["line"] == LOCKED_LINE and titles[pinned[0]["field"].split(".")[0]] == "국립중앙박물관"


def test_read_source_default_is_unchanged_without_the_setting():
    rows = read_source(BIG, today=TODAY, agent=Reader([FIRST, SECOND]), agent_mode="on")
    assert not [r for r in rows if r["field"].endswith(".locked")]


def test_the_setting_comes_from_the_guardrails():
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.intake import pipeline

    value = get_guardrails().get("travel.intake_reader.missed_line_passes")
    assert isinstance(value, int) and value >= 1
    assert pipeline.agent_reader_config("demo")["missed_line_passes"] == value


def test_a_reread_middle_day_keeps_its_own_day_number():
    """이어 읽기는 일차 머리줄을 함께 보낸다 — 앞 상태(마지막 3일차)로 일차를 다시 세지 않는다(Codex 리뷰 P1)."""
    text = "1일차\n10:00 경복궁 관람\n2일차\n10:00 덕수궁 관람\n3일차\n10:00 남산공원 산책"
    first = _answer([dict(_item("경복궁", 1, None, "10:00", None), time_quote="10:00"),
                     dict(_item("남산공원", 3, None, "10:00", None), time_quote="10:00")])
    second = _answer([dict(_item("덕수궁", 2, None, "10:00", None), time_quote="10:00")])
    reader = Reader([first, second])
    out = agent_read.read(text, text.splitlines(), reader, today=TODAY, expected_lines={2, 4, 6}, anchor_lines={1, 3, 5},
                          missed_line_passes=1)
    assert reader.asked[1].splitlines() == ["2일차", "10:00 덕수궁 관람"]
    assert {it.title.text: it.day for it in out.items} == {"경복궁": 1, "남산공원": 3, "덕수궁": 2}
