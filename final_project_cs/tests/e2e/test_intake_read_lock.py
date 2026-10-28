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
#: 읽기 시험에서 잠금을 쥐는 최대 시간(초) — 읽기가 끝나면 바로 놓는다. 읽기가 잠금을 기다리면 이 시간이 다 지나서야 끝나고 실패한다(우리가 고른 값)
HOLD_MAX_S = 30.0


def _hold(intake_id: UUID, seconds: float, until: threading.Event | None = None) -> threading.Thread:
    """다른 화면의 긴 쓰기처럼 접수 행을 잠그고 `seconds` 뒤에(`until` 이 있으면 그것이 켜지는 즉시) 놓는다 — 시험 스레드가 막히지 않게 따로 돈다.

    ★`until` 을 줬는데 `seconds` 가 다 지나 놓았으면 `thread.released_by_timeout` 이 True 다.
    """
    ready = threading.Event()

    def run() -> None:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT 1 FROM trip_intakes WHERE intake_id=%s FOR UPDATE", (intake_id,))
            ready.set()
            if until is None:
                time.sleep(seconds)
            else:
                thread.released_by_timeout = not until.wait(seconds)

    thread = threading.Thread(target=run, daemon=True)
    thread.released_by_timeout = False
    thread.start()
    assert ready.wait(10), "접수 행을 잠그지 못했다"
    return thread


def test_reading_the_check_and_its_alternatives_does_not_wait_for_a_write(rv):
    """①: 잠금을 **쥔 채로** 두 읽기가 끝나야 한다.

    ☆`[2026-10-28]` 전에는 「두 읽기 합계 < HOLD_S − 1(2초)」로 쟀다. 잠금 대기가 0건이어도 로컬 격리 실행에서 두 읽기가 각각 약 1초라
      단독 실행에서도 2.0초로 실패했다(`pg_stat_activity` 잠금 대기 표본 0 — 계산 시간이지 잠금이 아니었다). 이제 읽기가 끝날 때까지 잠금을
      쥐고 있다가 놓으므로, 읽기가 잠금을 기다리면 `HOLD_MAX_S` 가 다 지나야 끝나고 실패한다 — 읽기 속도와 무관하게 판정한다.
    """
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    item = view["review"]["items"][0]
    done = threading.Event()
    holder = _hold(UUID(view["intake_id"]), HOLD_MAX_S, until=done)
    started = time.monotonic()
    shown = client.get(f"/v1/web/trip-intakes/{view['intake_id']}", headers=headers)
    found = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates", headers=headers,
                       params={"source_id": item["source_id"], "index": item["index"]})
    waited = time.monotonic() - started
    held_throughout = holder.is_alive() and not holder.released_by_timeout
    done.set()
    holder.join()
    assert shown.status_code == 200 and found.status_code == 200, (shown.text, found.text)
    assert shown.json()["revision"] == view["revision"]
    assert held_throughout and not holder.released_by_timeout, f"읽기가 쓰기를 기다렸다 {waited:.1f}s"


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
