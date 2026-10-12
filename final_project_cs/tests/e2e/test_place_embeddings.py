# -*- coding: utf-8 -*-
"""장소 임베딩 · 분류 채우기 · 취향 순서 — 모델은 mock 서버(키워드로 벡터를 만드는 시험용 대역)로 대신한다. `[2026-10-07 사용자 결정 — uiux 전달]`

구현 `components/intake/embeddings.py` · `class_fill.py` · `taste.py` · 표 058(`place_embeddings`). 실제 임베딩 모델(bge-m3, Ollama)은 이 PC 에 없어 **실모델 확인은 따로**다.

★지키려는 것
 ①채우기는 기본이 세기만(dry-run)이고, 쇼핑 · 음식 가지는 만들지 않으며, 이미 만든 것은 건너뛰고 이름이 바뀌면 다시 만든다
 ②분류 짐작은 이름 일치가 먼저이고, 투표가 갈리거나 닮은 정도가 낮으면 모른다고 둔다. 목록 분류가 있는 행은 건드리지 않고, 짐작한 값은 `estimated` 로 적는다
 ③저장된 짐작 분류는 후보 고르기가 읽되 이유 문장에 「관광공사 분류」라고 쓰지 않는다
 ④취향 후보는 저장된 임베딩이 후보 전부와 일정 장소에 있을 때만 평균 벡터와 가까운 순으로 줄 세우고(`embedding`), 모자라면 규칙 순서(`count`)로 정직하게 적는다

재현:

    python -m pytest tests/e2e/test_place_embeddings.py -v
"""
from __future__ import annotations

import hashlib


from app.domains.travel_ops.components.intake import candidates, class_fill, embeddings
from app.infrastructure.db.session import get_connection

from .test_intake_experience_tiers import _alternatives, _palace_review, _plan_review  # noqa: F401
from .test_intake_review import rv  # noqa: F401
from .test_intake_similar_places import PALACE, _row
from .test_trip_api import api  # noqa: F401

AXES = {"공원": 0, "궁": 1, "시장": 2, "한옥": 3, "전시": 4}


def fake_embed(texts):
    """키워드마다 한 축을 세우고 글마다 아주 작은 잡음을 더한다 — 같은 키워드면 가깝고 다르면 멀다. 호출 횟수를 센다."""
    fake_embed.calls += 1
    out = []
    for text in texts:
        vector = [0.0] * embeddings.DIM
        axis = next((n for word, n in AXES.items() if word in text), 5)
        vector[axis] = 1.0
        vector[100 + int(hashlib.sha256(text.encode()).hexdigest(), 16) % 800] = 0.05
        out.append(vector)
    return out


fake_embed.calls = 0


def _tenants(env):
    return [env["tenant"]]


def _seed(rv):  # noqa: F811
    _row(rv, "990001", "12", "북악 둘레공원", 37.5800, 126.9800, "VE", "VE03", "VE030100")
    _row(rv, "990002", "12", "서울숲 공원", 37.5810, 126.9810, "VE", "VE03", "VE030100")
    _row(rv, "990003", "12", "창덕궁", 37.5794, 126.9910, "HS", "HS01", "HS010100")
    _row(rv, "990004", "14", "시립 전시관", 37.5820, 126.9820, "VE", "VE07", "VE070100")
    _row(rv, "990005", "38", "우정약국 종로", 37.5797, 126.9771, "SH", "SH04", "SH040100")        # 쇼핑 — 임베딩을 안 만든다


# ── ① 채우기 ──────────────────────────────────────────────────────
def test_filling_counts_first_skips_shopping_and_is_idempotent(rv):  # noqa: F811
    _seed(rv)
    with get_connection() as conn:
        assert embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=True) == {"missing": 4, "written": 0}       # 세기만 — 쇼핑 1곳은 대상이 아니다
        assert embeddings.vectors_of(conn, _tenants(rv), ["990001"]) == {}
        assert embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False) == {"missing": 4, "written": 4}
        assert embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False) == {"missing": 0, "written": 0}      # 이미 만든 것은 건너뛴다
        vector = embeddings.vectors_of(conn, _tenants(rv), ["990001"])["990001"]
        assert len(vector) == embeddings.DIM and vector[0] == 1.0                                                          # 글 리터럴로 쓰고 읽어도 같은 값
        with conn.cursor() as cur:                                                                                        # 이름이 바뀌면 다시 만든다
            cur.execute("UPDATE place_catalog SET title='북악 둘레 큰공원' WHERE tenant_id=%s AND content_id='990001'", (rv["tenant"],))
        assert embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=True)["missing"] == 1


