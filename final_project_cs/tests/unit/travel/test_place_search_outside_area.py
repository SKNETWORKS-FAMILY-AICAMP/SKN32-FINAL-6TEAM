"""서울 밖 장소를 검색하면 「못 찾음」이 아니라 「서비스 지역 밖(부산 …)」으로 알린다. `[2026-10-27 장소 품질 전수검사]`

☆사용자 시연 관찰(2026-10-27 14:00): 해운대해수욕장 · 감천문화마을 같은 부산 장소를 장소 검색에서 못 찾았다. 실측(로컬 acop_cs 읽기 전용,
  외부 호출 0): 관광공사 목록은 서울 8,060행 · 부산 0행이고 카카오는 서울 사각 + 주소로 거른다 — 부산 이름 30/30 · 시연 8/8 이 빈 결과였고,
  화면에는 「결과 없음」만 남아 이름을 잘못 쓴 것처럼 보였다(서비스 범위는 서울 — D-016, 범위는 넓히지 않는다).
★규칙(Codex 검토 Q1 수정 채택): 서울 결과가 비었고 · 카카오 서울 검색이 **성공**했을 때만 카카오를 **한 번** 서울 사각 없이 부른다.
  정규화 이름이 검색어와 **같고** 주소가 서울 밖인 곳만 근거로 `outside_service_area:<시·도>` 를 단다. 결과는 여전히 비어 있다.
  호출 실패 · 예산 소진은 근거가 아니다(`kakao:<사유>` 만), 이름이 다르면(「해운대해수욕장 주차장」) 달지 않는다.
"""
from __future__ import annotations

import httpx
import pytest

from app.domains.travel_ops.components.intake import areas
from app.domains.travel_ops.components.intake import candidates as c
from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal


# ── 어댑터 ───────────────────────────────────────────────────────
class _Budget:
    def __init__(self, ok=True):
        self.ok, self.reserved = ok, []

    def try_reserve(self, meter):
        self.reserved.append(meter)
        return self.ok


def _adapter(documents, *, status=200, budget=None, calls=None):
    def request(url, params, headers):
        if calls is not None:
            calls.append(dict(params))
        return httpx.Response(status, json={"documents": documents}, request=httpx.Request("GET", url))
    return KakaoLocal(api_key="unit-key", budget=budget or _Budget(), request=request)


BUSAN = {"id": "1", "place_name": "해운대해수욕장", "category_name": "여행 > 관광,명소 > 해수욕장", "category_group_code": "AT4",
         "road_address_name": "", "address_name": "부산 해운대구 우동", "x": "129.1586", "y": "35.1587"}
SEOUL = {"id": "2", "place_name": "해운대해수욕장 팝업", "category_name": "", "category_group_code": "",
         "road_address_name": "서울 성동구 성수동", "address_name": "", "x": "127.05", "y": "37.54"}


def test_outside_seoul_reads_the_whole_country_and_keeps_only_places_outside_seoul():
    calls = []
    kakao = _adapter([BUSAN, SEOUL], calls=calls)
    got = kakao.outside_seoul("해운대해수욕장")
    assert [(g["name"], g["region"], g["address"]) for g in got] == [("해운대해수욕장", "부산", "부산 해운대구 우동")]
    assert "rect" not in calls[0] and "x" not in calls[0] and calls[0]["query"] == "해운대해수욕장"


@pytest.mark.parametrize("budget,status", [(_Budget(ok=False), 200), (None, 500)])
def test_outside_seoul_failure_is_none_not_empty(budget, status):
    kakao = _adapter([BUSAN], status=status, budget=budget)
    assert kakao.outside_seoul("해운대해수욕장") is None


# ── 검색 ─────────────────────────────────────────────────────────
class _Kakao:
    def __init__(self, seoul, outside):
        self.seoul, self.outside, self.calls, self.outside_calls = seoul, outside, [], []

    def search(self, query, **kw):
        self.calls.append(query)
        return self.seoul

    def outside_seoul(self, query, **kw):
        self.outside_calls.append(query)
        return self.outside


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr(c, "_db_places_by_name", lambda *a, **kw: [])
    monkeypatch.setattr(c, "_ledger_places", lambda *a, **kw: [])
    monkeypatch.setattr(c, "_alias_places", lambda *a, **kw: [])
    monkeypatch.setattr(c, "assess", lambda *a, **kw: {"status": "ok", "fits": True})
    monkeypatch.setattr(c, "_present", lambda p, *a, **kw: {"place": p})
    monkeypatch.setattr(areas, "areas_for", lambda *a: areas.AreaIndex())      # 지명 사전 없음(DB 없음)
    item = {"id": "i1", "kind": "activity", "parts": {}, "place": None, "date": "2026-11-03"}
    return {"tenant_id": "demo", "review": {"items": [item]}, "item": item}


HIT = {"name": "해운대해수욕장", "address": "부산 해운대구 우동", "region": "부산"}


@pytest.mark.parametrize("by_relevance", [False, True])
def test_busan_name_is_reported_as_outside_the_service_area(ctx, by_relevance):
    kakao = _Kakao(seoul=[], outside=[HIT])
    out = c.search(None, **ctx, query="해운대해수욕장", kakao=kakao, by_relevance=by_relevance, around_self=by_relevance)
    assert out["results"] == [] and "outside_service_area:부산" in out["notes"]
    assert kakao.outside_calls == ["해운대해수욕장"]                     # 한 요청에 한 번


def test_spaced_query_matches_the_outside_name_after_normalising(ctx):
    kakao = _Kakao(seoul=[], outside=[HIT])
    out = c.search(None, **ctx, query="해운대 해수욕장", kakao=kakao)
    assert "outside_service_area:부산" in out["notes"]


def test_a_different_outside_name_is_not_evidence(ctx):
    kakao = _Kakao(seoul=[], outside=[{"name": "해운대해수욕장 공영주차장", "address": "부산 해운대구 중동", "region": "부산"}])
    out = c.search(None, **ctx, query="해운대해수욕장", kakao=kakao)
    assert not any(n.startswith("outside_service_area") for n in out["notes"])


def test_seoul_results_skip_the_outside_probe(ctx):
    seoul = [{"id": "9", "name": "해운대 횟집", "latitude": 37.5, "longitude": 127.0, "address": "서울 중구", "category_group": "FD6"}]
    kakao = _Kakao(seoul=seoul, outside=[HIT])
    out = c.search(None, **ctx, query="해운대", kakao=kakao)
    assert out["results"] and kakao.outside_calls == []


def test_failed_seoul_search_is_not_followed_by_an_outside_probe(ctx):
    kakao = _Kakao(seoul=None, outside=[HIT])
    kakao.misses = {"timeout": 1}
    out = c.search(None, **ctx, query="해운대해수욕장", kakao=kakao)
    assert "kakao:timeout" in out["notes"] and kakao.outside_calls == []
    assert not any(n.startswith("outside_service_area") for n in out["notes"])


def test_failed_outside_probe_is_reported_as_a_failure_not_as_outside(ctx):
    kakao = _Kakao(seoul=[], outside=None)
    kakao.misses = {"budget_exhausted": 1}
    out = c.search(None, **ctx, query="해운대해수욕장", kakao=kakao)
    assert "kakao:budget_exhausted" in out["notes"]
    assert not any(n.startswith("outside_service_area") for n in out["notes"])


def test_offline_search_without_kakao_does_not_probe(ctx):
    out = c.search(None, **ctx, query="해운대해수욕장", kakao=None)
    assert out["results"] == [] and "kakao:unavailable" in out["notes"]
