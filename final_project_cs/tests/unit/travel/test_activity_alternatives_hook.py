# -*- coding: utf-8 -*-
"""활동 팀이 꽂는 「다른 곳 후보」 자리(`team_hooks.activity_alternatives`) — 미등록 · 답하지 못함은 `None`(모름) 이다. `[2026-10-15 사용자 결정]`

부르는 쪽(확인 화면 `candidates.alternatives`)은 `None` 일 때만 자체 후보 고르기로 간다 — 팀이 「없다」고 답한 빈 목록은 대비책으로 넘어가지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.team_hooks import activity_alternatives as hook
from app.domains.travel_ops.instances.activity import review_alternatives

AT = datetime(2026, 10, 22, 8, 0, tzinfo=timezone(timedelta(hours=9)))


@pytest.fixture(autouse=True)
def clean():
    hook.clear()
    yield
    hook.clear()


def test_without_a_registered_team_the_answer_is_unknown():
    assert hook.is_registered() is False
    assert hook.ranked(None, "t", "126508", AT) is None


def test_an_unknown_origin_or_time_is_unknown_not_an_empty_answer():
    hook.register(rank=lambda *a, **k: {"alternatives": []})
    assert hook.ranked(None, "t", None, AT) is None and hook.ranked(None, "t", "126508", None) is None


def test_a_registered_team_answer_passes_through_even_when_it_is_empty():
    seen = {}

    def rank(conn, tenant, content_id, at, *, exclude_content_ids=(), preference=None):
        seen.update(tenant=tenant, content_id=content_id, exclude=exclude_content_ids)
        return {"alternatives": []}

    hook.register(rank=rank)
    assert hook.ranked(None, "t", "126508", AT, exclude_content_ids={"1", "2"}) == {"alternatives": []}
    assert seen["content_id"] == "126508" and set(seen["exclude"]) == {"1", "2"}


def test_the_activity_adapter_says_unknown_when_the_origin_is_not_in_the_catalog(monkeypatch):
    monkeypatch.setattr(review_alternatives, "find_place_candidates", lambda *a, **k: None)
    assert review_alternatives.rank(object(), "t", "no-such-place", AT) is None


def _row(cid, title, *, x=126.9882, y=37.5512, l3="VE010100", **extra):
    return {"contentid": cid, "title": title, "contenttypeid": "12", "lclsSystm1": "VE", "lclsSystm2": "VE01", "lclsSystm3": l3,
            "lDongSignguCd": "11140", "brand": None, "mapx": str(x), "mapy": str(y), "closed_days": None, "business_hours": None,
            "addr1": "서울 중구", **extra}


def _pool(candidates, aliases=()):
    return {"origin": _row("ORIG", "남산서울타워"), "candidates": candidates, "aliases": list(aliases), "source": "test",
            "confirmed_at": None}



def test_a_duplicate_of_the_origin_under_another_name_is_not_offered(monkeypatch):
    """★`[2026-10-22]` 원래 장소의 다른 이름 등록본(별칭으로 확인된 같은 곳)은 대체 후보가 아니다."""
    pool = _pool([_row("DUP", "시험용별칭전망탑", x=126.9883), _row("OTHER", "남산골한옥마을", x=126.9940)],
                 aliases=[{"alias": "시험용별칭전망탑", "content_id": "ORIG"}])
    monkeypatch.setattr(review_alternatives, "find_place_candidates", lambda *a, **k: pool)
    result = review_alternatives.rank(object(), "t", "ORIG", AT)
    shown = [a["title"] for a in result["alternatives"]]
    assert "시험용별칭전망탑" not in shown and "남산골한옥마을" in shown
    assert result["same_place_removed"] == 1


def test_a_duplicate_of_a_place_already_in_the_itinerary_is_not_offered(monkeypatch):
    pool = _pool([_row("IN_PLAN", "남산골한옥마을", x=126.9940), _row("IN_PLAN_DUP", "남산한옥마을 별칭", x=126.9941),
                  _row("OTHER", "서울로7017", x=126.9700)],
                 aliases=[{"alias": "남산한옥마을 별칭", "content_id": "IN_PLAN"}])
    monkeypatch.setattr(review_alternatives, "find_place_candidates", lambda *a, **k: pool)
    result = review_alternatives.rank(object(), "t", "ORIG", AT, exclude_content_ids=("IN_PLAN",))
    shown = [a["title"] for a in result["alternatives"]]
    assert shown == ["서울로7017"] and result["same_place_removed"] == 2     # 일정에 있는 곳과 그 별칭본 둘 다


def test_a_similar_name_nearby_without_an_alias_stays_but_is_counted(monkeypatch):
    """닮은 이름 · 가까운 거리만으로는 빼지 않는다(남산도서관 · 용산도서관 사례) — 수만 센다."""
    pool = _pool([_row("MAYBE", "남산서울타워전망대", x=126.9890)])
    monkeypatch.setattr(review_alternatives, "find_place_candidates", lambda *a, **k: pool)
    result = review_alternatives.rank(object(), "t", "ORIG", AT)
    assert [a["title"] for a in result["alternatives"]] == ["남산서울타워전망대"]
    assert result["same_place_removed"] == 0 and result["same_place_maybe"] == 1
