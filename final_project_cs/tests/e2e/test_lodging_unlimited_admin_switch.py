# -*- coding: utf-8 -*-
"""관리 콘솔의 「숙소 모드」 · 「언리미티드 모드」 — 운영 API 로 바꾸면 cs 프로젝트 서버의 바깥 호출 문이 그 값을 읽는다. `[2026-10-19 사용자 결정]`

관리 콘솔 「운영 설정」 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(고르기 칸 · 선택지 글자 `choice_labels_ko`).
언리미티드 모드는 「API 호출량」 탭이 확인 창을 거쳐 같은 PATCH 로 저장한다.
★실제 SerpApi 는 부르지 않는다 — 확인 화면 「다른 숙소」 길(`composition._lodging_rank`)은 소스 묶음을 mock 으로 바꿔 끼운다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.ports.data_sources import operator_modes

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_guard import _client
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_11_06 = reldate.day("2026-11-06")
D_2026_11_07 = reldate.day("2026-11-07")

LODGING, UNLIMITED = settings_hook.LODGING_MODE, settings_hook.UNLIMITED_MODE
QUERY = {"keyword": "명동", "check_in": D_2026_11_06, "check_out": D_2026_11_07, "adults": 2}


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    operator_modes.clear()
    web_guard.clear_cache()


def _patch(client, api, revision, changes, reason="시험"):
    return client.patch("/admin/limits", headers=api["auth"]("limits:write"),
                        json={"expected_revision": revision, "actor": "op-kim", "reason": reason, "changes": changes})


def test_the_console_lists_both_modes_off_and_saving_them_takes_effect(api):
    from app.composition import wire_operator_modes

    wire_operator_modes()                       # 조립이 바깥 호출 문에 두 모드를 꽂는 자리(`wire_optional_features` 가 부른다) — 다른 전역 등록은 남기지 않는다
    client = _client()
    view = client.get("/admin/limits", headers=api["auth"]("limits:read")).json()
    lodging = next(r for r in view["limits"] if r["name"] == LODGING)
    unlimited = next(r for r in view["limits"] if r["name"] == UNLIMITED)
    assert (lodging["type"], lodging["value"], lodging["source"]) == ("choice", "off", "default")
    assert lodging["choices"] == ["demo", "test", "off"]
    assert lodging["choice_labels_ko"] == {"demo": "숙소 시연 모드", "test": "테스트 모드", "off": "끄기"}
    assert (unlimited["type"], unlimited["value"]) == ("bool", False) and "유료 호출이 늘 수 있" in unlimited["text_ko"]
    assert operator_modes.lodging_mode() == "off" and operator_modes.unlimited() is False

    wrong = _patch(client, api, view["revision"], {LODGING: "on"})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "not_a_choice"

    demo = _patch(client, api, view["revision"], {LODGING: "demo", UNLIMITED: True}, reason="최종 발표 시연")
    assert demo.status_code == 200, demo.text
    assert settings_hook.lodging_mode(api["tenant"]) == "demo" and settings_hook.unlimited_mode(api["tenant"]) is True
    assert operator_modes.lodging_mode() == "demo" and operator_modes.unlimited() is True

    back = _patch(client, api, demo.json()["revision"], {LODGING: None, UNLIMITED: None}, reason="시연 끝")
    assert back.status_code == 200, back.text
    assert operator_modes.lodging_mode() == "off" and operator_modes.unlimited() is False


@pytest.fixture()
def lodging_rank(api, monkeypatch):
    """확인 화면 「다른 숙소」 — 조립이 꽂은 숙소 팀 고르기(`composition._lodging_rank`). 소스 묶음을 만드는 곳을 mock 으로 바꿔 몇 번 만드는지 센다."""
    from app import composition
    from app.domains.travel_ops.components.team_hooks import lodging_alternatives, lodging_ledger
    from app.domains.travel_ops.ports.data_sources import base

    built: list[float | None] = []

    def fake_build(settings, *, cache_only=False, low_priority_share=None):
        built.append(low_priority_share)
        return SimpleNamespace(stay_google=None)          # 구글 호텔이 없으면 숙소 팀은 바깥에 안 나가고 None

    monkeypatch.setattr(base, "build_travel_sources", fake_build)
    composition._wire_domain_providers(active_ids={"lodging"})
    yield built
    lodging_alternatives.clear()
    lodging_ledger.clear()


def test_the_confirm_screen_does_not_build_hotel_sources_when_lodging_mode_is_off(api, lodging_rank):
    from app.domains.travel_ops.components.team_hooks import lodging_alternatives

    assert lodging_alternatives.ranked(**QUERY) is None
    assert lodging_rank == [], "끄기 — 숙소 팀 길에 들어가지 않는다(자체 고르기: DB → 카카오 · 관광공사)"


@pytest.mark.parametrize("mode", ["test", "demo"])
def test_the_confirm_screen_asks_the_lodging_team_in_test_and_demo(api, lodging_rank, mode):
    from app.domains.travel_ops.components.team_hooks import lodging_alternatives
    from .test_web_guard import _set

    _set(api, LODGING, mode)
    assert lodging_alternatives.ranked(**QUERY) is None              # mock 소스에 구글 호텔이 없어 답은 None
    assert lodging_rank == [0.25], "몫(travel.candidates.lodging_source_share)으로 만든 소스 묶음 — 시연은 호출 문이 몫을 뺀다"
