"""대상이 **자기가 등록한 구현**을 UI 에 알려 준다.

★UI 는 `implementation_id` 만 주고받는다. Python 경로(`implementation_ref`)를
  UI 가 알면 그 순간 결합이 생기고, 대상이 구현을 옮길 때마다 UI 를 고쳐야 한다.

★목록은 **호스트가 넘긴다**(`ComposerHost.implementations`). 2026-09-06 이전에는
  이 파일이 `acop_basement`(sample 의 코어)를 직접 import 해 sample 의 Team 셋을
  하드코딩했다 — 그대로 `final_project_cs` 에 설치하면 cs 의 Team 여섯이 전부
  "미등록" 422 가 난다. 등록표는 제품마다 다르므로 패키지가 가질 수 없다.
"""
from __future__ import annotations

from typing import Any

from acop_composer.host import ComposerHost


class CatalogError(RuntimeError):
    """UI 가 보낸 `implementation_id` 를 이 호스트가 등록하지 않았다."""


def ref_for(host: ComposerHost, implementation_id: str) -> str:
    """`implementation_id` → `implementation_ref`.

    ★모르는 id 는 거부한다. 이게 HTTP 경로로 임의 모듈을 import 시키지 못하게
      하는 allowlist 다(보안 규칙이다).
    """
    try:
        return host.implementation(implementation_id).ref
    except KeyError as exc:
        known = ", ".join(sorted(item.id for item in host.implementations)) or "(없음)"
        raise CatalogError(
            f"등록되지 않은 구현이다: {implementation_id} (가능한 것: {known})") from exc


def id_for(host: ComposerHost, implementation_ref: str) -> str | None:
    """`implementation_ref` → `implementation_id`. 모르면 `None`(모름)이다."""
    for item in host.implementations:
        if item.ref == implementation_ref:
            return item.id
    return None


def team_entries(host: ComposerHost) -> list[dict[str, Any]]:
    """이 호스트가 등록한 Team 구현 목록."""
    return [{
        "implementation_id": item.id,
        "kind": "team",
        "display_name": item.display_name,
        "description": item.description,
        "parameters_schema": item.parameters_schema,
        "requires_restart": True,
    } for item in sorted(host.implementations, key=lambda i: i.id)]


def module_entries(declared_modules: dict[str, Any]) -> list[dict[str, Any]]:
    """모듈은 이 프로젝트가 **실제로 선언한 것**만 낸다.

    ★모듈 구현 목록은 product 의 조립 루트가 갖는다. 패키지가 그걸 import 하면
      선택 패키지가 product 조립부에 묶인다 — 그래서 현재 선언에 있는 키만 낸다.
      "이 프로젝트가 켜고 끌 수 있는 것" 이라는 뜻이라 UI 에는 이게 더 정확하다.
    """
    return [{
        "implementation_id": f"module.{name}",
        "kind": "module",
        "display_name": name,
        "description": "",
        "parameters_schema": None,
        "requires_restart": True,
    } for name in sorted(declared_modules)]


__all__ = ["CatalogError", "ref_for", "id_for", "team_entries", "module_entries"]
