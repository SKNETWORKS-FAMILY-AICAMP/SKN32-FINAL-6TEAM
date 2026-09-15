"""Composer 가 쓰는 저장소의 **모양**만 정의한다 — 구현은 호스트가 넘긴다.

★왜 Protocol 만인가. 구현(`FileConfigStore`·`PostgresConfigStore` 등)은 호스트
  코어에 남는다. `final_project_sample` 의 대상 런타임이 중앙 모드에서 **자기
  선언을 읽을 때** 같은 구현을 쓰기 때문이다
  (`acop_basement/application/config_source.py`). 구현을 이 패키지로 올리면
  호스트가 선택 패키지를 역으로 의존하게 되고, **Composer 를 안 깔면 대상이
  중앙에서 설정을 못 읽는다** — 결합 방향이 뒤집힌다(2026-09-06 판단).

★그래서 패키지는 "이런 모양이면 된다" 만 말하고, 무엇을 쓸지는 호스트가 정한다.
  `final_project_cs` 는 자기 구현을 넘기면 된다.

★**예외도 계약이다**(2026-09-06 실측으로 확인한 결함). 여기 있는 `StoreError` ·
  `RevisionMismatch` 를 패키지가 잡는데 호스트 저장소가 자기 예외를 던지면
  `except` 가 **조용히 빗나간다** — revision 충돌이 409 대신 500 으로 나간다.
  실제로 1차 분리(커밋 `43d3f09`) 직후 그 상태였다. 호스트 어댑터가 자기 예외를
  이 모양으로 옮겨 주어야 한다(`app/composer_host.py` 의 `_translate`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class StoreError(RuntimeError):
    """저장소가 요청을 수행하지 못했다. 호스트 예외를 이 모양으로 올린다."""


class RevisionMismatch(StoreError):
    """조건부 쓰기가 거부됐다 — 그 사이 남이 썼다.

    ★저장소가 **최종 판정자**다. 프로세스 락을 통과했어도 여기서 질 수 있다.
    """

    def __init__(self, current_revision: str) -> None:
        super().__init__(f"revision mismatch: {current_revision}")
        self.current_revision = current_revision


@dataclass(frozen=True)
class StoreTarget:
    """"이 요청이 어느 선언을 다루는가" — 패키지가 아는 것 전부.

    ★**어디에 있는가는 호스트가 정한다.** 패키지는 대상만 말하고, 파일이냐
      중앙 DB 냐는 `StoreProvider` 가 자기 설정을 보고 고른다.
    """

    #: 이 요청이 다루는 대상. 파일 모드에서는 쓰이지 않을 수 있다.
    deployment_id: str = ""
    #: `None` = 호스트 설정이 정한다 · `True` = 중앙 · `False` = 파일로 강제.
    #: ★`False` 는 라이브러리로 직접 부를 때(경로를 준 경우) 쓴다 — 그때는
    #:  부른 쪽이 파일을 지목한 것이므로 호스트 설정이 이를 뒤집으면 안 된다.
    central: bool | None = None
    #: 파일 모드일 때 선언 파일. 없으면 호스트 기본값.
    config_path: Path | None = None
    #: 파일 모드일 때 이력 JSONL.
    revisions_path: Path | None = None
    #: 파일 모드일 때 감사 JSONL.
    audit_path: Path | None = None


class ConfigStore(Protocol):
    """선언을 읽고 **조건부로** 쓴다."""

    def read(self) -> dict[str, Any]:
        """현재 선언(raw dict). 대상이 등록돼 있지 않으면 `StoreError`."""

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        """`base_revision` 이 맞을 때만 쓴다. 아니면 `RevisionMismatch`."""


class RevisionStore(Protocol):
    """선언 이력. ★append-only 다 — 고치거나 지우지 않는다."""

    def append(self, entry: dict[str, Any]) -> None: ...

    def recent(self, limit: int) -> list[dict[str, Any]]: ...

    def find(self, revision: str) -> dict[str, Any] | None: ...


class AuditStore(Protocol):
    """누가 언제 무엇을 바꿨는가. ★append-only 다."""

    def append(self, event: dict[str, Any]) -> None: ...

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None: ...


class StoreProvider(Protocol):
    """호스트가 "이 대상의 저장소는 이것" 이라고 답한다.

    ★파일이냐 중앙이냐를 **여기서** 고른다. 그 판단은 호스트 설정
      (`config_source`)에 달려 있고, 패키지는 그 설정을 읽지 않는다.
    """

    def config_store(self, target: StoreTarget) -> ConfigStore: ...

    def revision_store(self, target: StoreTarget) -> RevisionStore: ...

    def audit_store(self, target: StoreTarget) -> AuditStore: ...


__all__ = [
    "AuditStore", "ConfigStore", "RevisionMismatch", "RevisionStore",
    "StoreError", "StoreProvider", "StoreTarget",
]
