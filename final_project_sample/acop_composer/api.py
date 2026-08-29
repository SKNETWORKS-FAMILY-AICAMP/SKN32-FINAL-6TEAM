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
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from acop_composer import catalog as catalog_mod
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


class ChangePayload(BaseModel):
    """인스턴스 하나에 대한 명령.

    ★v2 의 `/apply` 는 전체 선언을 통째로 받는다. 그러면 UI 가 대상의 선언
      구조 전체를 알아야 하고, 그게 곧 스키마 복제로 이어진다. 이 명령은
      "무엇을 어떻게" 만 보낸다 — 나머지는 서버가 현재 선언에서 읽는다.
    """

    model_config = ConfigDict(extra="forbid")
    operation: Literal["create", "update", "delete", "enable", "disable"]
    resource_type: Literal["team", "module"]
    instance_id: str = Field(min_length=1)
    implementation_id: str | None = None
    parameters: dict[str, Any] | None = None
    active: bool | None = None
    base_revision: str
    reason: str = Field(min_length=1)
    dry_run: bool = False
    idempotency_key: str | None = None


class TogglePayload(BaseModel):
    """v3 계약(`program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md` §2.2).

    ★`/changes` 의 `enable`/`disable` 로도 같은 일을 할 수 있다. 그런데도 이
      엔드포인트를 따로 두는 이유는 **UI 가 부르는 이름이 계약으로 정해져
      있기** 때문이다(v3 §2.2, `final_project_cs` 도 같은 이름으로 구현). 다만
      **저장·revision·감사 경로는 `/changes` 와 공유한다** — 같은 일을 하는
      코드를 두 벌 만들면 한쪽만 고쳐지는 날이 온다.
    """

    model_config = ConfigDict(extra="forbid")
    target_type: Literal["module", "team"]
    target_id: str = Field(min_length=1)
    active: bool
    base_revision: str
    reason: str = Field(min_length=1)


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, **extra}})


@router.post("/toggle")
def toggle(payload: TogglePayload, request: Request,
           _principal=Depends(require_composer_scope("composer:write"))) -> dict[str, Any]:
    """등록된 module/team 의 활성 상태만 바꾼다 — v3 토글 계약."""
    outcome = _perform_change(
        request, _principal,
        ChangePayload(
            operation="enable" if payload.active else "disable",
            resource_type=payload.target_type,
            instance_id=payload.target_id,
            base_revision=payload.base_revision,
            reason=payload.reason,
        ),
        event_name="composer.toggle")
    return {
        "target_type": payload.target_type,
        "target_id": payload.target_id,
        "active": payload.active,
        "config_revision": outcome["desired_revision"],
        "audit_id": outcome["change_id"],
        # ★v3 계약에는 없지만 함께 낸다 — 저장됐다고 이미 떠 있는 런타임이 그
        #   설정으로 도는 것이 아니다. 이 사실을 응답에서 감추지 않는다.
        "activation_state": outcome["activation_state"],
    }


@router.get("/catalog")
def catalog(request: Request,
            _principal=Depends(require_composer_scope("composer:read"))) -> dict[str, Any]:
    """UI 가 고를 수 있는 구현 종류. ★Python 경로는 내보내지 않는다."""
    current_config = read_current(_path(request))
    try:
        entries = catalog_mod.team_entries() + catalog_mod.module_entries(current_config.modules)
    except catalog_mod.CatalogError as exc:
        # ★조용히 빈 목록을 주지 않는다 — 카탈로그가 깨졌으면 그렇다고 말한다.
        raise _error(500, "catalog_incomplete", str(exc)) from exc
    return {"config_revision": current_config.revision, "implementations": entries}


def _find_idempotent(key: str | None, audit_path: Path) -> dict[str, Any] | None:
    """같은 idempotency_key 로 이미 처리한 결과가 있으면 그것을 돌려준다.

    ★새 저장소를 만들지 않고 **감사 로그를 근거로 삼는다.** 감사는 이미
      append-only 로 영속되고, 프로세스가 죽어도 남는다. 메모리 dict 로 하면
      재시작하면 사라져서 "재시도했더니 두 번 적용" 이 그대로 살아난다.
    """
    if not key or not audit_path.exists():
        return None
    with audit_path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # 손상된 줄이 재시도를 막아서는 안 된다
            if event.get("idempotency_key") == key and event.get("result"):
                return dict(event["result"])
    return None


