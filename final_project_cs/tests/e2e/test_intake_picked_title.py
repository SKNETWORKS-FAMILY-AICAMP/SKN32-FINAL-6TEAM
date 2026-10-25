# -*- coding: utf-8 -*-
"""등록할 때 고객이 고른 곳은 **그 장소 이름이 일정 이름** — `POST …/confirm`. `[2026-10-25 사용자 결정]`

☆왜: 휴무인 창덕궁을 확인 화면에서 「쌈지길로 바꾸기」로 고른 뒤 등록하면 여행 화면이 「창덕궁」 + 아래 「쌈지길」이었다 — 처음 등록만 적힌 이름을
썼다(수정 모드 완료는 고른 곳의 이름을 쓴다). 계약 `wiki/external/rest-endpoints/web-intakes.md` 의 `/confirm` 줄 · 단위 `test_intake_registered_title.py`.

재현:

    python -m pytest tests/e2e/test_intake_picked_title.py -v
"""
from __future__ import annotations

from uuid import UUID

from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.infrastructure.db.session import get_connection

from .test_intake_review import _client, _edit, _field, _item, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처


def test_a_place_the_customer_picked_names_the_registered_stop_and_the_written_name_stays_in_the_evidence(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n10시 경복궁\n11시 올리브영\n14시 광장시장")
    oy = _item(view, "올리브영")
    pick = {"name": "올리브영 명동 플래그십", "latitude": 37.5637, "longitude": 126.9851, "source": "kakao", "kind": "activity"}
    done = _edit(client, headers, view, _field(oy, "place", pick))
    registered = client.post(f"/v1/web/trip-intakes/{done['intake_id']}/confirm", headers=headers, json={"revision": done["revision"]})
    assert registered.status_code == 200, registered.text
    with get_connection() as conn:
        items = TripStore(rv["tenant"]).latest(conn, UUID(registered.json()["trip"]["trip_id"]))[1]
    stops = {i.title: i for i in items if i.kind != "mobility"}
    assert "올리브영 명동 플래그십" in stops and "올리브영" not in stops, sorted(stops)   # ★전에는 「올리브영」(고른 곳은 아래 줄)
    assert stops["올리브영 명동 플래그십"].detail["provenance"]["title"]["method"] != "customer"   # 원래 적힌 말의 근거는 그대로 남는다
    assert {"경복궁", "광장시장"} <= set(stops)                                       # 고르지 않은 일정은 적힌 이름 그대로
    # ★`[2026-10-25]` 이름이 바뀐 일정 옆 이동도 등록에 남는다 — 이동을 잇는 짝은 제목이 아니라 원본 위치로 찾는다(`registered_moves._match`).
    #   ☆제목까지 견주던 판에서는 확인 화면이 잰 「경복궁 → 올리브영」 · 「올리브영 → 광장시장」이 빠졌다(로컬 실서버 여행 f966844a 의 「인사동 쌈지길 → 인사동」도 같았다)
    checked = [(m["from"], m["to"]) for m in done["review"]["moves"] if m.get("depart") and m.get("arrive")]
    assert (oy["id"] in {a for a, _ in checked}) and (oy["id"] in {b for _, b in checked}), done["review"]["moves"]
    kinds = [i.kind for i in sorted(items, key=lambda i: (i.starts_at, i.seq))]
    at = [i.title for i in sorted(items, key=lambda i: (i.starts_at, i.seq))].index("올리브영 명동 플래그십")
    assert kinds[at - 1] == "mobility" and kinds[at + 1] == "mobility", kinds
