"""UI 가 고를 수 있는 구현 종류의 카탈로그.

★**Python 경로를 UI 에 노출하지 않는다.** UI 는 `implementation_id`(안정된
  문자열)만 보고, ID↔경로 매핑은 이 서버 안에만 있다. 경로를 노출하면 UI 가
  대상의 내부 모듈 구조에 묶이고, 원격 요청 문자열이 곧 import 경로가 되는
  위험한 경로가 열린다(`docs/handoff/13` v2 가 registry allowlist 를 둔 이유).

★매핑은 **명시 선언**이다. `KNOWN_IMPLEMENTATION_REFS` 에 새 구현이 늘었는데
  여기 ID 가 없으면 조용히 빠뜨리지 않고 시작 시점에 터진다 — 카탈로그에
  안 뜨는 구현은 UI 에서 영원히 못 고르므로, 조용한 누락이 가장 나쁘다.
"""
from __future__ import annotations

from typing import Any

from acop_basement.core.project_config import (
    DECLARATIVE_TEAM_REF,
    KNOWN_IMPLEMENTATION_REFS,
    DeclarativeTeamParameters,
)

#: implementation_id → implementation_ref (Python 경로).
IMPLEMENTATION_IDS: dict[str, str] = {
    "team.declarative.v1": DECLARATIVE_TEAM_REF,
    "team.feedback_analytics": "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
    "team.placeholder": "app.modules.placeholder:PlaceholderTeam",
}

#: 사람이 읽는 설명. ID 와 분리해 둬야 설명을 고쳐도 ID 가 안 흔들린다.
_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "team.declarative.v1": (
        "선언형 Team",
        "코드 없이 이름·역할·프롬프트·도구 목록만으로 만드는 Team. 읽기 전용이다.",
    ),
    "team.feedback_analytics": ("피드백 분석 Team", "VOC 분류·집계 배치를 감싼다."),
    "team.placeholder": ("자리표시 Team", "구조 검증용 최소 구현."),
}


class CatalogError(RuntimeError):
    """카탈로그와 등록 구현 목록이 어긋났다."""


def _assert_complete() -> None:
    """등록됐는데 ID 가 없는 구현이 있으면 즉시 실패한다."""
    missing = sorted(set(KNOWN_IMPLEMENTATION_REFS) - set(IMPLEMENTATION_IDS.values()))
    if missing:
        raise CatalogError(
            "카탈로그에 implementation_id 가 없는 등록 구현이 있다: " + ", ".join(missing))


def ref_for(implementation_id: str) -> str:
    """ID 를 Python 경로로 바꾼다. 모르는 ID 는 거부한다."""
    try:
        return IMPLEMENTATION_IDS[implementation_id]
    except KeyError as exc:
        raise CatalogError(f"unknown implementation_id: {implementation_id}") from exc


def id_for(implementation_ref: str) -> str | None:
    """경로를 ID 로 되돌린다. 카탈로그 밖이면 None(=UI 에 안 보인다)."""
    for identifier, ref in IMPLEMENTATION_IDS.items():
        if ref == implementation_ref:
            return identifier
    return None


def team_entries() -> list[dict[str, Any]]:
    _assert_complete()
    entries: list[dict[str, Any]] = []
    for identifier, ref in sorted(IMPLEMENTATION_IDS.items()):
        display_name, description = _DESCRIPTIONS.get(identifier, (identifier, ""))
        entries.append({
            "implementation_id": identifier,
            "kind": "team",
            "display_name": display_name,
            "description": description,
            # ★선언형만 입력 스키마가 있다. 코드형은 인스턴스마다 설정할 값이
            #   없다 — 그래서 null 이고, UI 는 이름만 받으면 된다.
            "parameters_schema": (DeclarativeTeamParameters.model_json_schema()
                                  if ref == DECLARATIVE_TEAM_REF else None),
            # ★조립은 프로세스 기동 때 한 번만 일어난다(`app/composition.py`).
            #   그래서 무엇을 바꾸든 지금은 재시작이 필요하다.
            "requires_restart": True,
        })
    return entries


def module_entries(declared_modules: dict[str, Any]) -> list[dict[str, Any]]:
    """모듈은 이 프로젝트가 **실제로 선언한 것**만 낸다.

    ★모듈 구현 목록은 product 의 조립 루트(`app/composition.py` 의
      `_MODULE_IMPLEMENTATIONS`)가 갖는다. `acop_composer` 가 그걸 import 하면
      선택 패키지가 product 조립부에 묶인다 — 그래서 import 하지 않고, 현재
      선언에 있는 키만 낸다. "이 프로젝트가 켜고 끌 수 있는 것"이라는 뜻이라
      UI 에는 이게 더 정확하다.
    """
    return [{
        "implementation_id": f"module.{name}",
        "kind": "module",
        "display_name": name,
        "description": "",
        "parameters_schema": None,
        "requires_restart": True,
    } for name in sorted(declared_modules)]


__all__ = ["IMPLEMENTATION_IDS", "CatalogError", "ref_for", "id_for",
           "team_entries", "module_entries"]
