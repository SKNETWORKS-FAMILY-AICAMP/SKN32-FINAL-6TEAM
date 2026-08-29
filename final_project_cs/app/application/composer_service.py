"""Safe read/validate/apply operations for the Composer configuration channel."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.core.project_config import (
    DEFAULT_PROJECT_CONFIG,
    KNOWN_IMPLEMENTATION_REFS,
    ProjectConfig,
    ProjectConfigError,
    load_project_config,
)

_WRITE_LOCK = threading.Lock()


class RevisionConflict(RuntimeError):
    def __init__(self, current_revision: str) -> None:
        self.current_revision = current_revision
        super().__init__(f"revision conflict: current is {current_revision}")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    config: ProjectConfig | None
    errors: list[str]


def _revision(config: ProjectConfig) -> str:
    payload = config.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def config_payload(config: ProjectConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")


def read_current(path: str | Path | None = None) -> ProjectConfig:
    return load_project_config(path or DEFAULT_PROJECT_CONFIG)


def revision(config: ProjectConfig) -> str:
    return _revision(config)


def _validate_http_registry(raw: dict[str, Any]) -> list[str]:
    errors = []
    for team in raw.get("teams", []):
        if not isinstance(team, dict) or team.get("active") is not True:
            continue
        implementation_ref = team.get("implementation_ref")
        if implementation_ref not in KNOWN_IMPLEMENTATION_REFS:
            team_id = team.get("team_id", "<unknown>")
            errors.append(
                f"team '{team_id}' implementation_ref '{implementation_ref}' "
                "is not allowed for the Composer HTTP write channel"
            )
    return errors


def validate_candidate(raw: dict[str, Any], *, path: str | Path | None = None,
                       enforce_registry: bool = False) -> ValidationResult:
    if enforce_registry:
        errors = _validate_http_registry(raw)
        if errors:
            return ValidationResult(False, None, errors)

    target = Path(path or DEFAULT_PROJECT_CONFIG)
    candidate_path = target.with_name(f".{target.stem}.validate.{uuid4().hex}.yaml")
    try:
        candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
        candidate = load_project_config(candidate_path)
        return ValidationResult(True, candidate, [])
    except (ProjectConfigError, OSError, yaml.YAMLError, TypeError, ValueError) as exc:
        return ValidationResult(False, None, [str(exc)])
    finally:
        candidate_path.unlink(missing_ok=True)


def apply_candidate(raw: dict[str, Any], *, base_revision: str,
                    path: str | Path | None = None,
                    enforce_registry: bool = False) -> ProjectConfig:
    target = Path(path or DEFAULT_PROJECT_CONFIG)
    with _WRITE_LOCK:
        if enforce_registry:
            errors = _validate_http_registry(raw)
            if errors:
                raise ProjectConfigError("; ".join(errors))

        current = load_project_config(target)
        current_revision = _revision(current)
        if current_revision != base_revision:
            raise RevisionConflict(current_revision)

        candidate_path = target.with_name(f".{target.stem}.validate.{uuid4().hex}.yaml")
        staged = target.with_name(f".{target.stem}.write.{uuid4().hex}.yaml")
        try:
            candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
            candidate = load_project_config(candidate_path)
            backup = target.with_suffix(target.suffix + ".bak")
            backup.write_bytes(target.read_bytes())
            staged.write_bytes(candidate_path.read_bytes())
            os.replace(staged, target)
            return load_project_config(target)
        finally:
            candidate_path.unlink(missing_ok=True)
            staged.unlink(missing_ok=True)


def toggle_target(target_type: str, target_id: str, active: bool, *, base_revision: str,
                  path: str | Path | None = None) -> tuple[ProjectConfig, bool]:
    """Toggle one registered module/team flag while preserving the declaration."""
    target = Path(path or DEFAULT_PROJECT_CONFIG)
    with _WRITE_LOCK:
        current = load_project_config(target)

        if target_type == "module":
            if target_id not in current.modules:
                raise ProjectConfigError(f"project.yaml module is not declared: {target_id}")
            previous_active = current.modules[target_id].enabled
        elif target_type == "team":
            matching = next((team for team in current.teams if team.team_id == target_id), None)
            if matching is None:
                raise ProjectConfigError(f"project.yaml team is not declared: {target_id}")
            previous_active = matching.active
        else:
            raise ProjectConfigError(f"project.yaml {target_type} is not declared: {target_id}")

        current_revision = _revision(current)
        if current_revision != base_revision:
            raise RevisionConflict(current_revision)

        try:
            raw = yaml.safe_load(target.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ProjectConfigError(f"project declaration must be a mapping: {target}")
            if target_type == "module":
                raw["modules"][target_id]["enabled"] = active
            else:
                for team in raw["teams"]:
                    if team.get("team_id") == target_id:
                        team["active"] = active
                        break

            staged = target.with_name(f".{target.stem}.write.{uuid4().hex}.yaml")
            try:
                staged.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
                load_project_config(staged)
                backup = target.with_suffix(target.suffix + ".bak")
                backup.write_bytes(target.read_bytes())
                os.replace(staged, target)
            finally:
                staged.unlink(missing_ok=True)
            return load_project_config(target), previous_active
        except (KeyError, TypeError, yaml.YAMLError, OSError, ValueError) as exc:
            raise ProjectConfigError(f"invalid project declaration {target}: {exc}") from exc
