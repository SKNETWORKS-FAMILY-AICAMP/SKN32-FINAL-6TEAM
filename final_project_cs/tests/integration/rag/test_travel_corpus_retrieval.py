# -*- coding: utf-8 -*-
"""여행 코퍼스가 여행 질의에 답하고, 쇼핑몰 코퍼스와 섞이지 않는지 본다. `[2026-09-22]`

★왜 있나. 2026-09-22 전까지 `knowledge_documents` 에는 쇼핑몰 25문서뿐이었고 여행 문서는
  0건이었다. 그래서 여행 Team 셋은 `required_context` 에서 `policy` 를 빼고 돌았고
  (2026-09-17), 예약 인계 Team 은 선언만 남긴 채 **문서 0건인 scope** 를 검색해
  매번 degraded 로 떨어졌다. 이 시험은 그 상태로 되돌아가는 것을 막는다.

적재: `python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json`
"""
from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.rag.retriever import search_policy

#: 여행 코퍼스 scope (knowledge/travel/manifest.json · scripts/check_corpus.py TRAVEL_SCOPE_PLAN)
TRAVEL_SCOPES = ["travel_activity", "travel_weather", "travel_dining",
                 "travel_mobility", "travel_cancellation", "travel_access"]
COMMERCE_SCOPES = ["order", "shipping", "return", "exchange", "refund", "support", "incident"]


@pytest.fixture(scope="module", autouse=True)
def travel_corpus_loaded():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s AND scope = ANY(%s)",
                    ("demo", TRAVEL_SCOPES))
        documents = cur.fetchone()[0]
        cur.execute(
            """SELECT count(*), count(kc.embedding_1024)
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.tenant_id=%s AND kd.scope = ANY(%s)""", ("demo", TRAVEL_SCOPES))
        chunks, local_vectors = cur.fetchone()
    assert (documents, chunks, local_vectors) == (12, 130, 130), (
        "여행 코퍼스가 적재돼 있어야 한다: 기대 문서 12 · 청크 130 · 1024칸 130, "
        f"실측 문서 {documents} · 청크 {chunks} · 1024칸 {local_vectors}")


@pytest.mark.parametrize(
    ("query", "scopes", "expected_document"),
    [
        # 사용자가 실제로 던지는 문장 두 개 (작업 지시 §5)
        ("비가 와서 야외 활동을 못 하게 됐다",
         ["travel_activity", "travel_weather", "travel_cancellation"], "t_doc_04"),
        ("예약을 이틀 전에 취소하면 위약금이 있나요",
         ["travel_activity", "travel_cancellation"], "t_doc_01"),
        # 나머지 두 Team 의 대표 질의
        ("지하철 운행이 중단돼서 다음 일정에 못 갈 것 같아요",
         ["travel_mobility", "travel_weather"], "t_doc_08"),
        ("휠체어를 쓰는 일행이 있는데 들어갈 수 있나요",
         ["travel_dining", "travel_access"], "t_doc_12"),
    ],
)
def test_travel_queries_find_travel_documents(query, scopes, expected_document):
    results = search_policy("demo", query, scopes)
    assert results, f"{query!r} 가 아무 근거도 못 찾았다"
    assert len(results) <= 8
    assert expected_document in {chunk.document_id for chunk in results}
    assert all(chunk.scope in scopes for chunk in results)


def test_commerce_queries_still_find_commerce_documents():
    """★쇼핑몰 코퍼스의 판정이 깨지지 않았는지. 두 코퍼스는 공존한다."""
    results = search_policy("demo", "배송완료로 떴는데 못 받았어요", ["shipping", "return", "exchange"])
    assert "doc_01" in {chunk.document_id for chunk in results}
    assert not any(chunk.document_id.startswith("t_doc") for chunk in results)


def test_travel_query_under_commerce_scope_never_returns_travel_documents():
    """★scope 가 도메인을 가른다 — 질의가 여행이어도 scope 가 쇼핑몰이면 여행 문서는 안 나온다."""
    results = search_policy("demo", "비가 와서 야외 활동을 못 하게 됐다", COMMERCE_SCOPES)
    assert results, "쇼핑몰 scope 에는 문서가 있으므로 결과가 비면 안 된다"
    assert all(not chunk.document_id.startswith("t_doc") for chunk in results)


def test_commerce_query_under_travel_scope_never_returns_commerce_documents():
    results = search_policy("demo", "반품 수량이 주문 수량을 넘었어요", TRAVEL_SCOPES)
    assert results
    assert all(chunk.document_id.startswith("t_doc") for chunk in results)


def test_tenant_isolation_holds_for_the_travel_corpus():
    assert search_policy("tenant-that-does-not-exist", "비가 와서 못 간다", TRAVEL_SCOPES) == []


