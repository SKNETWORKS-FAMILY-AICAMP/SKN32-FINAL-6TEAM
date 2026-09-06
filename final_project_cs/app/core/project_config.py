"""Typed, fail-fast loader for the project composition declaration."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_CONFIG = REPO_ROOT / "config" / "project.yaml"

KNOWN_IMPLEMENTATION_REFS = frozenset({
    "app.modules.customer_ops:VocStoreManagerTeam",
    "app.modules.customer_ops.response_review:ResponseGenerationReviewTeam",
    "app.modules.customer_ops.return_refund:ReturnRefundTeam",
    "app.modules.customer_ops.procurement_order_payment:ProcurementOrderPaymentTeam",
    "app.modules.customer_ops.fulfillment_logistics:FulfillmentLogisticsTeam",
    "app.modules.customer_ops.catalog_verification:CatalogVerificationTeam",
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


class ResponseReviewConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    owner_team_id: str = Field(min_length=1)


_IMPLEMENTATION_REF_PATTERN = re.compile(
    r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*$",
    re.ASCII,
)


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: dict[str, ModuleConfig]
    ports: PortConfig
    teams: list[TeamConfig] = Field(min_length=1)
    response_review: ResponseReviewConfig = ResponseReviewConfig(
        enabled=False, owner_team_id="response_generation_review"
    )

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


def config_revision(config: ProjectConfig) -> str:
    """선언 **내용**에서 나오는 revision. 파일 mtime 이나 커밋이 아니다.

    ★여기 있는 이유(2026-09-06). 전에는 `app/application/composer_service.py`
      에 있었고 `/introspection` 이 그걸 import 했다. 그런데 introspection 은
      **Composer 를 안 깐 릴리즈 빌드에서도 떠야 하는** 코드다 — 선택 기능의
      모듈에 필수 경로가 의존하고 있었다. 계산은 코어의 일이다.
    """
    payload = config.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def config_from_declaration(raw: Any, *, source: str) -> ProjectConfig:
    """이미 읽어 온 선언(dict)을 **파일 없이** 검증한다.

    ★왜 필요한가. Composer 의 `/validate` 는 예전에 후보를 임시 파일로 쓴 뒤
      그 파일을 로더에 먹였다. 그러면 "검증만 했는데 디스크에 임시 파일이
      생기고", 검증이 대상 디렉터리에 쓰기 권한을 요구한다.

    ★검증기를 둘로 만들지 않는다 — `_load()` 가 이 함수를 부른다. 검증기가
      실제 로더와 다르면 "검증은 통과했는데 기동은 실패" 가 생긴다.
    """
    try:
        if not isinstance(raw, dict):
            raise ProjectConfigError(f"project declaration must be a mapping: {source}")
        config = ProjectConfig.model_validate(raw)
        _validate_active_team_implementations(config)
        return config
    except ProjectConfigError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise ProjectConfigError(f"invalid project declaration {source}: {exc}") from exc


def _load(path: Path) -> ProjectConfig:
    if not path.is_file():
        raise ProjectConfigError(f"project declaration file does not exist: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProjectConfigError(f"invalid project declaration {path}: {exc}") from exc
    return config_from_declaration(raw, source=str(path))


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
    "KNOWN_IMPLEMENTATION_REFS", "ProjectConfigError", "ResponseReviewConfig", "TeamConfig",
    "load_project_config",
]