def test_the_text_is_the_name_and_the_type_label_only():
    assert embeddings.catalog_text("북촌한옥마을", "관광지") == "북촌한옥마을 (관광지)"
    assert embeddings.catalog_text(" 경복궁 ", None) == "경복궁"


# ── ② 분류 짐작 ───────────────────────────────────────────────────
def test_the_vote_names_the_class_only_when_the_neighbours_agree(rv):  # noqa: F811
    _seed(rv)
    with get_connection() as conn:
        embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False)
        near_park = fake_embed(["연못 공원"])[0]                       # 공원 축 — 공원 둘이 닮았지만 나머지 이웃은 멀다
        guess = embeddings.estimate_class(conn, _tenants(rv), near_park)
        assert guess is None                                           # 7곳 중 닮은 공원은 2곳뿐 — 표가 갈려 모른다(지어내지 않는다)
        for n in range(8):                                             # 공원이 많아지면 같은 투표가 한쪽으로 모인다
            _row(rv, f"99100{n}", "12", f"테스트 공원 {n}", 37.58 + n / 1000, 126.98, "VE", "VE03", "VE030100")
        embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False)
        guess = embeddings.estimate_class(conn, _tenants(rv), near_park)
        assert guess and guess["lcls2"] == "VE03" and guess["lcls1"] == "VE" and guess["share"] >= 0.6 and guess["similarity"] >= 0.55


def test_filling_classes_prefers_the_name_match_then_estimates_then_admits_unknown_and_never_touches_typed_rows(rv):  # noqa: F811
    _seed(rv)
    for n in range(8):
        _row(rv, f"99100{n}", "12", f"테스트 공원 {n}", 37.58 + n / 1000, 126.98, "VE", "VE03", "VE030100")
    tenant = rv["tenant"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name, typed in (("창덕궁", None), ("이름만 공원", None), ("정체불명 가게", None), ("분류가 있는 곳", "12")):
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) VALUES (%s,%s,'activity',37.58,126.98,'seed',%s::jsonb)",
                        (tenant, name, '{"source_content_type_id": "%s"}' % typed if typed else "{}"))
    with get_connection() as conn:
        embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False)
        dry = class_fill.fill_places(conn, _tenants(rv), fake_embed, dry_run=True)
        assert (dry["targets"], dry["name_match"], dry["estimated"], dry["unknown"], dry["written"]) == (3, 1, 1, 1, 0), dry        # 분류가 있는 곳은 대상이 아니다
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM places WHERE tenant_id=%s AND attributes ? 'inferred_class'", (tenant,))
            assert cur.fetchone()[0] == 0                                                                                       # dry-run 은 아무것도 안 썼다
        done = class_fill.fill_places(conn, _tenants(rv), fake_embed, dry_run=False)
        assert done["written"] == 2
        with conn.cursor() as cur:
            cur.execute("SELECT name, attributes->'inferred_class' FROM places WHERE tenant_id=%s AND attributes ? 'inferred_class' ORDER BY name", (tenant,))
            saved = dict(cur.fetchall())
        assert saved["창덕궁"]["grade"] == "name_match" and saved["창덕궁"]["lcls"] == ["HS", "HS01", "HS010100"]
        assert saved["이름만 공원"]["grade"] == "estimated" and saved["이름만 공원"]["lcls"][:2] == ["VE", "VE03"] and saved["이름만 공원"]["method"] == "embedding_knn"
        assert "정체불명 가게" not in saved and "분류가 있는 곳" not in saved
        assert class_fill.fill_places(conn, _tenants(rv), fake_embed, dry_run=False)["targets"] == 1                            # 채운 곳은 다시 안 본다(모른 곳만 남는다)


def test_without_a_model_only_name_matches_are_made_and_the_rest_are_counted_unmatched(rv):  # noqa: F811
    _seed(rv)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name in ("창덕궁", "모르는 곳"):
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) VALUES (%s,%s,'activity',37.58,126.98,'seed','{}'::jsonb)", (rv["tenant"], name))
    with get_connection() as conn:
        got = class_fill.fill_places(conn, _tenants(rv), None, dry_run=True)
    assert (got["name_match"], got["unmatched"], got["estimated"]) == (1, 1, 0)


