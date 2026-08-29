"""Authenticated Composer configuration API."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.composer_service import (RevisionConflict, apply_candidate, config_payload,
    read_current, revision, toggle_target, validate_candidate)
from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfigError
from app.presentation.composer_auth import require_composer_scope

router = APIRouter(prefix="/composer", tags=["composer-write"])


class CandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]


class ApplyPayload(CandidatePayload):
    base_revision: str
    reason: str = Field(min_length=1)


class TogglePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: str
    target_id: str = Field(min_length=1)
    active: bool
    base_revision: str
    reason: str = Field(min_length=1)


def _path(request: Request) -> Path:
    return Path(getattr(request.app.state, "project_config_path", DEFAULT_PROJECT_CONFIG))


def _audit_path(request: Request) -> Path:
    default = Path(__file__).resolve().parents[3] / "var" / "audit" / "composer_events.jsonl"
    return Path(getattr(request.app.state, "composer_audit_path", default))


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, **extra}})


@router.get("/current")
def current(request: Request, _principal=Depends(require_composer_scope("composer:read"))):
    config = read_current(_path(request))
    return {"revision": revision(config), "config": config_payload(config)}


@router.post("/validate")
def validate(payload: CandidatePayload, request: Request,
            _principal=Depends(require_composer_scope("composer:validate"))):
    result = validate_candidate(payload.config, path=_path(request), enforce_registry=True)
    if not result.valid:
        return {"valid": False, "errors": result.errors}
    return {"valid": True, "errors": [], "revision": revision(result.config)}


@router.post("/apply")
def apply(payload: ApplyPayload, request: Request,
          principal=Depends(require_composer_scope("composer:write"))):
    target = _path(request)
    previous = read_current(target)
    try:
        applied = apply_candidate(payload.config, base_revision=payload.base_revision, path=target,
                                  enforce_registry=True)
    except RevisionConflict as exc:
        raise _error(409, "revision_conflict", "configuration changed; reload and retry",
                     current_revision=exc.current_revision) from exc
    except ProjectConfigError as exc:
        raise _error(422, "invalid_declaration", str(exc)) from exc
    event = {"event": "composer.apply", "actor": principal["sub"], "subject": str(target),
             "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
             "previous_revision": revision(previous), "revision": revision(applied),
             "changed_fields": _changed_fields(config_payload(previous), config_payload(applied)),
             "reason": payload.reason, "correlation_id": str(uuid4())}
    try:
        _append_audit(event, _audit_path(request))
    except OSError as exc:
        raise _error(500, "audit_failure", "config was applied but audit recording failed") from exc
    return {"revision": revision(applied), "applied": True}


@router.post("/toggle")
def toggle(payload: TogglePayload, request: Request,
          principal=Depends(require_composer_scope("composer:write"))):
    target = _path(request)
    try:
        applied, previous_active = toggle_target(
            payload.target_type, payload.target_id, payload.active,
            base_revision=payload.base_revision, path=target,
        )
    except RevisionConflict as exc:
        raise _error(409, "revision_conflict", "configuration changed; reload and retry",
                     current_revision=exc.current_revision) from exc
    except ProjectConfigError as exc:
        raise _error(422, "invalid_declaration", str(exc)) from exc

    correlation_id = str(uuid4())
    new_revision = revision(applied)
    event = {
        "event": "composer.toggle",
        "actor": principal["sub"],
        "subject": str(target),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "target_type": payload.target_type,
        "target_id": payload.target_id,
        "previous_active": previous_active,
        "active": payload.active,
        "base_revision": payload.base_revision,
        "config_revision": new_revision,
        "reason": payload.reason,
        "correlation_id": correlation_id,
    }
    try:
        _append_audit(event, _audit_path(request))
    except OSError as exc:
        raise _error(500, "audit_failure", "config was toggled but audit recording failed") from exc
    return {
        "target_type": payload.target_type,
        "target_id": payload.target_id,
        "active": payload.active,
        "config_revision": new_revision,
        "audit_id": correlation_id,
    }


def _changed_fields(previous: Any, current: Any, prefix: str = "") -> list[str]:
    if isinstance(previous, dict) and isinstance(current, dict):
        fields = []
        for key in sorted(set(previous) | set(current)):
            path = f"{prefix}.{key}" if prefix else key
            fields.extend([path] if key not in previous or key not in current else _changed_fields(previous[key], current[key], path))
        return fields
    if isinstance(previous, list) and isinstance(current, list):
        fields = []
        for index in range(max(len(previous), len(current))):
            path = f"{prefix}[{index}]"
            fields.extend([path] if index >= len(previous) or index >= len(current) else _changed_fields(previous[index], current[index], path))
        return fields
    return [prefix] if previous != current else []


def _append_audit(event: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
