"""해석기에 「지금」(한국 시각 · 여행 몇 일차)을 준다 — `decision_unit.now_line`.

전에는 이 줄이 없어 「오늘 15시」에 내일 15:00 일정을 골랐다(x600 서버 웹 채팅 시험 2026-10-13).
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.conversation import decision_unit as du

KST = ZoneInfo("Asia/Seoul")


def _stop(alias, day, hour, title="일정"):
    item = SimpleNamespace(item_id=uuid4(), kind="activity", title=title, place={"name": title}, seq=int(alias[1:]),
                           starts_at=datetime(2026, 10, day, hour, 0, tzinfo=KST), ends_at=None)
    return du.Stop(alias, item)


STOPS = [_stop("i1", 13, 9), _stop("i2", 13, 15), _stop("i3", 14, 15)]


def test_during_the_trip_the_line_names_the_date_and_the_trip_day():
    line = du.now_line(STOPS, datetime(2026, 10, 13, 8, 40, tzinfo=KST))
    assert line == "지금(한국 시각): 2026-10-13(화) 08:40 · 오늘은 여행 1일차"
    assert "2일차" in du.now_line(STOPS, datetime(2026, 10, 14, 1, 0, tzinfo=KST))


def test_before_and_after_the_trip_are_said_so():
    assert "여행 시작 전 — 1일차는 10-13" in du.now_line(STOPS, datetime(2026, 10, 12, 23, 0, tzinfo=KST))
    assert "여행이 끝난 뒤" in du.now_line(STOPS, datetime(2026, 10, 15, 9, 0, tzinfo=KST))


def test_a_utc_moment_is_shown_in_korean_time():
    line = du.now_line(STOPS, datetime(2026, 10, 12, 23, 40, tzinfo=ZoneInfo("UTC")))
    assert line.startswith("지금(한국 시각): 2026-10-13(화) 08:40")


def test_without_a_moment_the_prompt_is_unchanged():
    assert du.now_line(STOPS, None) == ""
    prompt = du._prompt(STOPS, [], [], "none", "다음 일정 뭐야?")
    assert prompt.startswith("일정 목록:")


def test_the_prompt_starts_with_the_now_line_so_the_model_reads_it_first():
    prompt = du._prompt(STOPS, [], [], "none", "오늘 15시에 뭐 해?", datetime(2026, 10, 13, 8, 40, tzinfo=KST))
    assert prompt.splitlines()[0] == "지금(한국 시각): 2026-10-13(화) 08:40 · 오늘은 여행 1일차"
    assert "일정 목록:" in prompt and prompt.rstrip().endswith("고객 문장: 오늘 15시에 뭐 해?")


def test_decide_hands_the_moment_to_the_model():
    seen = []

    class Chat:
        def structured(self, system, user, schema, *, num_predict=160):
            seen.append(user)
            return {"action": "other", "target_item": "none", "target_change": "none", "fact": "none", "minutes": 0,
                    "choices": [], "reads": [], "social": "", "general_requests": []}

    du.decide(Chat(), stops=STOPS, changes=[], history=[], selected_item_id=None, message="지금 뭐 해?",
              now=datetime(2026, 10, 13, 8, 40, tzinfo=KST))
    assert seen and seen[0].startswith("지금(한국 시각): 2026-10-13(화) 08:40")
