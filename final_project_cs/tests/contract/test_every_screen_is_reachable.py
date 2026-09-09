"""등록된 운영 UI 화면이 **메뉴에서 닿는가**.

★기존 검사는 반대 방향만 봤다 — "메뉴에 있는데 누르면 404" 를 막았다
  (`configure_nav`, `test_module_toggles`). 그 반대인 **"화면은 있는데 메뉴에
  없다"** 는 아무도 안 봤고, 실제로 `/ops/outbox` 가 그 상태였다(2026-09-05 발견).

★왜 중요한가: `/ops/outbox` 는 `unknown` — **돈이 나갔는지 모르는** 메시지를
  다루는 화면이다. 이 제품에서 가장 센 위험이고 대응 절차서까지 있는데
  (`wiki/records/manuals/운영_unknown상태_대응절차.md`), 운영자가 주소를 직접 쳐야만
  갈 수 있었다. 갈 수 없는 화면으로는 절차를 밟을 수 없다.

  `final_project_sample` 에는 처음부터 메뉴에 있었다(`TENANT_NAV`) — 이식하며
  빠진 것이다.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.presentation.ui import mount_ui
from app.presentation.ui import theme

#: 목록·상세가 아니라 **사람이 시작점으로 여는** 화면. 상세(`/ui/cases/{id}`)는
#: 목록에서 들어가므로 메뉴에 없어도 된다.
ENTRY_SCREENS = {"/ui/cases", "/ui/approvals", "/ui/admin", "/ops/outbox", "/ui/voc"}


def _mounted_paths() -> set[str]:
    app = mount_ui(FastAPI())
    return {r.path for r in app.routes if getattr(r, "methods", None) and "GET" in r.methods}


def test_every_entry_screen_has_a_menu_entry():
    mounted = _mounted_paths()
    nav = {href for href, _ in theme.NAV}
    missing = sorted((ENTRY_SCREENS & mounted) - nav)
    assert not missing, (
        f"화면은 있는데 메뉴에 없다: {missing}. 운영자가 주소를 직접 쳐야 갈 수 있다 — "
        "메뉴에 넣거나, 시작점이 아니라면 ENTRY_SCREENS 에서 이유와 함께 빼라.")


def test_every_menu_entry_points_at_a_mounted_screen():
    """반대 방향 — 이건 이미 지켜지고 있었지만 함께 고정한다."""
    mounted = _mounted_paths()
    dangling = sorted(href for href, _ in theme.NAV if href not in mounted)
    assert not dangling, f"메뉴에 있는데 화면이 없다(누르면 404): {dangling}"


@pytest.mark.parametrize("path", sorted(ENTRY_SCREENS))
def test_the_entry_screen_is_actually_mounted(path):
    assert path in _mounted_paths(), f"{path} 가 등록되지 않았다"
