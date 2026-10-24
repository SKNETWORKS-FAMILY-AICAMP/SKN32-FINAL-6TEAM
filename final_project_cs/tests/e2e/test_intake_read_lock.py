# -*- coding: utf-8 -*-
"""읽기는 쓰기를 기다리지 않는다 · 쓰기는 그대로 줄 선다 · 미리 보기는 계산하는 사이 판이 바뀌면 버린다. `[2026-10-24 사용자 결정 — ST4F-731]`

☆왜: 검사를 읽는 모든 길(`pipeline._review_of`)이 접수 행을 `FOR UPDATE` 로 잠가(2026-10-23), 「전체 자동 추천」 미리 보기(12~29초)가 잠금을 쥔 동안
멈춘 질문의 후보 · 접수 조회가 5~22초 기다렸다(2026-10-24 로컬 실측 — `wiki/records/reports/2026-10-24_계획확인_진행표시_후보대기_ST4F-731-732.md`).
잠금은 「늦게 끝난 일이 지난 판에 쓰지 않게」 넣은 것이라 **쓰기에는 모든 모드에서 그대로** 둔다(사용자 결정).

★지키려는 것
 ①다른 연결이 접수 행을 쥐고 있어도 접수 조회 · 후보는 기다리지 않는다
 ②쓰기(고치기)는 그 연결이 놓을 때까지 기다린다
 ③미리 보기의 추천 계산은 접수 행을 잠그지 않는다 — 그동안 다른 화면이 고쳐 판이 바뀌면 적용해 보지 않고 409 `stale_revision`

재현:

    python -m pytest tests/e2e/test_intake_read_lock.py -v
"""
from __future__ import annotations

import threading
import time
from uuid import UUID

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.intake import autofix as autofix_module

from .test_intake_review import ROOMY, _client, _field, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처

#: 다른 연결이 접수 행을 쥐는 시간(초) — 기다리는 요청은 이만큼 걸린다(우리가 고른 값)
HOLD_S = 3.0


def _hold(intake_id: UUID, seconds: float) -> threading.Thread:
    """다른 화면의 긴 쓰기처럼 접수 행을 잠그고 `seconds` 뒤에 놓는다 — 시험 스레드가 막히지 않게 따로 돈다."""
    ready = threading.Event()

    def run() -> None:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT 1 FROM trip_intakes WHERE intake_id=%s FOR UPDATE", (intake_id,))
            ready.set()
            time.sleep(seconds)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(10), "접수 행을 잠그지 못했다"
    return thread


def test_reading_the_check_and_its_alternatives_does_not_wait_for_a_write(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    item = view["review"]["items"][0]
    holder = _hold(UUID(view["intake_id"]), HOLD_S)
    started = time.monotonic()
    shown = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers)
    found = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates", headers=headers,
                       params={"source_id": item["source_id"], "index": item["index"]})
    waited = time.monotonic() - started
    holder.join()
    assert shown.status_code == 200 and found.status_code == 200, (shown.text, found.text)
    assert shown.json()["revision"] == view["revision"]
    assert waited < HOLD_S - 1, f"읽기가 쓰기를 기다렸다 {waited:.1f}s"


def test_a_write_still_waits_for_the_one_holding_the_intake(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    item = view["review"]["items"][0]
    holder = _hold(UUID(view["intake_id"]), HOLD_S)
    started = time.monotonic()
    edited = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                         json={"revision": view["revision"], "edits": [_field(item, "title", "경복궁 오전")]})
    waited = time.monotonic() - started
    holder.join()
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == view["revision"] + 1
    assert waited >= HOLD_S - 0.5, f"쓰기가 잠금을 기다리지 않았다 {waited:.1f}s"


def test_the_preview_is_dropped_when_the_plan_changes_while_it_is_worked_out(rv, monkeypatch):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    intake_id, item = UUID(view["intake_id"]), view["review"]["items"][0]

    def plan(conn, **kwargs):
        # 추천을 계산하는 사이 다른 화면이 고쳤다 — 그 연결은 기다리지 않는다(미리 보기가 잠금을 쥐고 있으면 2초 뒤 실패한다)
        with get_connection() as other, other.transaction(), other.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '2s'")
            cur.execute("UPDATE trip_intakes SET revision = revision + 1 WHERE intake_id=%s", (intake_id,))
        return {"changes": [{"id": item["id"], "source_id": item["source_id"], "index": item["index"],
                             "edits": [{"field": "title", "value": "다른 이름"}]}], "kept": []}

    monkeypatch.setattr(autofix_module, "plan", plan)
    got = client.post(f"/v1/web/trip-intakes/{intake_id}/autofix", headers=headers, json={"revision": view["revision"], "dry_run": True})
    assert got.status_code == 409, got.text
    assert got.json()["error"]["code"] == "stale_revision"
