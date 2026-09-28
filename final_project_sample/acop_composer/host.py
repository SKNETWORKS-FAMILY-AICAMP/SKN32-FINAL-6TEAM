"""호스트가 Composer 에게 넘기는 것들 — **패키지가 남의 저장소를 import 하지 않게** 한다.

★왜 필요한가. 이 패키지는 `final_project_cs` 같은 다른 제품에 pip 로 설치돼야
  한다. 그런데 지금까지는 `acop_basement`(sample 의 런타임 코어)를 직접 import
  했다. 그대로 cs 에 설치하면 셋이 깨진다:

    1. **등록표가 남의 것이다** — 패키지가 sample 의 `KNOWN_IMPLEMENTATION_REFS`
       를 보므로 cs 의 Team 여섯은 전부 "미등록" 422 가 난다
    2. **스키마가 남의 것이다** — sample 의 `ProjectConfig` 로 검증하는데
       `extra="forbid"` 라, cs 선언의 `response_review` 같은 칸에서 바로 실패한다
    3. **코어가 두 벌 들어간다** — 설정·DB 세션·저장소·인증을 전부 sample 코어에서
       가져오므로, cs 에 설치하면 런타임이 둘이 된다

★그래서 **호스트가 자기 것을 넘긴다.** 패키지는 이 객체가 준 것만 쓴다.
  sample 도 이제 다른 호스트와 똑같이 자기 것을 넘겨서 쓴다 — 특별대우가 없어야
  "cs 에서도 된다" 가 말이 된다.

★**막연한 `settings()` 를 넘기지 않는다**(2026-09-06 정정). 처음에는 호스트의
  설정 객체를 통째로 넘겼는데, 그러면 패키지가 `settings().composer_jwt_secret`
  처럼 **속성 이름**에 의존한다 — 계약이 어디에도 안 적힌 채 생긴다. 필요한 것을
  이름으로 물어보게 바꿨다. 그래야 cs 가 무엇을 채워야 하는지 이 파일만 보고 안다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from acop_composer.stores import StoreProvider


class ConfigCodec(Protocol):
    """호스트의 **선언 스키마**. 패키지는 구조를 모르고 이것만 부른다."""

    def from_declaration(self, raw: dict[str, Any], *, source: str) -> Any:
        """raw dict 를 검증된 선언 객체로. 실패하면 `ConfigInvalid` 를 올린다."""

    def to_declaration(self, config: Any) -> dict[str, Any]:
        """검증된 선언 객체를 raw dict 로(저장·비교·응답에 쓴다)."""

    def revision(self, config: Any) -> str:
        """선언 **내용**에서 나오는 revision. 파일 mtime 이나 커밋이 아니다."""


@dataclass(frozen=True)
class Implementation:
    """카탈로그 한 줄. ★`implementation_id` 는 계약이고 `ref` 는 구현 상세다.

    UI 는 `id` 만 주고받는다 — Python 경로를 UI 가 알면 그 순간 결합이 생긴다.
    """

    id: str
    ref: str
    display_name: str
    description: str
    parameters_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class AuthPolicy:
    """토큰 발급·검증에 필요한 것. ★비밀은 **값이 아니라 함수**로 받는다 —
    프로세스가 뜬 뒤 설정이 바뀌어도 따라가고, 이 객체를 로깅해도 비밀이 안 샌다.
    """

    #: JWT `aud`. 호스트마다 다르다 — cs 토큰이 sample 에서 통하면 안 된다.
    audience: str
    #: 발급·검증에 쓰는 서명 비밀
    jwt_secret: Callable[[], str]
    #: `/auth/token` 을 부를 자격(발급자 인증). ★서명 비밀과 **다른 값**이다.
    issuer_secret: Callable[[], str]
    #: 이 호스트에 존재하는 scope 전부. 없는 scope 를 담은 토큰은 발급하지 않는다.
    configured_scopes: Callable[[], frozenset[str]]
    #: 토큰 수명(분)
    ttl_minutes: Callable[[], int]


@dataclass(frozen=True)
class ComposerHost:
    """Composer 라우터를 만들 때 호스트가 넘기는 것 전부.

    ★여기 없는 것을 패키지가 쓰면 그게 곧 결합이다. 늘어나면 그 자체가 신호다.
    """

    #: 선언 검증·직렬화·revision — 호스트의 스키마
    codec: ConfigCodec
    #: 이 제품이 실제로 등록한 구현 목록. **호스트마다 다르다.**
    implementations: tuple[Implementation, ...] = ()
    #: 선언·이력·감사를 어디에 둘지 호스트가 답한다
    stores: StoreProvider | None = None
    #: 토큰 발급·검증 정책. 없으면 인증 라우터를 만들 수 없다.
    auth: AuthPolicy | None = None
    #: 선언 파일 기본 경로(파일 모드일 때)
    default_config_path: Path | None = None
    #: 감사·이력 파일이 놓일 폴더(파일 모드일 때). ★호스트 저장소 **안**이어야
    #:  한다 — 2026-09-06 에 `parents[N]` 을 잘못 세어 저장소 밖에 쌓고 있었다.
    audit_dir: Path | None = None
    #: 단일 대상 빌드에서 "이 프로세스가 관리하는 대상". 설정 서비스 모드에서는
    #: 요청 헤더가 대상을 지정하므로 쓰이지 않는다.
    default_deployment_id: Callable[[], str] | None = None
    #: 부가 정보(호스트가 필요하면 채운다). 패키지는 읽지 않는다.
    extra: dict[str, Any] = field(default_factory=dict)

    def implementation(self, implementation_id: str) -> Implementation:
        for item in self.implementations:
            if item.id == implementation_id:
                return item
        raise KeyError(implementation_id)

    @property
    def known_refs(self) -> frozenset[str]:
        """이 호스트가 등록한 `implementation_ref` 전부.

        ★HTTP 경로로 임의 모듈을 import 시키지 못하게 하는 allowlist 다
          (보안 규칙이지 도메인 지식이 아니다).
        """
        return frozenset(item.ref for item in self.implementations)


class ConfigInvalid(ValueError):
    """호스트 스키마가 선언을 거부했다. 패키지는 이유를 만들지 않고 전달만 한다."""


class HostIncomplete(RuntimeError):
    """호스트가 이 경로에 필요한 것을 안 넘겼다.

    ★조용히 기본값으로 떨어지지 않는다. 기본값으로 떨어지면 **남의 설정을
      건드리거나** 검증 없이 지나가는 사고가 소리 없이 일어난다.
    """


__all__ = [
    "AuthPolicy", "ComposerHost", "ConfigCodec", "ConfigInvalid",
    "HostIncomplete", "Implementation",
]
