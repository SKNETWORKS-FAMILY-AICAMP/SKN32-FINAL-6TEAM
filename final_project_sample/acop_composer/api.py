"""Composer 쓰기 채널 — `/composer/validate`, `/composer/apply`.

★이게 릴리스 이후 콘솔이 모듈을 켜고 끄는 방법이다.

  `/ui/composer` HTML 폼은 **개발 중에만** 켠다(`composer_ui` 모듈 토글, 릴리스 시 끈다).
  이 두 엔드포인트는 **모듈 토글과 무관하게 항상 켜져 있다** — scope 로만 잠근다.
  HTML 페이지가 없어져도 이 채널은 남아서, `final_project_ui` 같은 외부 콘솔이
  나중에 이걸 호출해 구성을 바꾼다.

★콘솔은 `ProjectConfig` 를 import 하지 않는다. raw dict 를 보내고, 이 서버가
  검증해서 결과를 JSON 으로 돌려줄 뿐이다 — "포크" 가 아니다
  (`final_project_ui/CLAUDE.md` §0.2 가 금지하는 것이 바로 검증 모델 복제다).

★`/v1` 아래에 두지 않는다 — case 리소스가 아니라 조립 관리 메타데이터다.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from acop_composer.service import RevisionConflict, apply_candidate, read_current, validate_candidate
from acop_basement.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfigError
from acop_composer.auth import require_composer_scope

router = APIRouter(prefix="/composer", tags=["composer-write"])


def _path(request: Request) -> Path:
    """읽고 쓸 선언 파일. ★HTML 라우터(`app/presentation/ui/composer.py`)와
    같은 `app.state.project_config_path` 관례를 따른다 — 테스트가 실제
    `config/project.yaml` 을 건드리지 않고 임시 선언으로 이 API 를 검사할 수 있다."""
    selected = getattr(request.app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
    return Path(selected)


def _audit_path(request: Request) -> Path:
    """audit JSONL 경로. ★`_path()` 와 같은 이유로 주입 가능해야 한다 —
    아니면 pytest 를 돌릴 때마다 실제 `var/audit/composer_events.jsonl` 에
    테스트용 가짜 apply 이벤트가 쌓인다(버그사냥 2026-08-18. 감사 로그는
    "누가 언제 무엇을 적용했는지" 를 남기는 것인데, 테스트 실행이 매번
    그 기록을 오염시키면 감사로서의 가치가 없다)."""
    default = Path(__file__).resolve().parents[3] / "var" / "audit" / "composer_events.jsonl"
    selected = getattr(request.app.state, "composer_audit_path", default)
    return Path(selected)


class CandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]


class ApplyPayload(CandidatePayload):
    #: ★적용 직전에 서버가 다시 확인한다. 이게 없으면 "마지막에 쓴 사람이 이긴다" 가
    #:   조용히 일어난다 — 남이 그 사이 바꾼 걸 알아채지 못하고 덮어쓴다.
    base_revision: str
    reason: str = Field(min_length=1)


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, **extra}})


@router.get("/current", tags=["composer-write"])
def current(request: Request, _principal=Depends(require_composer_scope("composer:read"))) -> dict[str, Any]:
    """지금 파일의 revision·내용. apply 를 보내기 전 base_revision 을 여기서 얻는다."""
    config = read_current(_path(request))
    return {"revision": config.revision, "config": config.model_dump(mode="json", exclude={"revision"})}


@router.post("/validate")
def validate(payload: CandidatePayload, request: Request,
            _principal=Depends(require_composer_scope("composer:validate"))) -> dict[str, Any]:
    """후보를 검증만 한다. **파일을 바꾸지 않는다.**

    ★활성 Team 의 `implementation_ref` 를 실제로 import 해서 검증한다
      (`ProjectConfigError` 를 통해). 이건 **이미 그 서버 프로세스에 설치된**
      모듈만 로드할 수 있다 — 원격에서 새 코드를 주입하는 경로가 아니다.
      임의 문자열을 보내도 `importlib.import_module` 이 없는 모듈이면 그냥 실패한다.
    """
    result = validate_candidate(payload.config, path=_path(request), enforce_registry=True)
    if not result.valid:
        return {"valid": False, "errors": result.errors}
    return {"valid": True, "errors": [], "revision": result.config.revision}


@router.post("/apply")
def apply(payload: ApplyPayload, request: Request,
         _principal=Depends(require_composer_scope("composer:write"))) -> dict[str, Any]:
    """검증 통과 + revision 일치 시에만 **원자적으로** 쓴다."""
    try:
        target = _path(request)
        previous = read_current(target)
        applied = apply_candidate(payload.config, base_revision=payload.base_revision, path=target, enforce_registry=True)
    except RevisionConflict as exc:
        # ★409 다. 400 이 아니다 — 요청 자체는 유효했고, 그 사이 상태가 바뀐 것이다.
        raise _error(409, "revision_conflict",
                     "다른 변경이 먼저 적용됐다. 최신 구성을 다시 읽고 다시 시도하라.",
                     current_revision=exc.current_revision) from exc
    except ProjectConfigError as exc:
        raise _error(422, "invalid_declaration", str(exc)) from exc
    event = {
        "event": "composer.apply", "actor": _principal["sub"], "subject": str(target),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "previous_revision": previous.revision, "revision": applied.revision,
        "changed_fields": _changed_fields(previous.model_dump(mode="json", exclude={"revision"}), applied.model_dump(mode="json", exclude={"revision"})),
        "reason": payload.reason, "correlation_id": str(uuid4()),
    }
    try:
        _append_audit(event, _audit_path(request))
    except OSError as exc:
        raise _error(500, "audit_failure", "config was applied but audit recording failed") from exc
    return {"revision": applied.revision, "applied": True}


def _changed_fields(previous: Any, current: Any, prefix: str = "") -> list[str]:
    if isinstance(previous, dict) and isinstance(current, dict):
        fields: list[str] = []
        for key in sorted(set(previous) | set(current)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in previous or key not in current:
                fields.append(path)
            else:
                fields.extend(_changed_fields(previous[key], current[key], path))
        return fields
    if isinstance(previous, list) and isinstance(current, list):
        fields: list[str] = []
        for index in range(max(len(previous), len(current))):
            path = f"{prefix}[{index}]"
            if index >= len(previous) or index >= len(current):
                fields.append(path)
            else:
                fields.extend(_changed_fields(previous[index], current[index], path))
        return fields
    return [prefix] if previous != current else []


def _append_audit(event: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush()
