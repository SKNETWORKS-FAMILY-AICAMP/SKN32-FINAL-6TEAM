"""Typed, fail-fast loader for the project composition declaration."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import os
import importlib
import json
from pathlib import Path
import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
#: ★환경변수로 선언 파일을 바꿀 수 있다. 테스트·로컬 실험에서 여러 형상을
#:  동시에 띄울 때 쓴다. ★기본값은 그대로다 — 환경변수가 없으면 달라지지 않는다.
DEFAULT_PROJECT_CONFIG = Path(
    os.environ.get("ACOP_PROJECT_CONFIG") or (REPO_ROOT / "config" / "project.yaml"))

# HTTP Composer candidates may select only implementations explicitly known to
# this application.  The canonical loader remains intentionally unchanged for
# trusted local file editing paths.
#
# ★버그사냥 2026-08-18 — 이전 판은 두 항목을 문자열 조각을 이어붙여
#   ("Billing" + "Sub" + "scriptionTeam") 만들었다. 도메인 클래스명을 그대로
#   쓰면 `tests/architecture/test_basement_is_domain_free.py` 가 부분
#   문자열("subscription"/"entitlement")로 잡아내는데, 조각을 나눠서 그
#   검사를 피해 간 것이다 — 검사를 우회한 것이지 basement 순수성을 지킨
#   게 아니다. 두 Team 이 `examples/`로 옮겨져(더 이상 production Team이
#   아님) `app/modules/customer_ops`에서 import 자체가 안 되므로, 이 참조는
#   지금 시점엔 죽은 항목이기도 하다 — 삭제로 두 문제(우회·죽은 참조)를
#   한 번에 없앤다.
#: 선언형 Team 실행기의 registry 경로. 이 값을 `implementation_ref` 로 쓰는
#: 선언만 `parameters` 를 가질 수 있다.
DECLARATIVE_TEAM_REF = "acop_basement.teams.declarative:DeclarativeTeamRuntime"

KNOWN_IMPLEMENTATION_REFS = frozenset({
    "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
    "app.modules.placeholder:PlaceholderTeam",
    # ★선언형 실행기는 basement 소속이라 도메인 교체와 무관하게 항상 등록돼
    #   있다. 이 하나만 배포해 두면 이후 새 Team 은 코드 없이 선언으로 만든다.
    DECLARATIVE_TEAM_REF,
})


class ProjectConfigError(RuntimeError):
    """The project declaration is missing or does not satisfy its schema."""


class ModuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class PortConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_executor: Literal["local", "a2a"]
    message_broker: Literal["outbox", "redis_streams"]
    graph_store: Literal["sql", "age", "neo4j"]


#: ★grant ceiling — 선언형 Team 이 부를 수 있는 tool 이름의 접두사.
#:
#:   왜 이름 목록이 아니라 접두사인가: tool 이름 목록을 여기 하드코딩하면
#:   ("read.subscription" 같은) 도메인 어휘가 basement 로 새어 들어온다
#:   (`tests/architecture/test_basement_is_domain_free.py` 가 잡는다).
#:   접두사 규칙은 도메인을 모르면서 "읽기 전용" 이라는 성질만 강제한다.
#:
#:   ★왜 필요한가: `composer:write` 를 가진 사람이 `allowed_tools` 를 마음대로
#:   넓힐 수 있으면 그것이 곧 **도구 권한을 스스로 부여하는 권한 상승**이다.
#:   선언(프롬프트)은 신뢰 경계 밖의 입력으로 취급해야 한다.
DECLARATIVE_TOOL_PREFIX = "read."


class DeclarativeTeamParameters(BaseModel):
    """선언형 Team 하나를 정의하는 값. 여기 있는 것은 전부 **데이터**다.

    ★도메인 어휘를 이 모델이 알 필요가 없다 — capability·case type·tool 이름은
      전부 product 가 선언에 적어 넣는 문자열이다.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    accepted_case_types: list[str] = Field(default_factory=list)
    required_context: list[Literal["case_state", "policy", "db_facts", "history"]] = Field(
        default_factory=lambda: ["case_state", "policy"])
    allowed_tools: list[str] = Field(default_factory=list)
    knowledge_scope: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=4, ge=1, le=12)
    prompt_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def _enforce_grant_ceiling(self) -> "DeclarativeTeamParameters":
        # ★런타임이 아니라 **로드 시점**에 거부한다. 런타임 검사로 미루면
        #   "저장은 됐는데 언젠가 터지는" 상태가 남는다.
        outside = sorted(t for t in self.allowed_tools
                         if not t.startswith(DECLARATIVE_TOOL_PREFIX))
        if outside:
            raise ValueError(
                "선언형 Team 은 읽기 전용 tool 만 쓸 수 있다 "
                f"(접두사 '{DECLARATIVE_TOOL_PREFIX}'): {', '.join(outside)}")
        return self


class TeamConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str = Field(min_length=1)
    active: bool
    implementation_ref: str = Field(min_length=1)
    #: 선언형 Team 전용. 코드형 Team 은 `None` 이어야 한다.
    parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _parameters_only_for_declarative(self) -> "TeamConfig":
        declarative = self.implementation_ref == DECLARATIVE_TEAM_REF
        if declarative:
            if self.parameters is None:
                raise ValueError(
                    f"team '{self.team_id}': 선언형 Team 은 parameters 가 있어야 한다")
            # 여기서 검증해 둬야 조립 시점이 아니라 로드 시점에 실패한다.
            DeclarativeTeamParameters.model_validate(self.parameters)
        elif self.parameters is not None:
            # ★조용히 무시하지 않는다 — 무시하면 사용자는 설정이 먹은 줄 안다.
            raise ValueError(
                f"team '{self.team_id}': parameters 는 선언형 Team 에만 쓴다 "
                f"(implementation_ref 가 '{DECLARATIVE_TEAM_REF}' 일 때)")
        return self

    def declarative_parameters(self) -> "DeclarativeTeamParameters | None":
        """선언형이면 검증된 파라미터를, 아니면 None 을 돌려준다."""
        if self.implementation_ref != DECLARATIVE_TEAM_REF or self.parameters is None:
            return None
        return DeclarativeTeamParameters.model_validate(self.parameters)


