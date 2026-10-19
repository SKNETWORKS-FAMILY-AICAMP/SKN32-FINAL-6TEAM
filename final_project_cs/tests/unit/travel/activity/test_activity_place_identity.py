# -*- coding: utf-8 -*-
"""같은 장소 판정(`place_identity`) — 이름이 달라도 같은 곳이면 대체 후보에서 뺀다. `[2026-10-19]`

★LLM 은 가짜다(실제 호출 없음). 규칙 판정 · 답 검증 · 메모리 기억 · 대체 흐름 연결을 본다.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.instances.activity import place_identity as pi
from app.domains.travel_ops.instances.activity import replacement as replacement_module
from app.domains.travel_ops.instances.activity.replacement import ReplacementMixin

#: 관광공사의 남산서울타워(후보) · 카카오의 N서울타워(일정) — 좌표가 약 60m 어긋난다
NAMSAN_ROW = {"contentid": "126535", "title": "남산서울타워", "mapy": "37.5510545", "mapx": "126.9878829", "lclsSystm3": "VE010200"}
N_TOWER = pi.Spot("N서울타워", 37.5512, 126.9885, None, "관광,명소")
LIBRARY_ROW = {"contentid": "L1", "title": "서울특별시교육청 남산도서관", "mapy": "37.5560", "mapx": "126.9810"}
OTHER_LIBRARY = pi.Spot("서울특별시교육청 용산도서관", 37.5561, 126.9811, None, None)


@pytest.fixture(autouse=True)
def _clean_memory():
    pi.forget_all()
    yield
    pi.forget_all()


# ── 규칙 판정 ────────────────────────────────────────────────────

def test_same_content_id_is_same_even_if_names_differ():
    assert pi.verdict(pi.Spot("아무 이름", None, None, "126535"), pi.spot_of(NAMSAN_ROW)) == "same"


def test_equal_normalized_name_is_same_regardless_of_distance():
    assert pi.verdict(pi.Spot("남산 서울타워", 37.0, 127.0), pi.spot_of(NAMSAN_ROW)) == "same"


def test_similar_name_within_300m_is_ambiguous_not_same():
    assert pi.verdict(N_TOWER, pi.spot_of(NAMSAN_ROW)) == "ambiguous"


def test_a_different_library_next_door_is_also_only_ambiguous_never_auto_same():
    """★이름이 아무리 닮아도(0.92) 규칙이 「같다」고 하지 않는다 — 다른 곳일 수 있어 물어야 한다."""
    assert pi.name_similarity(OTHER_LIBRARY.name, LIBRARY_ROW["title"]) > 0.9
    assert pi.verdict(OTHER_LIBRARY, pi.spot_of(LIBRARY_ROW)) == "ambiguous"


def test_far_away_or_without_coordinates_is_different():
    far = pi.Spot("N서울타워", 37.60, 127.05, None, None)
    assert pi.verdict(far, pi.spot_of(NAMSAN_ROW)) == "different"
    assert pi.verdict(pi.Spot("N서울타워", None, None), pi.spot_of(NAMSAN_ROW)) == "different"


def test_unrelated_names_nearby_are_different():
    assert pi.verdict(pi.Spot("롯데월드 아쿠아리움", 37.5511, 126.9879), pi.spot_of(NAMSAN_ROW)) == "different"


def test_short_names_never_count_as_similar():
    assert pi.name_similarity("남산", "남산서울타워") == 0.0


# ── 후보 가르기 · 기억 ───────────────────────────────────────────

def test_split_removes_rule_same_asks_ambiguous_and_keeps_the_rest():
    same = {"contentid": "9", "title": "N 서울타워", "mapy": "37.5512", "mapx": "126.9885"}
    plain = {"contentid": "7", "title": "경복궁", "mapy": "37.5796", "mapx": "126.977"}
    kept, removed, ask = pi.split([N_TOWER], [NAMSAN_ROW, same, plain])
    assert removed == 1 and [c["contentid"] for c in kept] == ["126535", "7"]
    assert [p.candidate_id for p in ask] == ["126535"] and ask[0].distance_m < pi.NEAR_M


def test_remembered_same_removes_without_asking_and_remembered_different_keeps_without_asking():
    pi.remember(N_TOWER, pi.spot_of(NAMSAN_ROW), True)
    kept, removed, ask = pi.split([N_TOWER], [NAMSAN_ROW])
    assert (kept, removed, ask) == ([], 1, [])
    pi.forget_all()
    pi.remember(OTHER_LIBRARY, pi.spot_of(LIBRARY_ROW), False)
    kept, removed, ask = pi.split([OTHER_LIBRARY], [LIBRARY_ROW])
    assert [c["contentid"] for c in kept] == ["L1"] and removed == 0 and ask == []


def test_memory_key_ignores_order_and_spacing():
    pi.remember(pi.Spot("N서울타워", 0, 0), pi.Spot("남산서울타워", 0, 0), True)
    assert pi.recalled(pi.Spot("남산 서울타워", 0, 0), pi.Spot("n 서울타워", 0, 0)) is True


def test_at_most_max_pairs_are_asked_nearest_first():
    rows = [{"contentid": str(i), "title": f"N서울타워{'가나다라마바사'[i]}", "mapy": str(37.5512 + i * 0.0003), "mapx": "126.9885"}
            for i in range(7)]
    _, _, ask = pi.split([pi.Spot("N서울타워", 37.5512, 126.9885)], rows)
    assert len(ask) <= pi.MAX_PAIRS and [p.distance_m for p in ask] == sorted(p.distance_m for p in ask)


# ── 모델 입력 · 출력 ─────────────────────────────────────────────

def _one_pair():
    return pi.split([N_TOWER], [NAMSAN_ROW])[2]


def test_payload_sends_names_class_and_distance_but_no_coordinates():
    body = pi.payload(_one_pair())
    text = str(body)
    assert body["pairs"][0]["in_plan"]["name"] == "N서울타워" and body["pairs"][0]["candidate"]["name"] == "남산서울타워"
    assert "37.55" not in text and "126.98" not in text


def test_apply_accepts_only_known_ids_with_a_reason_and_remembers():
    pairs = _one_pair()
    out = pi.apply(pairs, {"answers": [{"id": "0", "same": True, "reason": "같은 전망대의 다른 표기"},
                                       {"id": "99", "same": True, "reason": "목록에 없는 id"}]})
    assert out == {"0": True} and pi.recalled(N_TOWER, pi.spot_of(NAMSAN_ROW)) is True


@pytest.mark.parametrize("output", [None, {}, {"answers": "x"}, {"answers": [{"id": "0", "same": "yes", "reason": "r"}]},
                                    {"answers": [{"id": "0", "same": True, "reason": ""}]}])
def test_apply_rejects_unusable_answers_and_remembers_nothing(output):
    assert pi.apply(_one_pair(), output) is None
    assert pi.recalled(N_TOWER, pi.spot_of(NAMSAN_ROW)) is None


# ── 대체 흐름 연결(`ReplacementMixin._drop_same_places`) ─────────

class _LLM:
    def __init__(self, output=None, exc=None):
        self.output, self.exc, self.calls = output, exc, []

    async def judge(self, prompt_key, payload, *, schema, schema_name, web_search=None, instructions=None, run_id=None):
        self.calls.append({"prompt_key": prompt_key, "payload": payload})
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(output=self.output, model="fake")


class _Host(ReplacementMixin):
    def __init__(self, llm=None, budget=None):
        self.judge_llm, self.judge_budget, self.failures = llm, budget, []

    def _record_failure(self, task, code, **kw):
        self.failures.append((code, kw))


def _run(host, mode, rows, spots=(N_TOWER,)):
    task = SimpleNamespace(run_id=uuid4())
    warnings: list[str] = []
    original = replacement_module.kind_mode
    replacement_module.kind_mode = lambda kind, modes=None: mode
    try:
        return host._drop_same_places(task, list(rows), list(spots), warnings), warnings
    finally:
        replacement_module.kind_mode = original


YES = {"answers": [{"id": "0", "same": True, "reason": "같은 전망대"}]}
NO = {"answers": [{"id": "0", "same": False, "reason": "다른 시설"}]}


def test_default_rule_mode_keeps_ambiguous_candidates_and_warns_without_calling_llm():
    llm = _LLM(YES)
    kept, warnings = _run(_Host(llm), "rule", [NAMSAN_ROW])
    assert [c["contentid"] for c in kept] == ["126535"] and llm.calls == []
    assert any("확인하지 못해 그대로 두었다" in w for w in warnings)


def test_llm_mode_removes_the_candidate_the_llm_confirms_is_the_same_place():
    llm = _LLM(YES)
    kept, warnings = _run(_Host(llm), "llm", [NAMSAN_ROW])
    assert kept == [] and len(llm.calls) == 1 and llm.calls[0]["prompt_key"] == "activity_judge.same_place"
    assert any("같다고 확인한 후보 1곳" in w for w in warnings)


def test_llm_mode_keeps_the_candidate_the_llm_says_is_different():
    kept, _ = _run(_Host(_LLM(NO)), "llm", [NAMSAN_ROW])
    assert [c["contentid"] for c in kept] == ["126535"]


def test_second_call_uses_memory_and_does_not_ask_again():
    llm = _LLM(YES)
    host = _Host(llm)
    _run(host, "llm", [NAMSAN_ROW])
    kept, _ = _run(host, "llm", [NAMSAN_ROW])
    assert kept == [] and len(llm.calls) == 1


def test_rule_same_is_removed_without_any_llm_even_in_rule_mode():
    llm = _LLM(YES)
    kept, warnings = _run(_Host(llm), "rule", [{**NAMSAN_ROW, "title": "N 서울 타워"}])
    assert kept == [] and llm.calls == [] and any("같은 장소 1곳" in w for w in warnings)


@pytest.mark.parametrize("llm", [_LLM(exc=RuntimeError("boom")), _LLM({"answers": []}), _LLM(None)])
def test_llm_failure_or_unusable_answer_keeps_the_candidate(llm):
    host = _Host(llm)
    kept, warnings = _run(host, "llm", [NAMSAN_ROW])
    assert [c["contentid"] for c in kept] == ["126535"] and warnings


def test_budget_exhausted_does_not_call_the_llm():
    llm = _LLM(YES)
    kept, warnings = _run(_Host(llm, budget=lambda kind: False), "llm", [NAMSAN_ROW])
    assert [c["contentid"] for c in kept] == ["126535"] and llm.calls == [] and any("예산" in w for w in warnings)


def test_no_in_plan_spots_returns_candidates_untouched():
    kept, warnings = _run(_Host(_LLM(YES)), "llm", [NAMSAN_ROW], spots=())
    assert kept == [NAMSAN_ROW] and warnings == []
