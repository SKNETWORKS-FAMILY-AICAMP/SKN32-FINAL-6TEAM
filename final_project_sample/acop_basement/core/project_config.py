"""Typed, fail-fast loader for the project composition declaration."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import os
import importlib
import json
from pathlib import Path
import re
from typing import Literal

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
KNOWN_IMPLEMENTATION_REFS = frozenset({
    "app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
    "app.modules.placeholder:PlaceholderTeam",
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


class TeamConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str = Field(min_length=1)
    active: bool
    implementation_ref: str = Field(min_length=1)


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
        if not isinstance(raw, dict):
            raise ProjectConfigError(f"project declaration must be a mapping: {path}")
        config = ProjectConfig.model_validate(raw)
        # ★revision 은 선언에 적는 값이 아니라 **계산되는 값**이다.
        #   사람이 손으로 적게 두면 내용과 어긋나도 아무도 모른다.
        config.revision = config.compute_revision()
        _validate_active_team_implementations(config)
        return config
    except ProjectConfigError:
        raise
    except (OSError, yaml.YAMLError, ValidationError, TypeError, ValueError) as exc:
        raise ProjectConfigError(f"invalid project declaration {path}: {exc}") from exc


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

        missing = [name for name in ("manifest", "execute") if not hasattr(implementation, name)]
        if missing:
            raise ProjectConfigError(
                f"team '{team.team_id}' implementation_ref '{ref}' does not satisfy "
                f"TeamModule: missing {', '.join(missing)}"
            )


@lru_cache(maxsize=8)
def _cached_load(path: str, mtime_ns: int) -> ProjectConfig:
    return _load(Path(path))


def load_project_config(path: str | Path | None = None) -> ProjectConfig:
    """Load a declaration; absence and schema errors are never silently defaulted."""
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
]