# ── ③ 저장된 짐작을 후보 고르기가 쓴다 ────────────────────────────────
def test_a_stored_estimated_class_drives_the_same_kind_tier_without_claiming_the_official_class(rv):  # noqa: F811
    _row(rv, "993001", "12", "고궁 하나", 37.5796, 126.9770, "HS", "HS01", "HS010100")
    _row(rv, "993002", "12", "고궁 둘", 37.5800, 126.9780, "HS", "HS01", "HS010100")
    tenant = rv["tenant"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) VALUES (%s,'이름이 없는 목록 밖 궁','activity',%s,%s,'seed',%s::jsonb) RETURNING place_id",
                    (tenant, PALACE[0], PALACE[1], '{"inferred_class": {"lcls": ["HS", "HS01", null], "grade": "estimated", "method": "embedding_knn"}}'))
        place_id = cur.fetchone()[0]
    place = {"name": "이름이 없는 목록 밖 궁", "latitude": PALACE[0], "longitude": PALACE[1], "kind": "activity", "source": "places", "content_id": None,
             "content_type_id": None, "ref": f"place:{place_id}"}
    review, item = _palace_review()
    item = {**item, "title": place["name"], "place": place}
    review = {"items": [item]}
    with get_connection() as conn:
        cls = candidates._original_class(conn, tenant, place)
    assert cls["lcls"] == ["HS", "HS01", None] and cls["grade"] == "estimated" and cls["by"] == "stored"
    got = _alternatives(rv, review, item)
    assert [c["place"]["name"] for c in got["candidates"]][:2] == ["고궁 하나", "고궁 둘"] and {c["basis"] for c in got["candidates"]} == {"same_kind"}
    assert all(c["class_grade"] == "estimated" and "(관광공사 분류)" not in c["reason"] and "분류를 추정했어요" in c["reason"] for c in got["candidates"]), got["candidates"][0]["reason"]


# ── ④ 취향 후보의 순서 ─────────────────────────────────────────────
def _taste_world(rv):  # noqa: F811
    """일정에 북촌한옥마을(한옥 축)이 있고, 취향 갈래(VE02)의 후보 둘 — 가까운 쪽은 시장 축, 먼 쪽은 한옥 축이다(임베딩 순서는 가까운 순과 거꾸로)."""
    _row(rv, "960001", "12", "경복궁", *PALACE, "HS", "HS01", "HS010100")
    _row(rv, "980001", "12", "북촌한옥마을", 37.5820, 126.9830, "VE", "VE02", "VE020100")
    _row(rv, "980002", "12", "가까운 시장골목", 37.5797, 126.9772, "VE", "VE02", "VE020200")
    _row(rv, "980003", "12", "먼 한옥길", 37.5900, 126.9700, "VE", "VE02", "VE020300")
    return _plan_review(("beachon", "북촌한옥마을", "980001", "14:00", 37.5820, 126.9830))


def test_the_taste_order_follows_the_embedding_only_when_every_vector_is_there(rv):  # noqa: F811
    review, item = _taste_world(rv)
    plain = _alternatives(rv, review, item)
    assert [c["place"]["name"] for c in plain["candidates"]] == ["가까운 시장골목", "먼 한옥길"]                  # 임베딩이 없으면 규칙(가까운 순)
    assert {c["taste"]["ranked_by"] for c in plain["candidates"]} == {"count"}
    with get_connection() as conn:
        embeddings.fill_catalog(conn, _tenants(rv), fake_embed, dry_run=False)
    ranked = _alternatives(rv, review, item)
    assert [c["place"]["name"] for c in ranked["candidates"]][0] == "먼 한옥길"                                  # 일정의 한옥 축과 가까운 쪽이 앞
    assert {c["taste"]["ranked_by"] for c in ranked["candidates"]} == {"embedding"} and ranked["candidates"][0]["taste"]["score"] > ranked["candidates"][1]["taste"]["score"]
    with get_connection() as conn, conn.cursor() as cur:                                                         # 후보 하나의 벡터가 없으면 섞지 않고 규칙 순서
        cur.execute("DELETE FROM place_embeddings WHERE tenant_id=%s AND content_id='980003'", (rv["tenant"],))
    partial = _alternatives(rv, review, item)
    assert [c["place"]["name"] for c in partial["candidates"]] == ["가까운 시장골목", "먼 한옥길"] and {c["taste"]["ranked_by"] for c in partial["candidates"]} == {"count"}
