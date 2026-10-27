"""`[2026-10-27 서빙 속도]` 처음 검사의 위험 점검(`risks.decorate`)은 일정마다 바깥 조회를 **차례로** 기다렸다.

x600 실측(2026-10-20~26 접수 152건, 첫 판): 점검 시작 → 마지막 일정 점검 끝 p50 4.8초 · p95 19.5초, 일정당 p50 1.24초.
고객은 이 시간 동안 「읽는 중」을 본다(첫 판 검사가 끝나야 확인 화면으로 넘어간다).

바꾼 것: 첫 일정은 혼자 점검한다(지역 단위 응답 — 특보 · 대기질 · 지진 — 을 공유 캐시에 채운다, `cache.py` 머리말의 이유),
남은 일정은 가드레일 `travel.mcp.risk_check.parallel_items` 개까지 동시에 점검한다. 1 이면 예전처럼 차례로.
결과 · 순서 · 한도(`max_items`) · 진행 알림 순서는 차례로 돌 때와 같아야 한다.
"""
import threading
import time
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core import settings as settings_module
from app.domains.travel_ops.components.intake import risks
from app.domains.travel_ops.components.watch import risk_report

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 14, tzinfo=KST)
STAMP = NOW.isoformat()


def row(n: int) -> dict:
    return {"id": f"1-{n}", "source_id": str(uuid4()), "index": n, "title": f"일정 {n}", "kind": "activity",
            "day": 1, "date": "2030-01-01", "starts_at": "13:00", "ends_at": "16:00", "locked": False,
            "place_state": "found", "place": {"name": f"장소 {n}", "latitude": 37.5 + n / 1000, "longitude": 127.0,
                                              "weather_sensitive": True, "source": "tour_api"}, "rows": []}


def clear_report() -> dict:
    return {"verdict": "clear", "checked_at": STAMP, "disruptions": [], "failed_categories": [],
            "checks": [{"category": c, "status": "ok", "source": "test_source", "confirmed_at": STAMP}
                       for c in risk_report.CATEGORIES]}


@pytest.fixture
def parallel(monkeypatch):
    """가드레일의 `travel.mcp.risk_check.parallel_items` 만 바꿔 끼운다(나머지는 실제 파일 값)."""
    real = settings_module.get_guardrails

    def use(value: int) -> None:
        class Patched:
            def __init__(self, base):
                self._base = base

            def get(self, key, *args, **kwargs):
                if key == "travel.mcp.risk_check.parallel_items":
                    return value
                return self._base.get(key, *args, **kwargs)

        monkeypatch.setattr(settings_module, "get_guardrails", lambda: Patched(real()))
    return use


def run(items, check, events=None):
    return risks.decorate(None, tenant_id="unit", review={"items": items, "ready": True}, check=check, now=NOW, mode="fresh",
                          **({"on_event": lambda name, body: events.append(body)} if events is not None else {}))


def test_the_config_names_how_many_items_are_checked_at_once():
    value = settings_module.get_guardrails().get("travel.mcp.risk_check.parallel_items")
    assert isinstance(value, int) and value >= 1


def test_after_the_first_item_the_rest_are_checked_together(parallel):
    """첫 일정이 끝난 뒤에야 나머지가 시작하고(캐시 채우기), 나머지 셋은 서로 기다리지 않고 동시에 돈다."""
    parallel(3)
    lock = threading.Lock()
    first_done = threading.Event()
    meet = threading.Barrier(3, timeout=2.0)          # 차례로 돌면 아무도 만나지 못해 깨진다 → 점검 오류
    order: list[str] = []

    def check(*, place, starts_at):
        name = place["name"]
        with lock:
            order.append(name)
        if name == "장소 0":
            time.sleep(0.05)
            first_done.set()
        else:
            assert first_done.is_set(), "첫 일정이 끝나기 전에 다른 일정을 점검했다"
            meet.wait()
        return clear_report()

    out = run([row(n) for n in range(4)], check)
    risks_out = [it["risk"] for it in out["items"]]
    assert [r.get("code") for r in risks_out] == [None, None, None, None], risks_out
    assert [r["status"] for r in risks_out] == ["clear"] * 4
    assert order[0] == "장소 0"
    assert [it["id"] for it in out["items"]] == ["1-0", "1-1", "1-2", "1-3"]


def test_one_means_strictly_one_at_a_time(parallel):
    parallel(1)
    active, peak = [0], [0]
    lock = threading.Lock()

    def check(*, place, starts_at):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.02)
        with lock:
            active[0] -= 1
        return clear_report()

    run([row(n) for n in range(4)], check)
    assert peak[0] == 1


def test_limit_order_and_progress_are_the_same_as_one_at_a_time(parallel):
    """한도(`max_items`, 지금 6) 밖의 일정은 점검하지 않고 · 결과는 일정 순서대로 · 진행 알림도 같은 순서."""
    def check(*, place, starts_at):
        time.sleep(0.01 * (8 - int(place["name"].split()[-1])))        # 뒤 일정이 먼저 끝나게 — 순서가 섞이면 드러난다
        return {**clear_report(), "checked_at": place["name"]}

    items = [row(n) for n in range(8)]
    parallel(1)
    seq_events: list[dict] = []
    sequential = run(items, check, seq_events)
    parallel(4)
    par_events: list[dict] = []
    together = run(items, check, par_events)

    assert [it["risk"] for it in together["items"]] == [it["risk"] for it in sequential["items"]]
    limit = int(settings_module.get_guardrails().get("travel.mcp.risk_check.max_items"))
    codes = [it["risk"].get("code") for it in together["items"]]
    assert codes == [None] * limit + ["item_limit"] * (8 - limit)
    assert par_events == seq_events


def test_measured_wall_time_drops_when_items_run_together(parallel):
    """측정용 — 일정 4개 · 점검 0.2초씩: 차례로 ≈0.8초, 첫 일정 + 나머지 동시 ≈0.4초."""
    def check(*, place, starts_at):
        time.sleep(0.2)
        return clear_report()

    items = [row(n) for n in range(4)]
    parallel(1)
    started = time.perf_counter()
    run(items, check)
    one_by_one = time.perf_counter() - started
    parallel(3)
    started = time.perf_counter()
    run(items, check)
    together = time.perf_counter() - started
    print(f"risk decorate 4 items x 0.2s: sequential={one_by_one:.3f}s parallel3={together:.3f}s")
    assert one_by_one >= 0.75 and together < 0.6
