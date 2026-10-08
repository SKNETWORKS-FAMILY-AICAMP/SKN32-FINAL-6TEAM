# -*- coding: utf-8 -*-
"""검사 **진행 알림** — 일정 하나가 끝날 때마다 이벤트를 쌓아 두는 프로세스 안 보관소와, 읽기(`read_source`)가 내는 「장소 n/m」. `[2026-10-03 ui 세션 요청서 2번]`

☆왜: 검사(`review.build`)는 한 트랜잭션 안에서 돌고 **끝나 커밋돼야** DB 에 보여서, 실시간 진행(SSE)이 검사 줄 56개 · 이동 12개를 끝난 4.9초에 한꺼번에 내보냈다.
이동 계산(시간표)이 대부분의 시간인데 그동안 화면은 아무것도 몰랐다. 보관소는 **계산이 끝나는 대로** 이벤트를 쌓고, SSE 가 1초마다 그것을 비워 내보낸다.

★지키려는 것: ①차례대로 쌓이고 **자기 몫(cursor)만** 비운다 — 연결마다 따로 ②접수 하나당 상한이 있다(메모리가 자라지 않는다) ③오래 안 쓴 접수는 버린다
④쌓기가 실패해도 **읽기를 막지 않는다**(진행 알림은 부가 기능) ⑤읽기가 「장소 n/m」을 일정마다 알린다.

재현:

    python -m pytest tests/unit/travel/test_intake_progress.py -v
"""
from __future__ import annotations

from datetime import date

from app.domains.travel_ops.components.intake import progress
from app.domains.travel_ops.components.intake.pipeline import read_source


def setup_function(_fn):
    progress.reset()


def test_events_are_kept_in_order_and_each_reader_drains_only_its_own_share():
    progress.emit("a", "progress", {"phase": "hours", "done": 1, "total": 3})
    progress.emit("a", "check", {"item": "0-0", "row": "place"})
    first, cursor = progress.drain("a", 0)
    assert [name for name, _ in first] == ["progress", "check"] and cursor == 2
    progress.emit("a", "move", {"from": "0-0", "to": "0-1"})
    second, cursor2 = progress.drain("a", cursor)                         # 이미 가져간 것은 다시 안 준다
    assert [name for name, _ in second] == ["move"] and cursor2 == 3
    again, _ = progress.drain("a", 0)                                      # 다른 연결(처음부터)은 처음부터 다 받는다
    assert len(again) == 3
    assert progress.drain("someone-else", 0) == ([], 0)                    # 다른 접수의 것은 안 섞인다


def test_the_store_is_bounded_per_intake_and_keeps_the_newest(monkeypatch):
    monkeypatch.setattr(progress, "MAX_EVENTS", 5)
    for n in range(12):
        progress.emit("a", "progress", {"done": n})
    events, cursor = progress.drain("a", 0)
    assert [body["done"] for _, body in events] == [7, 8, 9, 10, 11] and cursor == 12     # 가장 새 상태가 남는다(이벤트는 상태의 복사본)


def test_an_untouched_intake_is_forgotten_after_the_time_limit(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(progress.time, "monotonic", lambda: now[0])
    progress.emit("old", "progress", {"done": 1})
    now[0] += progress.TTL_SECONDS + 1
    progress.emit("new", "progress", {"done": 1})                          # 다음 쓰기가 오래된 접수를 치운다
    assert progress.drain("old", 0) == ([], 0) and len(progress.drain("new", 0)[0]) == 1


def test_clear_forgets_one_intake():
    progress.emit("a", "progress", {"done": 1})
    progress.emit("b", "progress", {"done": 1})
    progress.clear("a")
    assert progress.drain("a", 0) == ([], 0) and len(progress.drain("b", 0)[0]) == 1


def test_a_failing_store_never_breaks_reading(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("보관소 장애")

    monkeypatch.setattr(progress, "emit", boom)
    push = progress.sink("a")
    push("progress", {"done": 1})                                          # 예외가 밖으로 안 나온다(읽기를 막지 않는다)


# ── 읽기가 내는 「장소 n/m」 ───────────────────────────────────────────
class _Tour:
    PLACES = {"경복궁": ("126508", "12", 37.5796, 126.9770), "광장시장": ("264570", "38", 37.5700, 126.9996)}
    misses: dict = {}

    def find(self, name, area_code=None):
        if name not in self.PLACES:
            return None
        cid, ctype, lat, lon = self.PLACES[name]
        return {"matched_title": name, "content_id": cid, "content_type_id": ctype, "latitude": lat, "longitude": lon,
                "address": "서울특별시 종로구"}


def test_reading_reports_place_progress_one_item_at_a_time():
    seen: list[tuple] = []
    text = "2026-10-15\n10시 경복궁 관람\n12시 광장시장\n15시 아무도 모르는 곳"
    read_source(text, tour=_Tour(), kakao=None, our_places=[], today=date(2026, 10, 3),
                on_progress=lambda phase, done, total, index, title: seen.append((phase, done, total, index, title)))
    assert [(p, d, t) for p, d, t, _, _ in seen] == [("places", 1, 3), ("places", 2, 3), ("places", 3, 3)]    # 찾든 못 찾든 한 곳씩 센다
    assert [title for *_, title in seen] == ["경복궁 관람", "광장시장", "아무도 모르는 곳"]
    assert [index for _, _, _, index, _ in seen] == [0, 1, 2]


def test_reading_without_a_progress_hook_is_unchanged():
    rows = read_source("10시 경복궁", tour=_Tour(), kakao=None, our_places=[], today=date(2026, 10, 3))
    assert any(r["field"] == "items[0].place" for r in rows)