_IMPLEMENTATION_REF_PATTERN = re.compile(
    r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$",
    re.ASCII,
)


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: dict[str, ModuleConfig]
    ports: PortConfig
    teams: list[TeamConfig] = Field(min_length=1)

    #: ★조립을 식별하는 값. 콘솔의 모든 화면이 같은 revision 을 표시한다.
    #:  이게 없으면 "마지막 실행 결과" 가 **어느 조립 상태에서 나온 것인지** 알 수 없고,
    #:  검증·평가·샘플 실행 사이의 추적이 끊긴다.
    #:  ★선언 **내용**에서 나온다 — 파일 mtime 이나 git 커밋이 아니다.
    #:  같은 내용이면 어느 기계에서 읽어도 같은 값이어야 재현이 성립한다.
    revision: str = ""

    def compute_revision(self) -> str:
        """정규화한 선언 내용의 sha256 앞 12자.

        ★키 순서·주석·들여쓰기가 달라도 **내용이 같으면 같은 값**이다.
          그래야 형식만 바꾼 저장이 revision 을 흔들지 않는다.
        """
        payload = self.model_dump(mode="json", exclude={"revision"})
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    @model_validator(mode="after")
    def validate_team_ids(self) -> "ProjectConfig":
        ids = [team.team_id for team in self.teams]
        duplicates = sorted({team_id for team_id in ids if ids.count(team_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate team_id in project declaration: {', '.join(duplicates)}")
        return self

    def module_enabled(self, module_id: str) -> bool:
        try:
            return self.modules[module_id].enabled
        except KeyError as exc:
            raise ProjectConfigError(f"project.yaml module is not declared: {module_id}") from exc

    def require_module(self, module_id: str, operation: str) -> None:
        if not self.module_enabled(module_id):
            raise ProjectConfigError(
                f"module '{module_id}' is disabled; cannot assemble {operation}"
            )


def _load(path: Path) -> ProjectConfig:
    if not path.is_file():
        raise ProjectConfigError(f"project declaration file does not exist: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProjectConfigError(f"invalid project declaration {path}: {exc}") from exc
    return config_from_declaration(raw, source=str(path))


def config_from_declaration(raw: Any, *, source: str = "<declaration>") -> ProjectConfig:
    """선언 dict 를 **파일 없이** 검증한다.

    ★중앙 설정 저장소(`config_store.py`)로 옮기면서 필요해졌다. 선언이 파일이
      아니라 DB 행으로 올 수 있으므로, 검증이 파일 경로에 묶여 있으면 안 된다.

    ★검증 규칙은 파일 경로와 **완전히 같다** — 같은 함수를 쓴다. 저장소마다
      다른 검증기를 두면 "한쪽은 통과하고 한쪽은 죽는" 상태가 생긴다.
    """
    try:
        if not isinstance(raw, dict):
            raise ProjectConfigError(f"project declaration must be a mapping: {source}")
        config = ProjectConfig.model_validate(raw)
        # ★revision 은 선언에 적는 값이 아니라 **계산되는 값**이다.
        #   사람이 손으로 적게 두면 내용과 어긋나도 아무도 모른다.
        config.revision = config.compute_revision()
        _validate_active_team_implementations(config)
        return config
    except ProjectConfigError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise ProjectConfigError(f"invalid project declaration {source}: {exc}") from exc


def _validate_active_team_implementations(config: ProjectConfig) -> None:
    """Resolve active team declarations while keeping imports out of the Core graph.

    This uses a string-driven import rather than a static dependency on any team
    package.  Inactive declarations intentionally remain placeholders and are
    not inspected beyond the schema's non-empty string check.
    """
    for team in config.teams:
        if not team.active:
            continue

        ref = team.implementation_ref
        if not _IMPLEMENTATION_REF_PATTERN.fullmatch(ref):
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' is invalid: "
                "expected 'package.module:Class'"
            )

        module_name, class_name = ref.split(":", maxsplit=1)
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' cannot be imported: {exc}"
            ) from exc

        try:
            implementation = getattr(module, class_name)
        except AttributeError as exc:
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' is invalid: "
                f"class '{class_name}' is not defined in module '{module_name}'"
            ) from exc

        if not isinstance(implementation, type):
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' is invalid: "
                "target is not a class"
            )

        # ★코드형 Team 은 `manifest` 를 클래스 속성으로 갖는다. 선언형 실행기는
        #   인스턴스마다 선언에서 manifest 를 만들기 때문에 클래스에는 없다 —
        #   대신 그 선언(`parameters`)을 `TeamConfig` 가 이미 검증했다. 그래서
        #   선언형에는 `execute` 만 요구한다. `manifest` 까지 요구하면 "클래스에
        #   빈 manifest 를 달아 검사만 통과시키는" 무의미한 회피를 부른다.
        required = ("execute",) if ref == DECLARATIVE_TEAM_REF else ("manifest", "execute")
        missing = [name for name in required if not hasattr(implementation, name)]
        if missing:
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' does not satisfy "
                f"TeamModule: missing {', '.join(missing)}"
            )


@lru_cache(maxsize=8)
def _cached_load(path: str, mtime_ns: int) -> ProjectConfig:
    return _load(Path(path))


def load_project_config(path: str | Path | None = None) -> ProjectConfig:
    """Load a declaration from a **file**; absence and schema errors are never
    silently defaulted.

    ★중앙 저장소를 포함한 "설정이 정한 출처" 로 읽으려면
      `acop_basement.application.config_source.load_active_config()` 를 쓴다.
      그 해석기가 core 가 아니라 application 층에 있는 이유는, core 가
      `infrastructure`(DB 드라이버)를 import 할 수 없기 때문이다 —
      `tests/contract/test_core_isolation.py` 가 강제한다.
    """
    selected = Path(path) if path is not None else DEFAULT_PROJECT_CONFIG
    selected = selected if selected.is_absolute() else (REPO_ROOT / selected)
    try:
        mtime_ns = selected.stat().st_mtime_ns
    except OSError as exc:
        raise ProjectConfigError(f"project declaration file does not exist: {selected}") from exc
    return _cached_load(str(selected.resolve()), mtime_ns)


__all__ = [
    "DEFAULT_PROJECT_CONFIG", "ModuleConfig", "PortConfig", "ProjectConfig",
    "ProjectConfigError", "TeamConfig", "KNOWN_IMPLEMENTATION_REFS", "load_project_config",
    "DECLARATIVE_TEAM_REF", "DECLARATIVE_TOOL_PREFIX", "DeclarativeTeamParameters",
    "config_from_declaration", "configured_store",
]
