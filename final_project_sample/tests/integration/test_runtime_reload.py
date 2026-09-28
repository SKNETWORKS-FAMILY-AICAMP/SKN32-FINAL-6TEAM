"""반영(reload) 계약 — 실행 중인 조립과 저장소의 선언을 구분해 말하는가.

★이 파일이 막는 것: **반영 안 된 상태를 정상처럼 보이게 하는 것.**
  전에는 `/introspection` 이 매 요청마다 선언을 다시 읽어 `config_revision` 을
  계산했다. 그래서 Composer 로 선언을 바꾼 직후, 대상은 아직 옛 조립으로
  요청을 처리하는데 화면에는 새 revision 이 **이미 반영된 것처럼** 보였다.
  (설계검토 `docs/reports/2026-08-19_Composer_reload_계약_설계검토.md` §3)
"""
from __future__ import annotations

import pytest

from acop_basement.application.runtime import (
    STATE_ACTIVE, STATE_FAILED, STATE_STALE, STATE_UNKNOWN,
    ControllerProxy, RuntimeComposition,
)


class _Controller:
    def __init__(self, name: str) -> None:
        self.name = name

    def handle(self) -> str:
        return self.name


def test_proxy_follows_the_swap_instead_of_holding_the_old_controller():
    """★router 가 조립 시점 객체를 붙잡으면 갈아 끼워도 옛 것을 계속 쓴다."""
    runtime = RuntimeComposition(_Controller("old"), "rev-1")
    proxy = ControllerProxy(runtime)
    assert proxy.handle() == "old"

    runtime.swap(_Controller("new"), "rev-2")

    assert proxy.handle() == "new"
    assert runtime.active_revision == "rev-2"


def test_stale_is_reported_when_the_store_moved_ahead():
    runtime = RuntimeComposition(_Controller("old"), "rev-1")
    assert runtime.state("rev-1") == STATE_ACTIVE
    assert runtime.state("rev-2") == STATE_STALE


def test_unknown_revision_is_not_dressed_up_as_active_or_stale():
    """★모르는 것을 `stale` 로 적으면 없는 사실을 만든 것이고,
    `active` 로 적으면 반영 안 된 상태를 정상으로 감춘 것이다."""
    runtime = RuntimeComposition(_Controller("injected"), None)
    assert runtime.state("rev-2") == STATE_UNKNOWN
    assert runtime.active_revision is None


def test_a_failed_reload_keeps_the_old_composition_and_says_so():
    runtime = RuntimeComposition(_Controller("old"), "rev-1")
    runtime.mark_failed("rev-2", "team 'x' 를 만들지 못했다")

    assert runtime.controller.handle() == "old"      # 옛 조립 그대로
    assert runtime.state("rev-2") == STATE_FAILED
    assert runtime.last_error == "team 'x' 를 만들지 못했다"


def test_a_successful_swap_clears_the_previous_failure():
    runtime = RuntimeComposition(_Controller("old"), "rev-1")
    runtime.mark_failed("rev-2", "실패")
    runtime.swap(_Controller("new"), "rev-2")

    assert runtime.state("rev-2") == STATE_ACTIVE
    assert runtime.last_error is None


def test_snapshot_without_a_runtime_does_not_claim_anything_is_active():
    """★`runtime` 을 안 주면 실행 중인 revision 을 **모른다.** 저장소에서 읽은
    값을 실행 중인 것처럼 적지 않는다."""
    from acop_basement.introspection import snapshot

    pytest.importorskip("app.composition")
    snap = snapshot()

    assert snap["active_revision"] is None
    assert snap["reload_state"] == STATE_UNKNOWN
    assert snap["desired_revision"] is not None


def test_snapshot_separates_running_from_stored():
    from acop_basement.introspection import snapshot

    pytest.importorskip("app.composition")
    runtime = RuntimeComposition(_Controller("old"), "rev-옛것")
    snap = snapshot(runtime=runtime)

    assert snap["active_revision"] == "rev-옛것"
    assert snap["desired_revision"] != "rev-옛것"
    assert snap["reload_state"] == STATE_STALE
    # 옛 소비자용 필드는 실행 중인 값을 가리킨다
    assert snap["config_revision"] == "rev-옛것"
    assert snap["contract_version"] == "1.1"
