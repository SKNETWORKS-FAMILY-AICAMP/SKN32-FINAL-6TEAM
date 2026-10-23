"""이름 찾기 순서 — 공용 별칭이 카카오보다 먼저다(계획 읽기 · 확인 화면 검색). `[2026-10-22 사용자 지시]`

☆x600 서버: 확인 화면에서 「mmca 서울」을 찾으면 우리 목록의 국립현대미술관 서울(활동 별칭 CSV 에 「MMCA 서울」)이 아니라 카카오 결과로만 나왔다.
"""
from copy import deepcopy

from app.domains.travel_ops.components.intake import areas, candidates
from app.domains.travel_ops.components.intake.places import resolve
from app.domains.travel_ops.components.team_hooks import place_aliases as alias_hook

MMCA = {"content_id": "1934593", "title": "국립현대미술관 서울", "latitude": 37.5788, "longitude": 126.9800}


class Kakao:
    def __init__(self, rows):
        self.rows, self.calls, self.misses = rows, [], {}

    def search(self, query, **kwargs):
        self.calls.append(query)
        return deepcopy(self.rows)


class Tour:
    """관광공사 목록 — 이름이 정확히 같을 때만 찾는다."""

    def __init__(self, places):
        self.places, self.misses, self.asked = places, {}, []

    def find(self, name, **_):
        self.asked.append(name)
        for p in self.places:
            if p["title"] == name:
                return {"content_id": p["content_id"], "content_type_id": "14", "matched_title": p["title"],
                        "latitude": p["latitude"], "longitude": p["longitude"], "address": "서울특별시 종로구"}
        return None


def kakao_mmca():
    return Kakao([{"id": "k1", "name": "국립현대미술관 서울", "latitude": 37.5789, "longitude": 126.9801,
                   "category_group": "CT1", "category": "문화시설 > 미술관", "address": "서울 종로구"}])


def test_plan_reading_finds_alias_before_kakao():
    kakao = kakao_mmca()
    found = resolve("MMCA 서울", our_places=[], tour=Tour([MMCA]), kakao=kakao)
    assert found.status == "resolved" and found.method == "tour_api" and found.name == "국립현대미술관 서울"
    assert kakao.calls == []                                  # 별칭이 정했으니 카카오는 부르지 않는다
    assert any(t.startswith("team_alias:MMCA 서울") for t in found.tried)


def test_romanized_alias_is_found_before_kakao_chain_shops():
    """「Gyeongbokgung」 — 카카오 1~5위가 식당 체인 「경복궁 ○○점」이던 이름(2026-09-27 실측). 공용 별칭이 카카오 전에 경복궁으로 정한다."""
    kakao = Kakao([{"id": "c1", "name": "경복궁 관훈점", "latitude": 37.57, "longitude": 126.98, "category_group": "FD6"}])
    found = resolve("Gyeongbokgung", our_places=[], kakao=kakao,
                    tour=Tour([{"content_id": "126508", "title": "경복궁", "latitude": 37.5796, "longitude": 126.9770}]))
    assert found.status == "resolved" and found.name == "경복궁" and kakao.calls == []


def test_plan_reading_exact_name_beats_alias():
    exact = {"place_id": 7, "name": "MMCA 서울", "kind": "activity", "latitude": 37.1, "longitude": 127.1}
    found = resolve("MMCA 서울", our_places=[exact], tour=Tour([MMCA]), kakao=kakao_mmca())
    assert found.method == "places" and found.name == "MMCA 서울"   # 우리 장소 표에 그 이름이 있으면 그곳이 먼저다


def test_customer_alias_still_comes_first():
    found = resolve("MMCA 서울", our_places=[], tour=Tour([MMCA, {**MMCA, "content_id": "130173", "title": "국립현대미술관 덕수궁"}]),
                    kakao=kakao_mmca(), aliases={"mmca서울": "국립현대미술관 덕수궁"})
    assert found.name == "국립현대미술관 덕수궁"               # 그 고객이 고친 말이 공용 별칭보다 앞이다


def test_unregistered_hook_skips_only_the_alias_step(monkeypatch):
    monkeypatch.setattr(alias_hook, "target", lambda conn, name: None)
    kakao = kakao_mmca()
    found = resolve("MMCA 서울", our_places=[], tour=Tour([MMCA]), kakao=kakao)
    assert kakao.calls == ["MMCA 서울"]                       # 별칭이 없으면 전처럼 카카오로 간다(이번 사고의 모양)
    assert not any(t.startswith("team_alias:") for t in found.tried)


def _search(monkeypatch, *, by_name=()):
    item = {"id": "0-0", "title": "경복궁", "kind": "activity", "date": "2030-01-05",
            "starts_at": "12:00", "ends_at": "13:30", "place": None, "parts": {}}
    monkeypatch.setattr(candidates, "_db_places_by_name", lambda *a, **k: [dict(p) for p in by_name])
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k: [])
    monkeypatch.setattr(areas, "areas_for", lambda *a: {})
    monkeypatch.setattr(candidates, "_db_places_by_content_id", lambda conn, tenant, cid, now: [
        candidates._place(MMCA["title"], MMCA["latitude"], MMCA["longitude"], "tour_api", kind="activity", address="서울특별시 종로구 삼청로 30",
                          content_id=cid, content_type_id="14", ref=f"tour:{cid}")] if cid == MMCA["content_id"] else [])
    monkeypatch.setattr(candidates, "assess", lambda *a: {"rows": [], "fits": True, "status": "ok",
                                                           "slack": {"before": None, "after": None}, "estimated": False})
    return item, {"items": [item]}


def test_review_search_finds_our_place_by_alias_before_kakao(monkeypatch):
    item, review = _search(monkeypatch)
    found = candidates.search(object(), tenant_id="test", review=review, item=item, query="mmca 서울", kakao=kakao_mmca())
    first = found["results"][0]["place"]
    assert first["source"] == "tour_api" and first["content_id"] == "1934593" and first["name"] == "국립현대미술관 서울"
    assert [r["place"]["source"] for r in found["results"]] == ["tour_api"]   # 같은 곳의 카카오 결과는 지워진다


def test_review_search_skips_alias_when_our_list_has_the_exact_name(monkeypatch):
    exact = candidates._place("MMCA 서울", 37.2, 127.2, "tour_api", kind="activity", address="서울특별시 중구", content_id="999", ref="tour:999")
    item, review = _search(monkeypatch, by_name=[exact])
    found = candidates.search(object(), tenant_id="test", review=review, item=item, query="MMCA 서울", kakao=Kakao([]))
    assert [r["place"]["content_id"] for r in found["results"]] == ["999"]
