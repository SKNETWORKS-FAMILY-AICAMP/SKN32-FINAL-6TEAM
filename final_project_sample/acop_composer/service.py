"""구성 선언(`config/project.yaml`)을 검증하고 쓰는 유일한 통로.

★왜 필요한가 — Composer 는 basement 에 남는 유일한 **쓰기** 기능이다.
  `final_project_ui` 는 read-only 원칙(§0.3)을 지키므로 이 저장소를 직접 못 쓴다.
  그런데 릴리스 이후 우리가 콘솔을 다시 붙여 **모듈을 켜고 끄는 작업**을 하려면
  쓰기 채널이 있어야 한다. 이 파일이 그 채널의 실체다:

      /ui/composer 의 HTML 폼            ← 로컬 개발자용. composer_ui 로 끌 수 있다
      /composer/validate, /composer/apply ← 이 서비스를 호출한다. **module 토글과 무관**
                                             하게 항상 존재한다 — HTML 페이지가 꺼져도
                                             릴리스 이후 콘솔이 이 API 로 계속 쓴다.

  둘 다 **이 파일 하나만** 실제로 파일을 건드린다. HTML 라우터가 자기 파일 I/O 를
  갖고 있었던 것(예전 `composer.py`)이 문제였다 — 검증·저장 정책이 화면에 흩어졌다.

★Codex 교차검증(`docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`)이 잡은 것:
  1. 고정된 임시 파일명(`.composer.validation.yaml`) — 동시 요청이 서로의 후보를 덮어썼다
  2. revision 확인 없이 즉시 썼다 — "마지막에 쓴 사람이 이긴다" 가 조용히 일어났다
  3. 파일 교체가 원자적이지 않았다 — 쓰다가 죽으면 반쪽 YAML 이 남을 수 있었다
  이 파일이 그 세 가지를 고친다.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from acop_composer.stores import (
    ConfigStore, RevisionMismatch, RevisionStore, StoreTarget,
)
from acop_composer.host import ComposerHost, ConfigInvalid, HostIncomplete

#: ★단일 프로세스 안에서만 동시 쓰기를 막는다. 여러 워커·여러 인스턴스에 걸친
#:  잠금은 아직 없다 — 지금은 로컬 단일 개발자 도구다. 인스턴스 레지스트리가
#:  생기면(§4 후속 과제) 파일 lock 이나 DB 조건부 쓰기로 넓혀야 한다.
_WRITE_LOCK = threading.Lock()


class RevisionConflict(RuntimeError):
    """제출된 base_revision 이 현재 파일의 revision 과 다르다."""

    def __init__(self, current_revision: str) -> None:
        self.current_revision = current_revision
        super().__init__(f"revision conflict: current is {current_revision}")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    config: Any | None
    errors: list[str]


def _validate_http_registry(raw: dict[str, Any], host: ComposerHost) -> list[str]:
    """HTTP 로 들어온 선언이 **이 호스트가 등록한 구현만** 쓰는지 본다.

    ★allowlist 는 호스트가 준다. 2026-09-06 이전에는 이 파일이 sample 코어의
      `KNOWN_IMPLEMENTATION_REFS` 를 직접 import 했다 — 그대로 다른 제품에
      설치하면 그 제품의 Team 이 전부 "미등록" 으로 거부된다.
    """
    teams = raw.get("teams")
    if not isinstance(teams, list):
        return []
    errors: list[str] = []
    for index, team in enumerate(teams):
        if not isinstance(team, dict) or team.get("active") is not True:
            continue
        ref = team.get("implementation_ref")
        if ref not in host.known_refs:
            errors.append(
                f"team '{team.get('team_id', index)}' implementation_ref '{ref}' "
                "is not registered in the implementation registry"
            )
    return errors


def _store_for(path: str | Path | None, store: ConfigStore | None,
               host: ComposerHost) -> ConfigStore:
    """어디에 쓸 것인가 — 주입된 저장소, 없으면 파일.

    ★중앙 설정 저장소로 옮기는 중이다
      (`program/plan/A-COP_Composer_중앙설정저장소_결정.md`). 파일이 기본값인
      이유는 하위호환 때문이다 — 기존 배포·테스트가 그대로 돌아야 한다.
    """
    if store is not None:
        return store
    if host.stores is None:
        raise HostIncomplete(
            "저장소가 없다 — 호스트가 `store` 를 주거나 `stores` 를 넘겨야 한다")
    # ★`central=False` 다. 경로를 지목해 부른 것이므로 호스트 설정이 이를
    #   뒤집어 중앙 DB 를 열면 안 된다 — 부른 쪽이 말한 파일을 다룬다.
    return host.stores.config_store(
        StoreTarget(config_path=Path(path or host.default_config_path), central=False))


def read_current(host: ComposerHost, path: str | Path | None = None, *,
                 store: ConfigStore | None = None) -> Any:
    """현재 선언. ★검증은 **호스트 스키마**가 한다 — 패키지는 구조를 모른다."""
    source = _store_for(path, store, host)
    return host.codec.from_declaration(source.read(), source="<store>")


def validate_candidate(raw: dict[str, Any], host: ComposerHost, *,
                       path: str | Path | None = None,
                       store: ConfigStore | None = None,
                       enforce_registry: bool = False) -> ValidationResult:
    """후보 선언을 검증만 한다. **저장하지 않는다.**

    ★canonical loader(`load_project_config`)를 그대로 쓴다 — 별도 검증기를 만들지
      않는다. 검증기가 실제 로더와 다르면 "검증은 통과했는데 기동은 실패" 가 생긴다.
      스키마·활성 Team import·Port 호환성까지 여기서 전부 확인된다.
    """
    registry_errors = _validate_http_registry(raw, host) if enforce_registry else []
    if registry_errors:
        return ValidationResult(valid=False, config=None, errors=registry_errors)
    try:
        # ★2026-08-29 — 예전에는 후보를 임시 파일로 쓴 뒤 그 파일을 로더에
        #   먹였다. 지금은 `config_from_declaration()` 이 같은 검증을 파일 없이
        #   한다. 검증기가 둘이 되는 것은 아니다 — **같은 함수**를 쓴다.
        #   덤으로 "검증만 했는데 디스크에 임시 파일이 생긴다" 는 성질이 사라져,
        #   검증이 대상 디렉터리에 쓰기 권한을 요구하지 않게 됐다(중앙 저장소
        #   모드에서는 애초에 그런 디렉터리가 없다).
        config = host.codec.from_declaration(raw, source="<candidate>")
        return ValidationResult(valid=True, config=config, errors=[])
    except ConfigInvalid as exc:
        return ValidationResult(valid=False, config=None, errors=[str(exc)])


def apply_candidate(raw: dict[str, Any], host: ComposerHost, *, base_revision: str,
                    path: str | Path | None = None,
                    store: ConfigStore | None = None,
                    enforce_registry: bool = False,
                    history: RevisionStore | None = None,
                    actor: str = "", reason: str = "",
                    event: str = "apply") -> Any:
    """검증에 통과하면 **원자적으로, revision 이 맞을 때만** 쓴다.

    ★검증(validate)과 별개로 다시 한다 — 사람이 "검증" 버튼을 누른 뒤 "적용" 을
      누르는 사이에도 남이 파일을 바꿀 수 있다. 여기서 다시 확인한다.

    ★`history` 를 주면 **쓴 직후 같은 잠금 아래에서** 이력을 한 줄 남긴다
      (D-011, 2026-09-06). 쓰기 경로가 이 함수 하나뿐이라 여기서 한 번만 적으면
      `/apply`·`/changes`·`/toggle`·`/restore` 전부의 이력이 빠짐없이 남는다.
      첫 기록이면 **직전 상태를 `baseline` 으로 먼저** 남긴다 — 그래야 첫 변경
      직후에도 "이전 revision 으로 되돌리기" 가 성립한다.

    raises:
        RevisionConflict — 지금 파일의 revision 이 base_revision 과 다르다
        ConfigInvalid — 후보가 유효하지 않다(호스트 스키마가 거부했다)
        RevisionStoreError — 저장은 됐는데 이력을 못 남겼다(호출부가 500 으로 올린다)
    """
    target_store = _store_for(path, store, host)
    with _WRITE_LOCK:
        registry_errors = _validate_http_registry(raw, host) if enforce_registry else []
        if registry_errors:
            raise ConfigInvalid("; ".join(registry_errors))
        # ★lock 을 잡은 뒤 다시 읽는다 — lock 밖에서 읽은 revision 은 이미 낡았을 수 있다.
        #   ★중앙 저장소에서는 이 프로세스 락만으로 부족하다. 그래서 아래
        #   `store.write()` 가 **저장소에서 조건부로** 다시 검사한다(CAS).
        current_raw = target_store.read()
        current = host.codec.from_declaration(current_raw, source="<current>")
        current_revision = host.codec.revision(current)
        if current_revision != base_revision:
            raise RevisionConflict(current_revision)

        # 실패하면 여기서 던진다 — 저장소를 건드리기 전이다.
        candidate = host.codec.from_declaration(raw, source="<candidate>")
        try:
            target_store.write(raw, base_revision=base_revision,
                               new_revision=host.codec.revision(candidate))
        except RevisionMismatch as exc:
            # 저장소가 최종 판정자다. 위 검사를 통과했어도 그 사이 남이 썼을 수 있다.
            raise RevisionConflict(exc.current_revision) from exc
        if history is not None:
            _record_history(history, previous_raw=current_raw, previous_revision=current_revision,
                            raw=raw, revision=host.codec.revision(candidate),
                            actor=actor, reason=reason, event=event)
        return candidate


def _record_history(history: RevisionStore, *, previous_raw: dict[str, Any],
                    previous_revision: str, raw: dict[str, Any], revision: str,
                    actor: str, reason: str, event: str) -> None:
    """이력 한 줄. 직전 상태가 이력에 없으면 그것부터 `baseline` 으로 남긴다."""
    stamp = _utc_now()
    if history.find(previous_revision) is None:
        history.append({
            "revision": previous_revision, "previous_revision": None,
            "declaration": previous_raw, "actor": "system",
            "reason": "baseline — 첫 이력 직전의 상태", "event": "baseline",
            "timestamp": stamp,
        })
    history.append({
        "revision": revision, "previous_revision": previous_revision,
        "declaration": raw, "actor": actor, "reason": reason, "event": event,
        "timestamp": stamp,
    })


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