def _apply_change(declaration: dict[str, Any], payload: ChangePayload) -> dict[str, Any]:
    """현재 선언에서 **해당 인스턴스 하나만** 바꾼 새 선언을 만든다."""
    result = json.loads(json.dumps(declaration))  # 깊은 복사 — 원본을 안 건드린다
    op, target = payload.operation, payload.instance_id

    if payload.resource_type == "module":
        modules = result.setdefault("modules", {})
        if op == "delete":
            if target not in modules:
                raise KeyError(f"module '{target}' 이 선언에 없다")
            modules.pop(target)
        elif op in ("create", "update"):
            enabled = True if payload.active is None else payload.active
            modules[target] = {"enabled": enabled}
        else:  # enable / disable
            if target not in modules:
                raise KeyError(f"module '{target}' 이 선언에 없다")
            modules[target] = {"enabled": op == "enable"}
        return result

    teams = result.setdefault("teams", [])
    index = next((i for i, t in enumerate(teams) if t.get("team_id") == target), None)

    if op == "create":
        if index is not None:
            raise KeyError(f"team '{target}' 이 이미 있다")
        if payload.implementation_id is None:
            raise ValueError("create 에는 implementation_id 가 필요하다")
        teams.append({
            "team_id": target,
            "active": True if payload.active is None else payload.active,
            "implementation_ref": catalog_mod.ref_for(payload.implementation_id),
            "parameters": payload.parameters,
        })
        return result

    if index is None:
        raise KeyError(f"team '{target}' 이 선언에 없다")

    if op == "delete":
        teams.pop(index)
    elif op == "update":
        entry = teams[index]
        if payload.implementation_id is not None:
            entry["implementation_ref"] = catalog_mod.ref_for(payload.implementation_id)
        if payload.parameters is not None:
            entry["parameters"] = payload.parameters
        if payload.active is not None:
            entry["active"] = payload.active
    else:  # enable / disable
        teams[index]["active"] = op == "enable"
    return result


@router.post("/changes")
def changes(payload: ChangePayload, request: Request,
            _principal=Depends(require_composer_scope("composer:write"))) -> dict[str, Any]:
    """카탈로그 기반 인스턴스 CRUD.

    ★성공해도 `activation_state` 는 `pending_restart` 다. 조립은 프로세스
      기동 때 한 번만 일어나므로(`app/composition.py`), 저장됐다고 해서 이미
      떠 있는 런타임이 그 설정으로 도는 것이 아니다. "적용 완료" 처럼
      응답하면 그건 조용한 성공 위장이다(`CLAUDE.md` §0.1).
    """
    return _perform_change(request, _principal, payload)


def _perform_change(request: Request, _principal: Any, payload: ChangePayload,
                    event_name: str = "composer.change") -> dict[str, Any]:
    """`/changes` 와 `/toggle` 이 공유하는 단일 저장 경로."""
    target = _path(request)
    audit_path = _audit_path(request)

    cached = _find_idempotent(payload.idempotency_key, audit_path)
    if cached is not None:
        return cached

    previous = read_current(target)
    declaration = previous.model_dump(mode="json", exclude={"revision"})

    try:
        candidate = _apply_change(declaration, payload)
    except catalog_mod.CatalogError as exc:
        raise _error(422, "unknown_implementation", str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise _error(422, "invalid_change", str(exc).strip("'")) from exc

    if payload.dry_run:
        # ★대상 파일을 건드리지 않는다. 검증만 한다.
        #   `validate_candidate` 는 예외가 아니라 결과 객체를 돌려준다.
        outcome = validate_candidate(candidate, path=target, enforce_registry=True)
        if not outcome.valid:
            raise _error(422, "invalid_declaration", "; ".join(outcome.errors),
                         errors=outcome.errors)
        return {"change_id": str(uuid4()), "desired_revision": previous.revision,
                "activation_state": "pending_restart", "dry_run": True, "errors": []}

    try:
        applied = apply_candidate(candidate, base_revision=payload.base_revision,
                                  path=target, enforce_registry=True)
    except RevisionConflict as exc:
        raise _error(409, "revision_conflict",
                     "다른 변경이 먼저 적용됐다. 최신 구성을 다시 읽고 다시 시도하라.",
                     current_revision=exc.current_revision) from exc
    except ProjectConfigError as exc:
        raise _error(422, "invalid_declaration", str(exc)) from exc

    result = {"change_id": str(uuid4()), "desired_revision": applied.revision,
              "activation_state": "pending_restart", "dry_run": False, "errors": []}
    event = {
        "event": event_name, "actor": _principal["sub"], "subject": str(target),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "operation": payload.operation, "resource_type": payload.resource_type,
        "instance_id": payload.instance_id, "implementation_id": payload.implementation_id,
        "previous_revision": previous.revision, "revision": applied.revision,
        "changed_fields": _changed_fields(declaration,
                                          applied.model_dump(mode="json", exclude={"revision"})),
        "reason": payload.reason, "idempotency_key": payload.idempotency_key,
        "correlation_id": result["change_id"], "result": result,
    }
    try:
        _append_audit(event, audit_path)
    except OSError as exc:
        raise _error(500, "audit_failure", "change was applied but audit recording failed") from exc
    return result


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
