# -*- coding: utf-8 -*-
"""후보 이유 문장을 **모델이 확인된 값으로** 쓴다 — 검사 · 저장 · 실패하면 틀 문장. `[2026-10-07 사용자 결정 — uiux 전달]`

구현 `components/intake/reasons.py` · 저장 057(`candidate_reasons`) · 설정 `travel.candidate_reason`. 모델은 mock 서버(고정 답을 내는 시험용 대역)로 대신한다 — 실제 모델 확인은 따로다.

★지키려는 것
 ①모델은 **사실 목록만** 받는다(후보 이름 · 고른 기준 · 거리 · 영업 · 여유 · 일정의 장소). 모르는 값은 적지 않고 영업시간만 「확인하지 못함」이라고 말한다
 ②사실에 없는 숫자 · 따옴표 이름 · 장소 이름 · 평가 말 · 너무 긴 문장 · 문장이 아닌 답은 **버린다**(틀 문장을 쓰고 저장하지 않는다)
 ③같은 사실이면 한 번만 쓴다(저장된 문장을 쓴다 — 모델을 다시 안 부른다)
 ④모델이 죽거나 시간 상한 안에 못 쓰면 틀 문장으로 나가고, 늦게 끝난 문장은 **저장돼 다음 요청부터** 쓰인다
 ⑤모델이 없거나 설정이 꺼져 있으면 아무것도 안 바뀐다 · 보이는 후보 `visible` 개만 쓴다 · 후보마다 `reason_by` 가 어느 쪽인지 말한다

재현:

    python -m pytest tests/e2e/test_candidate_reasons.py -v
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from app.core.settings import get_guardrails
from app.domains.travel_ops.components.intake import candidates, reasons
from app.infrastructure.db.session import get_connection

from .test_intake_experience_tiers import _alternatives, _palace_review, park_world  # noqa: F401
from .test_intake_review import rv  # noqa: F401
from .test_intake_similar_places import NOW
from .test_trip_api import api  # noqa: F401


class FakeChat:
    """모델 흉내 — 정해 둔 문장을 돌려준다. `calls` 로 몇 번 불렸는지 센다."""
    model = "fake-model"

    def __init__(self, sentence: Any = "경복궁에서 410m라 가까워요.", *, delay: float = 0.0, fail: bool = False):
        self.sentence, self.delay, self.fail, self.calls = sentence, delay, fail, 0

    def structured(self, system, user, schema, *, num_predict=160):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("model down")
        return {"sentence": self.sentence() if callable(self.sentence) else self.sentence}


def _candidate(**over):
    base = {"place": {"name": "북악 둘레길"}, "basis": "similar_experience", "experience": "outdoor_walk", "similarity": None, "distance_m": 410,
            "reference": "경복궁", "rows": [{"row": "hours", "result": "ok", "text": "09:00~18:00 영업"}], "slack": {"before": 5, "after": 25}, "reason": "틀"}
    return {**base, **over}


# ── ① 사실 ────────────────────────────────────────────────────────
def test_the_facts_hold_only_confirmed_values():
    facts = reasons.facts_for(_candidate(), "경복궁")
    assert facts == {"후보 장소": "북악 둘레길", "원래 장소": "경복궁",
                     "고른 기준": "같은 종류는 가까이에 없어 야외에서 걷고 둘러보기을 하는 곳 중 가까운 곳", "거리": "경복궁에서 410m",
                     "영업": "09:00~18:00 영업", "여유": "다음 일정까지 25분"}
    unknown = reasons.facts_for(_candidate(rows=[{"row": "hours", "result": "unknown", "text": "?"}], slack={"before": None, "after": -3}, distance_m=None), "경복궁")
    assert unknown["영업"] == "영업시간은 확인하지 못함" and "여유" not in unknown and "거리" not in unknown          # 늦는 후보에 여유를 쓰지 않고 모르는 값은 안 적는다
    taste = reasons.facts_for(_candidate(basis="taste", taste={"with": ["북촌한옥마을"], "count": 1}), None)
    assert taste["고른 기준"] == "일정에 담은 「북촌한옥마을」과 같은 분류의 곳이에요" and "원래 장소" not in taste


# ── ② 검사 ────────────────────────────────────────────────────────
FACTS = {"후보 장소": "북악 둘레길", "원래 장소": "경복궁", "거리": "경복궁에서 410m", "영업": "09:00~18:00 영업", "여유": "다음 일정까지 25분"}


@pytest.mark.parametrize("sentence, ok", [
    ("경복궁에서 410m 떨어진 곳이고 09:00~18:00에 열어요.", True),
    ("다음 일정까지 25분 여유가 있어요", True),
    ("경복궁에서 410m라 가까워요", True),
    ("경복궁에서 500m 떨어진 곳이에요.", False),                      # 사실에 없는 숫자
    ("분위기 좋은 곳이에요.", False),                                    # 평가 · 분위기
    ("인기 있는 곳이에요.", False),
    ("덕수궁과 가까워요.", False),                                       # 사실에 없는 장소 이름
    ("「덕수궁」 근처예요.", False),                                     # 따옴표로 묶은 이름이 사실에 없다
    ("북악 둘레길 근처의 공원이에요.", False),                           # 「공원」이 사실에 없다
    ("경복궁에서 410m", False),                                          # 문장이 아니다(끝이 요 · 다가 아니다)
    ("가" * 120 + "요.", False),                                         # 너무 길다
    ("", False), (None, False), (123, False),
])
def test_the_guard_keeps_only_sentences_made_of_the_facts(sentence, ok):
    assert (reasons.guard(sentence, FACTS) is not None) is ok, sentence


# ── ③ 저장 · ④ 실패 · 시간 상한 · ⑤ 꺼짐 ─────────────────────────────
def _polish(env, cands, chat, original="경복궁"):
    with get_connection() as conn:
        return reasons.polish(conn, env["tenant"], cands, original, chat)


def test_the_model_sentence_replaces_the_template_and_is_stored_for_the_same_facts(rv):  # noqa: F811
    chat = FakeChat()
    first = [_candidate()]
    assert _polish(rv, first, chat) == {"model": 1, "cached": 0, "template": 0, "pending": 0}
    assert first[0]["reason"] == "경복궁에서 410m라 가까워요." and first[0]["reason_by"] == "model" and chat.calls == 1
    again = [_candidate()]
    assert _polish(rv, again, chat)["cached"] == 1 and chat.calls == 1                      # 같은 사실 — 모델을 다시 안 부른다
    assert again[0]["reason"] == first[0]["reason"]
    other = [_candidate(distance_m=420)]
    _polish(rv, other, FakeChat("경복궁에서 420m 떨어진 곳이에요."))                          # 사실이 바뀌면 새로 쓴다
    assert other[0]["reason"] == "경복궁에서 420m 떨어진 곳이에요."


def test_a_bad_sentence_or_a_dead_model_leaves_the_template_and_stores_nothing(rv):  # noqa: F811
    for chat in (FakeChat("분위기 좋은 곳이에요."), FakeChat(fail=True), FakeChat(None)):
        cands = [_candidate()]
        result = _polish(rv, cands, chat)
        assert cands[0]["reason"] == "틀" and cands[0]["reason_by"] == "template" and result["model"] == 0
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM candidate_reasons WHERE tenant_id=%s", (rv["tenant"],))
        assert cur.fetchone()[0] == 0


def test_only_the_visible_candidates_are_written_and_the_rest_keep_the_template(rv):  # noqa: F811
    chat = FakeChat(lambda: "다음 일정까지 25분 여유가 있어요")
    cands = [_candidate(place={"name": f"곳{n}"}) for n in range(5)]
    _polish(rv, cands, chat)
    assert [c["reason_by"] for c in cands] == ["model", "model", "model", "template", "template"] and chat.calls == 3


def test_a_slow_model_goes_out_as_the_template_and_the_late_sentence_is_stored_for_next_time(rv, monkeypatch):  # noqa: F811
    real = reasons._cfg
    monkeypatch.setattr(reasons, "_cfg", lambda key: 0.05 if key == "budget_seconds" else real(key))
    chat = FakeChat(delay=0.6)
    cands = [_candidate()]
    result = _polish(rv, cands, chat)
    assert result["pending"] == 1 and cands[0]["reason"] == "틀" and cands[0]["reason_by"] == "template"
    time.sleep(1.2)                                                                          # 뒤에서 끝난다
    again = [_candidate()]
    assert _polish(rv, again, chat)["cached"] == 1 and again[0]["reason_by"] == "model" and chat.calls == 1


def test_no_model_or_a_switched_off_setting_changes_nothing(rv, monkeypatch):  # noqa: F811
    cands = [_candidate()]
    assert _polish(rv, cands, None)["template"] == 1 and cands[0]["reason"] == "틀" and cands[0]["reason_by"] == "template"
    real = reasons._cfg
    monkeypatch.setattr(reasons, "_cfg", lambda key: False if key == "enabled" else real(key))
    chat = FakeChat()
    off = [_candidate()]
    _polish(rv, off, chat)
    assert off[0]["reason"] == "틀" and chat.calls == 0


# ── 후보 함수 끝까지 ───────────────────────────────────────────────
def test_alternatives_marks_where_each_reason_came_from(park_world):
    review, item = _palace_review()
    plain = _alternatives(park_world, review, item)
    assert plain["candidates"] and {c["reason_by"] for c in plain["candidates"]} == {"template"}
    chat = FakeChat(lambda: "다음 일정까지 여유가 있어요")
    with get_connection() as conn:
        got = candidates.alternatives(conn, tenant_id=park_world["tenant"], review=review, item=item, kakao=None, use_engine=False, now=NOW, chat=chat)
    assert got["candidates"] and {c["reason_by"] for c in got["candidates"]} <= {"model", "template"}
    assert len(get_guardrails().get("travel.candidate_reason")) >= 5
