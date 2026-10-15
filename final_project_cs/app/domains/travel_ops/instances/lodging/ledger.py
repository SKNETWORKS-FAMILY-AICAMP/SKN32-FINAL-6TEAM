# -*- coding: utf-8 -*-
"""숙소 · 항공 원장 — 보여 준 후보를 기억하고, 고른 MCP 숙소를 그 여행 전용 장소로 들여놓는다. `[2026-10-12]`

왜.
    숙소 · 항공 팀의 후보는 MCP(마이리얼트립 · Ignav · 구글)에서 온다 — DB 에 없다(사용자 10-12 「우리 에이전트는 MCP 라 DB 가 전혀 없다」).
    요식 팀은 원장(`dining.*`)이 있어 대체 후보를 그 여행 전용 장소로 들여놓고(`instances/dining/nearby.py`) 일정 항목이 진짜
    `place_id` 를 가리킨다. 우리도 같은 모양으로 둔다(사용자 10-12 「우리 안에서 다른 에이전트들처럼」).

무엇을.
    remember_shown   한 항목에 보여 준 후보를 적는다(`lg_offer_shown`) — 다음 「바꿔 줘」에서 뺀다.
    shown_keys       그 항목에 지금까지 보여 준 후보 key 들.
    adopt_option     고른 숙소 후보를 그 여행 전용 장소로 들여놓고(`TripStore.adopt_places`) 연결을 적는다(`lg_core_place_link`).
                     좌표가 없으면(마이리얼트립 목록 값) 들여놓지 않고 None — 부르는 쪽은 지금처럼 `place_id` 를 비운다.

경계(요식 원장과 같다).
    코어 표에 직접 쓰지 않는다 — 장소 행은 코어(`store.adopt_places`)가 만든다. 여기는 `lg_*` 표만 쓴다.
    외부 값은 그 여행에만 둔다(029) — 열쇠에 여행 id 가 들어 있다.
    코어 · 인프라를 import 하지 않는다(팀 경계). 연결(`conn`)과 코어 저장소(`store`)는 부르는 쪽이 넘긴다.
    부르는 쪽은 부품이고 조립 때 꽂힌 자리(`components/team_hooks/lodging_ledger.py`)로 부른다 — 팀(Case 경로)은 DB 에 쓰지 않는다.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def item_key(kind: str, query: dict[str, Any]) -> str | None:
    """항목을 판이 바뀌어도 같은 이름으로 — 숙소는 체크인 · 체크아웃, 항공은 노선 · 날짜(팀의 `detail.query` 와 같은 값)."""
    if kind == "lodging" and query.get("check_in") and query.get("check_out"):
        return f"lodging:{query['check_in']}:{query['check_out']}"
    if kind == "flight" and query.get("origin") and query.get("destination") and query.get("depart_date"):
        return f"flight:{query['origin']}-{query['destination']}:{query['depart_date']}"
    return None


def remember_shown(conn, tenant_id: str, trip_id: Any, key: str, options: list[dict[str, Any]],
                   *, case_id: Any = None) -> int:
    """보여 준 후보를 적는다. 이미 있으면 그대로(같은 후보를 두 번 적지 않는다). 적은 줄 수."""
    written = 0
    with conn.cursor() as cur:
        for option in options:
            price = option.get("price_per_night") if option.get("price_per_night") is not None else option.get("best")
            cur.execute("INSERT INTO lg_offer_shown (tenant_id, trip_id, item_key, offer_key, name, source, link, price, case_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (tenant_id, str(trip_id), key, str(option["key"]), str(option["name"]),
                         option.get("source") or option.get("seller"), option.get("link"), price,
                         str(case_id) if case_id else None))
            written += cur.rowcount if isinstance(getattr(cur, "rowcount", None), int) and cur.rowcount > 0 else 0
    return written


def shown_keys(conn, tenant_id: str, trip_id: Any, key: str) -> list[str]:
    """그 항목에 보여 준 후보 key — 보여 준 순서대로."""
    with conn.cursor() as cur:
        cur.execute("SELECT offer_key FROM lg_offer_shown WHERE tenant_id=%s AND trip_id=%s AND item_key=%s "
                    "ORDER BY shown_at, offer_key", (tenant_id, str(trip_id), key))
        return [row[0] for row in cur.fetchall()]


def shown_offers(conn, tenant_id: str, trip_id: Any, key: str) -> list[dict[str, Any]]:
    """그 항목에 보여 준 후보의 key 와 이름 — 보여 준 순서대로. `[2026-10-13]` 숙소 팀은 이름으로, 항공 팀은 key 로 뺀다."""
    with conn.cursor() as cur:
        cur.execute("SELECT offer_key, name FROM lg_offer_shown WHERE tenant_id=%s AND trip_id=%s AND item_key=%s "
                    "ORDER BY shown_at, offer_key", (tenant_id, str(trip_id), key))
        return [{"key": row[0], "name": row[1]} for row in cur.fetchall()]


def adopt_option(conn, store: Any, trip_id: Any, option: dict[str, Any]) -> dict[str, Any] | None:
    """고른 숙소 후보 → 그 여행 전용 장소(코어 행) + 연결. 좌표가 없으면 None(들여놓지 않는다 — 좌표를 지어내지 않는다).

    ★같은 여행 · 같은 이름 · 같은 종류(`lodging`)면 코어가 있는 행을 돌려준다(029 유일 색인) — 다시 불러도 같은 행이다."""
    lat, lon = option.get("latitude"), option.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    attributes = {"source": "lodging_ledger", "offer_key": str(option["key"]), "provider": option.get("source"),
                  **({"link": option["link"]} if option.get("link") else {})}
    adopted = store.adopt_places(conn, trip_id, [{"name": str(option["name"]), "kind": "lodging",
                                                  "latitude": float(lat), "longitude": float(lon), "attributes": attributes}])
    place = next((p for p in adopted if p.get("kind") == "lodging" and p.get("name") == str(option["name"])), None)
    if place is None:
        return None
    with conn.cursor() as cur:
        cur.execute("INSERT INTO lg_core_place_link (tenant_id, core_place_id, trip_id, offer_key, source, link) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (store.tenant_id, str(place["place_id"]), str(trip_id), str(option["key"]),
                     option.get("source"), option.get("link")))
    return place


__all__ = ["adopt_option", "item_key", "remember_shown", "shown_keys", "shown_offers"]
