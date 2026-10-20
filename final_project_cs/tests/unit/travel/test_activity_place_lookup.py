# -*- coding: utf-8 -*-
"""장소 이름 찾기 — 카탈로그 → (없으면) 카카오 **존재만** 확인 → Team 이 상태별로 답한다.

DB·네트워크 없이 본다(가짜 DB·가짜 카카오). SQL 자체는 `tests/integration/db/test_place_by_name_db.py`.
★핵심 둘: ① 「없음」과 「못 물어봄」을 가른다 ② 카카오가 준 값은 결과·근거·로그 어디에도 남지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone



from app.domains.travel_ops.instances.activity.db_search.place_by_name import SQL_ALIAS_IDS, SQL_BY_ID
from app.domains.travel_ops.instances.activity.db_search.place_candidates import ALIAS_EXISTS_SQL
from app.domains.travel_ops.instances.activity.place_aliases import key_of
from app.domains.travel_ops.instances.activity.place_lookup import lookup_place
from app.tools.read_tools import ReadToolbox


WHEN = datetime(2026, 10, 3, 15, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, rows, aliases=None):
        # `aliases` — {정규화한 별칭: content_id}. `None` 이면 별칭 표가 아직 없다(마이그레이션 306 전)
        self.rows, self.aliases, self.sql, self.params = rows, aliases, None, None

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params

    def fetchone(self):
        rows = self.fetchall()
        return rows[0] if rows else None

    def fetchall(self):
        if self.sql == ALIAS_EXISTS_SQL:
            return [(self.aliases is not None,)]
        if self.sql == SQL_ALIAS_IDS:
            return [(cid,) for key, cid in (self.aliases or {}).items() if key == self.params[0]]
        if self.sql == SQL_BY_ID:
            return [r for r in self.rows if r[0] == self.params[1]]
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn(_Cursor):
    def cursor(self):
        return self


def _db(rows, aliases=None):
    # (content_id, content_type_id, title, latitude, longitude, source)
    return lambda: _Conn([tuple(r) for r in rows], aliases)


GYEONGBOK = ("126508", "12", "경복궁", 37.576, 126.977, "tour_api")


class _Kakao:
    def __init__(self, hits, misses=None):
        self.hits, self.misses, self.calls = hits, misses or {}, []

    def search(self, query, **kw):
        self.calls.append(query)
        return self.hits


KAKAO_HIT = [{"id": "999", "name": "새로생긴전시관", "category": "문화", "category_group": "CT1",
              "address": "서울 종로구 비밀주소 1", "latitude": 37.5, "longitude": 127.0}]


# ── lookup_place ─────────────────────────────────────────────────

def test_catalog_hit_never_calls_kakao():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([GYEONGBOK]), "t", "경복궁", kakao)
    assert out["status"] == "found" and out["content_id"] == "126508" and kakao.calls == []


def test_two_catalog_hits_are_ambiguous_with_candidate_names():
    rows = [("1", "12", "서울 숲", 37.5, 127.0, "tour_api"), ("2", "12", "서울  숲", 37.6, 127.1, "tour_api")]
    out = lookup_place(_db(rows), "t", "서울숲", _Kakao(None))
    assert out["status"] == "ambiguous" and out["match_count"] == 2
    assert [c["content_id"] for c in out["candidates"]] == ["1", "2"]


def test_exact_title_beats_looser_matches():
    rows = [("1", "12", "경복궁", 37.5, 127.0, "tour_api"), ("2", "12", "경복궁 야간개장", 37.5, 127.0, "tour_api")]
    assert lookup_place(_db(rows), "t", "경복궁", None)["content_id"] == "1"


def test_missing_in_catalog_but_kakao_knows_it_is_exists_unregistered():
    out = lookup_place(_db([]), "t", "새로생긴전시관", _Kakao(KAKAO_HIT))
    assert out == {"status": "exists_unregistered", "via": "kakao"}


def test_kakao_values_never_appear_in_the_result():
    out = lookup_place(_db([]), "t", "새로생긴전시관", _Kakao(KAKAO_HIT))
    raw = json.dumps(out, ensure_ascii=False)
    for leaked in ("비밀주소", "37.5", "127.0", "999", "CT1"):
        assert leaked not in raw


def test_kakao_with_no_matching_name_is_not_found():
    """카카오 1위가 아무 가게여도 「있다」고 하지 않는다."""
    out = lookup_place(_db([]), "t", "듣도보도못한곳", _Kakao(KAKAO_HIT))
    assert out["status"] == "not_found"


def test_kakao_empty_result_is_not_found():
    assert lookup_place(_db([]), "t", "없는곳", _Kakao([]))["status"] == "not_found"


def test_kakao_failure_is_unknown_not_not_found():
    out = lookup_place(_db([]), "t", "없는곳", _Kakao(None, misses={"budget_exhausted": 3}))
    assert out["status"] == "unknown" and out["reason"] == "kakao_blocked" and out["detail"] == "budget_exhausted"


def test_no_kakao_key_is_unknown_not_not_found():
    out = lookup_place(_db([]), "t", "없는곳", None)
    assert out["status"] == "unknown" and out["reason"] == "kakao_unavailable"


def test_too_short_name_is_not_searched_at_all():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([GYEONGBOK]), "t", "경", kakao)
    assert out["status"] == "not_found" and kakao.calls == []


def test_toolbox_tool_returns_none_for_blank_name():
    class Scope:
        tenant_id = "t"

    assert ReadToolbox(_db([])).place_lookup(Scope(), name="  ") is None
    assert "read.place_lookup" in ReadToolbox(_db([]))._travel_tools()


# ── fuzzy(어순 · 오타) — 기본은 꺼짐 `[2026-10-19]` ─────────────────

NAMSAN = ("126535", "12", "남산서울타워", 37.551, 126.988, "tour_api")
OLIVE = ("2", "38", "올리브영 명동 타운", 37.564, 126.985, "tour_api")


def test_fuzzy_is_off_by_default_and_typo_is_not_found():
    out = lookup_place(_db([NAMSAN]), "t", "남산서울타우", _Kakao([]))
    assert out["status"] == "not_found"


def test_fuzzy_finds_a_typo_and_asks_for_review_without_calling_kakao():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([NAMSAN, GYEONGBOK]), "t", "남산서울타우", kakao, fuzzy=True)
    assert out["status"] == "found" and out["content_id"] == "126535"
    assert out["match"] == "typo" and out["needs_review"] is True and "오타" in out["note"]
    assert kakao.calls == []


def test_fuzzy_finds_swapped_word_order():
    out = lookup_place(_db([OLIVE, NAMSAN]), "t", "명동 올리브영 타운", _Kakao([]), fuzzy=True)
    assert out["status"] == "found" and out["content_id"] == "2" and out["match"] == "word_order"


def test_fuzzy_does_not_override_an_exact_match():
    out = lookup_place(_db([NAMSAN]), "t", "남산서울타워", _Kakao([]), fuzzy=True)
    assert out["status"] == "found" and "match" not in out and "needs_review" not in out


def test_fuzzy_with_an_unrelated_name_still_falls_through_to_kakao():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([NAMSAN]), "t", "새로생긴전시관", kakao, fuzzy=True)
    assert out["status"] == "exists_unregistered" and kakao.calls == ["새로생긴전시관"]


def test_fuzzy_does_not_pick_between_two_equally_close_names():
    rows = [("1", "12", "경복굴", 37.5, 127.0, "tour_api"), ("2", "12", "경복군", 37.6, 127.1, "tour_api")]
    out = lookup_place(_db(rows), "t", "경복궁", _Kakao([]), fuzzy=True)
    assert out["status"] == "not_found"          # 비율이 같은 서로 다른 이름 둘 — 고르지 않는다


# ── 별칭(마이그레이션 306) `[2026-10-19]` ─────────────────────────

def test_alias_finds_the_canonical_place_without_calling_kakao():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([NAMSAN], {key_of("남산타워"): "126535", key_of("N서울타워"): "126535"}), "t", "N 서울 타워", kakao)
    assert out["status"] == "found" and out["content_id"] == "126535" and out["match"] == "alias" and kakao.calls == []


def test_name_that_is_not_an_alias_still_falls_through_to_kakao():
    kakao = _Kakao(KAKAO_HIT)
    out = lookup_place(_db([NAMSAN], {key_of("남산타워"): "126535"}), "t", "새로생긴전시관", kakao)
    assert out["status"] == "exists_unregistered" and kakao.calls == ["새로생긴전시관"]


def test_missing_alias_table_is_not_an_error_and_the_seed_file_still_applies():
    """★DB 표가 없어도(마이그레이션 306 전 · 적재 전) 배포에 실린 시드 파일의 별칭은 늘 적용된다."""
    assert lookup_place(_db([NAMSAN], None), "t", "남산타워", _Kakao([]))["content_id"] == "126535"
    assert lookup_place(_db([NAMSAN], None), "t", "별칭도 아닌 이름", _Kakao([]))["status"] == "not_found"


def test_database_alias_that_contradicts_the_seed_is_ambiguous_and_not_used():
    out = lookup_place(_db([NAMSAN], {key_of("남산타워"): "999"}), "t", "남산타워", _Kakao([]))
    assert out["status"] == "not_found"


def test_alias_pointing_at_a_place_not_in_the_ledger_is_not_found():
    out = lookup_place(_db([GYEONGBOK], {key_of("남산타워"): "126535"}), "t", "남산타워", _Kakao([]))
    assert out["status"] == "not_found"
