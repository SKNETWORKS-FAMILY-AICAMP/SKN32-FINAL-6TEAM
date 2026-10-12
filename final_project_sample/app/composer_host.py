"""이 제품이 Composer 패키지에 넘기는 것 — **호스트 어댑터**.

★위치가 `app/` 인 이유(2026-09-06 정정). 처음엔 `acop_basement/` 에 뒀는데,
  그러면 **cs 가 항상 설치하는 코어가 선택 패키지를 역으로 import** 한다 —
  Composer 를 안 깐 배포에서 이 모듈이 깨진다. 어댑터는 코어가 아니라 **제품
  조립부**의 것이다: 등록표(`IMPLEMENTATIONS`)가 `app.modules.*` 를 가리키는
  것만 봐도 제품 소유임이 드러난다. cs 도 자기 `app/composer_host.py` 를 쓴다.

★패키지(`acop_composer`)는 이제 이 저장소를 import 하지 않는다. 대신 호스트가
  자기 스키마·등록표·저장소·인증을 넘긴다(`acop_composer.host.ComposerHost`).
  `final_project_cs` 도 자기 것을 담은 같은 모양의 객체를 만들어 넘기면 된다.

★sample 도 **특별대우 없이** 이 길로 넘긴다. 참조 구현만 지름길을 쓰면
  "cs 에서도 된다" 가 말이 안 된다.

★**예외를 옮기는 것도 이 파일의 일이다.** 패키지는 `acop_composer.stores` 의
  `StoreError`·`RevisionMismatch` 를 잡는데 이 저장소의 저장소들은 자기 예외를
  던진다. 그대로 두면 `except` 가 **조용히 빗나가서** revision 충돌이 409 대신
  500 으로 나간다 — 1차 분리(커밋 `43d3f09`) 직후 실제로 그 상태였고
  2026-09-06 실측으로 확인했다. 어댑터가 경계에서 옮긴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acop_basement.core import settings as settings_module
from acop_basement.core.audit_store import (
    AuditStoreError, FileAuditStore, PostgresAuditStore,
)
from acop_basement.core.config_store import (
    ConfigStoreError, FileConfigStore, PostgresConfigStore,
    RevisionMismatch as HostRevisionMismatch,
)
from acop_basement.core.project_config import (
    DECLARATIVE_TEAM_REF,
    DeclarativeTeamParameters,
    ProjectConfigError,
    config_from_declaration,
)
from acop_basement.core.revision_store import (
    FileRevisionStore, PostgresRevisionStore, RevisionStoreError,
)
from acop_basement.infrastructure.db.session import get_connection
from acop_composer.host import AuthPolicy, ComposerHost, ConfigInvalid, Implementation
from acop_composer.stores import RevisionMismatch, StoreError, StoreTarget

REPO_ROOT = Path(__file__).resolve().parents[1]

#: JWT `aud`. ★호스트마다 달라야 한다 — sample 용 토큰이 cs 에서 통하면 안 된다.
AUDIENCE = "final_project_sample"

#: 이 저장소의 저장소들이 던지는 것 전부. 패키지 예외로 옮겨 준다.
_HOST_STORE_ERRORS = (ConfigStoreError, RevisionStoreError, AuditStoreError)


class _Codec:
    """이 저장소의 선언 스키마를 패키지가 쓸 수 있는 모양으로 감싼다."""

    def from_declaration(self, raw: dict[str, Any], *, source: str) -> Any:
        try:
            return config_from_declaration(raw, source=source)
        except ProjectConfigError as exc:
            # ★패키지는 이유를 만들지 않는다. 호스트가 만든 메시지를 그대로 옮긴다.
            raise ConfigInvalid(str(exc)) from exc

    def to_declaration(self, config: Any) -> dict[str, Any]:
        payload = config.model_dump(mode="json", exclude={"revision"})
        # ★코드형 Team 의 `parameters: null` 은 빼고 낸다 — 뜻은 같지만 토글 한 번에
        #   선언 파일마다 의미 없는 한 줄이 붙어 diff 가 지저분해진다(2026-08-31 실측).
        for team in payload.get("teams") or []:
            if team.get("parameters") is None:
                team.pop("parameters", None)
        return payload

    def revision(self, config: Any) -> str:
        return config.revision


def _translate(call):
    """호스트 저장소 예외 → 패키지 예외. ★`RevisionMismatch` 를 먼저 본다."""
    try:
        return call()
    except HostRevisionMismatch as exc:
        raise RevisionMismatch(exc.current_revision) from exc
    except _HOST_STORE_ERRORS as exc:
        raise StoreError(str(exc)) from exc


@dataclass(frozen=True)
class _TranslatingStore:
    """어떤 저장소든 감싸서 예외만 바꿔 준다.

    ★`path`·`deployment_id` 는 그대로 비쳐 보여야 한다 — 감사의 `subject` 가
      그걸 읽는다(`acop_composer.api._perform_change`).
    """

    inner: Any

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.inner, name)
        if not callable(attr):
            return attr

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return _translate(lambda: attr(*args, **kwargs))

        return wrapped


class _Stores:
    """선언·이력·감사를 어디에 둘 것인가 — **이 저장소의 정책**이다.

    ★설정이 중앙 저장소를 가리키면 셋 다 중앙에 둔다. 선언만 중앙으로 옮기고
      감사를 대상마다의 파일에 두면, 누가 무엇을 바꿨는지가 수천 군데로 흩어져
      감사로서 쓸모가 없다(`program/plan/A-COP_Composer_중앙설정저장소_결정.md`).
    """

    @staticmethod
    def _central(target: StoreTarget) -> bool:
        if target.central is not None:
            # ★부른 쪽이 지목했다. 호스트 설정이 이를 뒤집지 않는다.
            return target.central
        return settings_module.get_settings().config_source == "central"

    def config_store(self, target: StoreTarget):
        if self._central(target):
            return _TranslatingStore(PostgresConfigStore(get_connection, target.deployment_id))
        return _TranslatingStore(FileConfigStore(target.config_path))

    def revision_store(self, target: StoreTarget):
        if self._central(target):
            return _TranslatingStore(PostgresRevisionStore(get_connection, target.deployment_id))
        return _TranslatingStore(FileRevisionStore(target.revisions_path))

    def audit_store(self, target: StoreTarget):
        if self._central(target):
            return _TranslatingStore(PostgresAuditStore(get_connection, target.deployment_id))
        return _TranslatingStore(FileAuditStore(target.audit_path))


def _validate_parameters(raw: dict[str, Any]) -> None:
    DeclarativeTeamParameters.model_validate(raw)


#: 이 제품이 실제로 등록한 구현. ★`final_project_cs` 는 자기 여섯 개를 넣는다.
IMPLEMENTATIONS: tuple[Implementation, ...] = (
    Implementation(
        id="team.declarative.v1",
        ref=DECLARATIVE_TEAM_REF,
        display_name="선언형 Team",
        description="코드 없이 이름·역할·프롬프트·도구 목록만으로 만드는 Team. 읽기 전용이다.",
        parameters_schema=DeclarativeTeamParameters.model_json_schema(),
    ),
    Implementation(
        id="team.feedback_analytics",
        ref="app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
        display_name="피드백 분석 Team",
        description="VOC 분류·집계 배치를 감싼다.",
    ),
    Implementation(
        id="team.placeholder",
        ref="app.modules.placeholder:PlaceholderTeam",
        display_name="자리표시 Team",
        description="구조 검증용 최소 구현.",
    ),
)


def _auth_policy() -> AuthPolicy:
    """★비밀을 **값이 아니라 함수**로 넘긴다 — 프로세스가 뜬 뒤 설정이 바뀌어도
    따라가고, 이 객체를 로깅해도 비밀이 안 샌다."""
    return AuthPolicy(
        audience=AUDIENCE,
        jwt_secret=lambda: settings_module.get_settings().composer_jwt_secret,
        # ★서명 비밀과 **다른 값**이다. 발급 자격과 토큰 검증은 다른 일이다.
        issuer_secret=lambda: settings_module.get_settings().composer_issuer_secret,
        configured_scopes=lambda: frozenset(
            settings_module.get_guardrails().get("security.scopes")),
        ttl_minutes=lambda: int(
            settings_module.get_guardrails().get("security.composer_jwt_ttl_minutes")),
    )


def composer_host() -> ComposerHost:
    """이 저장소용 `ComposerHost`."""
    from acop_basement.core.project_config import DEFAULT_PROJECT_CONFIG

    return ComposerHost(
        codec=_Codec(),
        implementations=IMPLEMENTATIONS,
        stores=_Stores(),
        auth=_auth_policy(),
        default_config_path=Path(DEFAULT_PROJECT_CONFIG),
        # ★`parents[N]` 을 세지 않는다 — 2026-09-06 에 그걸 잘못 세어 감사·이력이
        #   저장소 **밖**(Documents/var/audit)으로 쌓이고 있었다(감사 9건·이력 62건).
        audit_dir=REPO_ROOT / "var" / "audit",
        default_deployment_id=lambda: settings_module.get_settings().deployment_id,
    )


__all__ = ["AUDIENCE", "IMPLEMENTATIONS", "composer_host"]
