"""전부 과거인 계획은 계획 담기 단계에서 끝난다 — 읽기 · 첫 검사 뒤 `review` 로 넘기기 전에 `fatal`(all_dates_in_past).

`[2026-10-26 사용자 지시]` 「전부 과거면 계획 고르는 화면으로 넘어가면 안되고 그 전에 있는 계획담기 페이지의 가드레일에 걸려서 통과 안되게」.
제품 시계(`itinerary_checks.datetime`)만 고정한다. DB · 모델 · 공급자 호출 없음(SQL 은 기록하는 대역이 받는다).
"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake import review as review_module
from app.domains.travel_ops.components.itinerary import itinerary_checks as checks

NOW = datetime(2032, 5, 8, 12, tzinfo=checks.KST)
MESSAGE = "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요"


def _day(offset: int) -> str:
    return (NOW + timedelta(days=offset)).date().isoformat()


@pytest.fixture
def frozen_clock(monkeypatch):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
    monkeypatch.setattr(checks, "datetime", Frozen)


def _run(monkeypatch, payload, *, asking=False):
    """`pipeline.process` 를 실제로 돌린다 — 저장소 · 읽기 단계만 대역. 돌려준 상태 · 실행한 SQL · 이후 단계 호출을 돌려준다."""
    state = {"status": "reading", "stage": "received", "payload": deepcopy(payload)}
    sql_log, later = [], []

    class Conn:
        rowcount = 0
        row = None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def transaction(self):
            return nullcontext(self)

        def cursor(self):
            return self

        def execute(self, sql, params=()):
            sql_log.append((sql, tuple(params)))
            self.row, self.rowcount = None, 0
            if sql.startswith("UPDATE trip_intakes SET stage='reading'"):
                state["stage"] = "reading"
                self.row = (datetime.now(timezone.utc),)
            elif sql.startswith("SELECT customer_id"):
                self.row = ("owner",)
            elif sql.startswith("DELETE FROM intake_claims"):
                pass
            elif sql.startswith("UPDATE trip_intakes SET status='review', stage=%s"):
                # 실제 DB 처럼 읽는 중(status='reading')일 때만 1행 — 확인 화면 전환 0행이면 처리기가 물러난다(전수검사 A17)
                if state["status"] == "reading":
                    self.rowcount = 1
                    state.update(status="review", stage=params[0])
            elif sql.startswith("UPDATE trip_intakes SET stage='review'"):
                state["stage"] = "review"
            elif sql.startswith("UPDATE trip_intakes SET status='fatal'"):
                if state["status"] == "reading" or (state["status"], state["stage"]) == ("review", "checking"):
                    state.update(status="fatal", stage="fatal", fatal=params[:2])
                    self.rowcount = 1
            elif sql.startswith("SELECT status, revision"):
                self.row = (state["status"], 1)
            else:
                raise AssertionError(sql)

        def fetchone(self):
            return self.row

    conn = Conn()
    monkeypatch.setattr(pipeline, "_Heartbeat", lambda *a: nullcontext())
    monkeypatch.setattr(pipeline, "agent_reader_config",
                        lambda *a: dict(mode="off", prefill="off", num_predict=1, chunk_chars=500))
    monkeypatch.setattr(pipeline, "_require_reader_schema", lambda *a: None, raising=False)
    for name in ("_sources", "_claims"):
        monkeypatch.setattr(pipeline, name, lambda *a: [])
    monkeypatch.setattr(pipeline, "_stage", lambda *a: state.update(stage=a[-1]))
    monkeypatch.setattr(pipeline, "with_catalog", lambda *a: None)
    monkeypatch.setattr(pipeline, "_our_places", lambda *a: None)
    monkeypatch.setattr(pipeline, "load_aliases", lambda *a: {})
    monkeypatch.setattr(pipeline, "areas_for", lambda *a: {})
    monkeypatch.setattr(pipeline, "_hold_reading", lambda *a: None)
    monkeypatch.setattr(pipeline, "_has_questions", lambda *a: asking)
    for name in ("_prefill", "_apply_interpretations", "_prepare_alternatives", "_dining_judge"):
        monkeypatch.setattr(pipeline, name, lambda *a, _name=name, **kw: later.append(_name))
    monkeypatch.setattr(pipeline, "rejudge", lambda *a, **kw: later.append("rejudge"))
    monkeypatch.setattr(review_module, "ensure", lambda *a, **kw: deepcopy(state["payload"]))
    monkeypatch.setattr(review_module, "load",
                        lambda *a, **kw: deepcopy(state["payload"]) if state["payload"] is not None else None)
    monkeypatch.setattr(review_module, "intake_state", lambda *a: (state["status"], 1))
    got = pipeline.process(lambda: conn, tenant_id="fixture", intake_id="intake", blobs={}, see=None)
    return got, state, sql_log, later


def _review(*items):
    return {"revision": 1, "items": [{"id": f"0-{n}", **item} for n, item in enumerate(items)],
            "moves": [], "needs": {"items": 0, "moves": 0, "total": 0}, "ready": True}


def test_wholly_past_plan_stops_at_plan_entry_and_never_reaches_review(monkeypatch, frozen_clock):
    got, state, sql_log, later = _run(monkeypatch, _review({"date": _day(-2)}, {"date": _day(-1)}))
    assert got == "fatal"
    assert state["status"] == "fatal" and state["fatal"] == ("all_dates_in_past", MESSAGE)
    assert not any(sql.startswith("UPDATE trip_intakes SET status='review'") for sql, _ in sql_log)
    assert not any(sql.startswith("UPDATE trip_intakes SET stage='review'") for sql, _ in sql_log)
    # 계획 고르기 · 식사 판정 · 대안 준비는 시작하지 않는다
    assert later == []


def test_wholly_past_is_judged_even_when_reading_questions_are_pending(monkeypatch, frozen_clock):
    got, state, _, later = _run(monkeypatch, _review({"date": _day(-3)}), asking=True)
    assert got == "fatal" and state["fatal"][0] == "all_dates_in_past"
    assert later == []


@pytest.mark.parametrize("items", [
    ({"date": _day(-1)}, {"date": _day(0)}),                       # 일부만 과거 + 오늘
    ({"date": _day(-1)}, {"date": _day(3)}),                       # 일부만 과거 + 미래
    ({"date": _day(0)},),                                          # 오늘
    ({"date": _day(-1), "end_date": _day(0)},),                    # 밤을 넘겨 오늘 끝남
    ({"date": _day(-1)}, {"date": None}),                          # 날짜 미확정이 섞임
    ({"date": None},),                                             # 날짜를 모름
], ids=["past+today", "past+future", "today", "overnight-ends-today", "past+unknown", "unknown"])
def test_not_wholly_past_plans_go_on_to_review_as_before(monkeypatch, frozen_clock, items):
    got, state, sql_log, _ = _run(monkeypatch, _review(*items))
    assert got == "review"
    assert state["status"] == "review" and "fatal" not in state
    assert not any(sql.startswith("UPDATE trip_intakes SET status='fatal'") for sql, _ in sql_log)


@pytest.mark.parametrize("payload", [None, _review()], ids=["check-failed", "no-items"])
def test_missing_check_or_no_items_keeps_the_old_path(monkeypatch, frozen_clock, payload):
    got, state, _, _ = _run(monkeypatch, payload)
    assert got == "review" and state["status"] == "review"


def test_gate_follows_the_product_clock_not_a_keyword(monkeypatch):
    """같은 계획도 제품 시계가 그 날짜 이전이면 통과한다 — 판정은 날짜 비교뿐이다(paired)."""
    earlier = NOW - timedelta(days=10)

    class Earlier(datetime):
        @classmethod
        def now(cls, tz=None):
            return earlier.astimezone(tz) if tz else earlier.replace(tzinfo=None)
    monkeypatch.setattr(checks, "datetime", Earlier)
    got, state, _, _ = _run(monkeypatch, _review({"date": _day(-2)}, {"date": _day(-1)}))
    assert got == "review" and state["status"] == "review"


def test_wholly_past_helper_is_the_registration_predicate(frozen_clock):
    past = _review({"date": _day(-2)}, {"date": _day(-1), "end_date": _day(-1)})
    assert review_module.wholly_past(past) is True
    assert review_module.wholly_past(_review({"date": _day(-1), "end_date": _day(0)})) is False
    assert review_module.wholly_past(_review()) is False
    # 검사 줄을 붙이는 기존 판정도 같은 판정 위에 있다
    guarded = review_module.admission_dates(past)
    assert guarded["ready"] is False and all(row["text"] == MESSAGE for it in guarded["items"]
                                             for row in it["rows"] if row["row"] == "date")
    assert review_module.ALL_PAST_MESSAGE == MESSAGE
