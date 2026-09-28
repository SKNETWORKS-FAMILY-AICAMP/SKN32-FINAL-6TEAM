"""등록된 운영 UI 화면이 **메뉴에서 닿는가** (cs 에서 찾은 결함의 대칭 검사).

★기존 검사는 한 방향만 봤다 — "메뉴에 있는데 누르면 404". 그 반대인
  **"화면은 있는데 메뉴에 없다"** 는 아무도 안 봤고, `final_project_cs` 에서
  실제로 `/ops/outbox` 가 그 상태였다(2026-09-05 발견, cs 커밋 `04b3cd8`).

  이 저장소는 그때 이미 옳았다(`TENANT_NAV` 에 "Outbox unknown" 이 있다). 참조
  구현이 맞았고 이식 쪽이 빠뜨린 것이다. **맞는 상태를 고정해 둔다** — 다음에
  여기서 빠지면 cs 로 또 옮겨간다.

★왜 `/ops/outbox` 가 특히 중요한가: `unknown` 은 provider 응답을 못 받아
  **돈이 나갔는지 모르는** 상태다. 이 제품에서 가장 센 위험이고, 갈 수 없는
  화면으로는 대응 절차를 밟을 수 없다.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from acop_basement.presentation.ui import mount_ui
from acop_basement.presentation.ui import theme

#: 사람이 **시작점으로 여는** 화면. 상세(`/ops/cases/{id}`)는 목록에서 들어가므로
#: 메뉴에 없어도 된다.
ENTRY_SCREENS = {"/ops/cases", "/ops/approvals", "/ops/outbox", "/ops/voc"}


def _mounted_paths() -> set[str]:
    app = mount_ui(FastAPI())
    return {r.path for r in app.routes if getattr(r, "methods", None) and "GET" in r.methods}


def test_every_entry_screen_has_a_menu_entry():
    missing = sorted((ENTRY_SCREENS & _mounted_paths()) - {href for href, _ in theme.NAV})
    assert not missing, (
        f"화면은 있는데 메뉴에 없다: {missing}. 운영자가 주소를 직접 쳐야 간다 — "
        "메뉴에 넣거나, 시작점이 아니라면 ENTRY_SCREENS 에서 이유와 함께 빼라.")


def test_every_menu_entry_points_at_a_mounted_screen():
    dangling = sorted(href for href, _ in theme.NAV if href not in _mounted_paths())
    assert not dangling, f"메뉴에 있는데 화면이 없다(누르면 404): {dangling}"


@pytest.mark.parametrize("path", sorted(ENTRY_SCREENS))
def test_the_entry_screen_is_actually_mounted(path):
    assert path in _mounted_paths(), f"{path} 가 등록되지 않았다"
