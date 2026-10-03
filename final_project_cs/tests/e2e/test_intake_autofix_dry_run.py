# -*- coding: utf-8 -*-
"""전체 자동 추천의 **미리 보기**(`dry_run`) — 저장하지 않고 바뀔 모습(`view`)만 돌려준다. `[2026-10-03 ui 세션 요청서 3번]`

☆왜: 웹은 전체 자동 추천을 보여 주려고 **일단 적용한 뒤 되돌리는** 길로 대신했다 — 적용하면 새 판(`revision + 1`)과 `intake_claims` 한 판이 생기고 되돌리면 또 한 판이 생긴다.
미리 보기는 아무것도 남기지 않으면서 **실제로 적용했을 때와 같은 모양**을 준다.

★지키려는 것: ①저장하지 않는다(판 번호 · 값 줄 · 저장된 검사가 그대로) ②미리 보기의 검사는 **실제로 적용한 결과와 같다**(같은 길로 새 판을 만들어 읽고 되돌리므로)
③`preview: true` 로 표시한다(화면이 현재 판으로 착각하지 않게) ④바꿀 것이 없으면 현재 모습 그대로 ⑤`dry_run` 을 안 보내면 전과 같다(적용).

재현:

    python -m pytest tests/e2e/test_intake_autofix_dry_run.py -v
"""
from __future__ import annotations

from app.infrastructure.db.session import get_connection

from .test_intake_review import ROOMY, _client, _item, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처


def _counts(intake_id) -> tuple[int, int, int]:
    """(값 줄 수, 저장된 검사 수, 접수의 판 번호) — 미리 보기가 아무것도 남기지 않았는지 센다."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM intake_claims WHERE intake_id=%s", (intake_id,))
        claims = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM intake_reviews WHERE intake_id=%s", (intake_id,))
        reviews = cur.fetchone()[0]
        cur.execute("SELECT revision FROM trip_intakes WHERE intake_id=%s", (intake_id,))
        return claims, reviews, cur.fetchone()[0]


def _autofix(client, headers, view, **extra):
    return client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                       json={"revision": view["revision"], **extra})


def test_a_dry_run_saves_nothing_and_says_what_would_change(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    before = _counts(view["intake_id"])
    got = _autofix(client, headers, view, dry_run=True)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["applied"] is False and body["dry_run"] is True and body["revision"] == view["revision"]
    [change] = [c for c in body["changed"] if c["title"] == "올리브영"]
    assert change["to"]["place"]["name"] == "올리브영 광화문점"
    assert _counts(view["intake_id"]) == before                                          # ★아무것도 안 남았다
    assert client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers).json()["revision"] == view["revision"]


def test_the_preview_view_is_exactly_what_a_real_apply_produces(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    preview = _autofix(client, headers, view, dry_run=True).json()["view"]
    assert preview["preview"] is True and preview["revision"] == view["revision"] + 1          # 적용하면 이 판이 된다
    real = _autofix(client, headers, view).json()
    assert real["applied"] is True and real["revision"] == preview["revision"]
    assert "preview" not in real["view"]                                                       # 실제 적용 결과에는 표시가 없다
    for part in ("items", "moves", "needs", "ready"):
        assert preview["review"][part] == real["view"]["review"][part], part               # 검사 결과가 같다
    assert _item(preview, "올리브영")["place"] == _item(real["view"], "올리브영")["place"]


def test_a_dry_run_with_nothing_to_change_shows_the_current_state(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    applied = _autofix(client, headers, view).json()
    again = _autofix(client, headers, {**view, "revision": applied["revision"]}, dry_run=True).json()
    assert again["applied"] is False and again["dry_run"] is True and again["changed"] == []
    assert again["view"]["revision"] == applied["revision"] and again["view"].get("preview") is not True


def test_without_dry_run_the_behaviour_is_unchanged(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    body = _autofix(client, headers, view).json()
    assert body["applied"] is True and body.get("dry_run") is False and body["revision"] == view["revision"] + 1


def test_dry_run_is_only_for_auto_fix_and_must_be_a_boolean(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    assert _autofix(client, headers, view, dry_run="yes please").status_code == 422
    revalidate = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/revalidate", headers=headers,
                             json={"revision": view["revision"], "dry_run": True})
    assert revalidate.status_code == 422                                                      # 재검증에는 미리 보기가 없다(모르는 칸은 거절)