def test_the_two_corpora_do_not_share_a_scope_name():
    """★이름이 겹치면 한 질의가 두 도메인을 가로지른다. DB 로 직접 센다."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT scope FROM knowledge_documents WHERE tenant_id=%s", ("demo",))
        scopes = {row[0] for row in cur.fetchall()}
    assert set(TRAVEL_SCOPES) & set(COMMERCE_SCOPES) == set()
    assert set(TRAVEL_SCOPES) <= scopes, f"적재되지 않은 여행 scope: {set(TRAVEL_SCOPES) - scopes}"
    assert set(COMMERCE_SCOPES) <= scopes


def test_registered_teams_never_search_commerce_scopes():
    """★등록된 여섯은 전부 **여행** Team 이다(`tests/registered_teams.py`). 쇼핑몰 문서를 보면 안 된다.

    2026-09-22 이전 Activity 의 `knowledge_scope` 에 `refund` 가 들어 있었다 — 쇼핑몰
    코퍼스에 **실재하는 scope** 라, 정책을 켜는 순간 활동 취소 판정이 쇼핑몰 환불 규정을
    근거로 집어 온다. 이름이 겹치지 않게 `travel_` 접두를 쓰는 이유가 이것이다.
    """
    from app.composition import build_registry

    bleeding = {m.team_id: sorted(set(m.knowledge_scope) & set(COMMERCE_SCOPES))
                for m in build_registry().manifests()
                if set(m.knowledge_scope) & set(COMMERCE_SCOPES)}
    assert not bleeding, f"여행 Team 이 쇼핑몰 scope 를 검색 범위에 두고 있다: {bleeding}"


def test_every_team_that_requires_policy_has_documents_in_its_scope():
    """★★`required_context` 에 `policy` 를 선언한 Team 은 **문서가 있는 scope** 를 봐야 한다.

    없으면 검색이 0건이고, 0건은 `ContextPack.degraded=True` 를 만들며, degraded 는
    `TravelTeamBase._guard` 에서 곧바로 `escalated` 다 — 즉 그 Team 의 **모든 Case 가
    사람에게 간다.** 2026-09-22 이전에 예약 인계·숙소·항공 셋이 실제로 그 상태였다.
    """
    from app.composition import build_registry

    offenders = []
    with get_connection() as conn, conn.cursor() as cur:
        for manifest in build_registry().manifests():
            if "policy" not in (manifest.required_context or []):
                continue
            cur.execute(
                "SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s AND scope = ANY(%s)",
                ("demo", list(manifest.knowledge_scope)))
            if cur.fetchone()[0] == 0:
                offenders.append((manifest.team_id, list(manifest.knowledge_scope)))
    assert not offenders, (
        "policy 를 필수로 선언했는데 그 scope 에 문서가 0건인 Team 이 있다 — "
        f"이 Team 의 모든 Case 가 degraded 로 escalated 된다: {offenders}")

# ── 일정 생성기가 요청을 이 코퍼스에 붙인다 `[2026-09-22]` ─────────
@pytest.mark.parametrize("preferences", [
    "비가 오면 야외 활동은 어떻게 되나요",
    "아이 동반이라 유모차로 다닐 수 있는 곳이 좋아요",
    "지하철이 멈추면 다음 예약은 어떻게 되나요",
])
def test_the_planner_grounds_a_request_in_travel_rules_only(preferences):
    """★`POST /v1/trips/plan` 이 고객의 말로 **이 코퍼스**를 검색한다.

    ★여기서 쇼핑몰 문서가 하나라도 나오면 그건 2026-09-22 에 고친 결함이 되돌아온 것이다
      (여행 질의 top-8 중 7건이 쇼핑몰 환불 문서였다).
    """
    from datetime import date

    from app.modules.travel_ops.planner import PlanRequest, ground_request, grounding_text

    found = ground_request(
        tenant_id="demo",
        request=PlanRequest(city="서울", start_date=date(2026, 10, 5), days=2, party_size=2,
                            preferences=preferences))

    assert found["hits"] > 0, (preferences, found["note"])
    assert all(item["scope"] in TRAVEL_SCOPES for item in found["evidence"]), found["evidence"]
    assert all(item["source_type"] == "policy" and "#c" in item["source_id"]
               for item in found["evidence"])
    # 모델에게 보일 형태에도 그 조각이 그대로 실린다
    text = grounding_text(found)
    assert found["evidence"][0]["excerpt"][:20] in text


def test_grounding_never_reaches_into_the_commerce_corpus():
    """★상품 범위 밖의 말을 해도 쇼핑몰 문서를 끌어오면 안 된다."""
    from datetime import date

    from app.modules.travel_ops.planner import PlanRequest, ground_request

    found = ground_request(
        tenant_id="demo",
        request=PlanRequest(city="서울", start_date=date(2026, 10, 5), days=2, party_size=2,
                            preferences="환불 받을 수 있나요 배송은 언제 오나요"))
    assert all(item["scope"] in TRAVEL_SCOPES for item in found["evidence"]), found["evidence"]
