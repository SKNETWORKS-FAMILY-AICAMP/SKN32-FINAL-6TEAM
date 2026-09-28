"""Composer 쓰기 채널 — `/composer/*`.

★이게 릴리스 이후 콘솔이 모듈을 켜고 끄는 방법이다. `final_project_ui` 같은
  외부 콘솔이 이 API 로 구성을 바꾼다. scope 로만 잠근다.

★콘솔은 선언 스키마를 import 하지 않는다. raw dict 를 보내고, 이 서버가
  검증해서 결과를 JSON 으로 돌려줄 뿐이다 — "포크" 가 아니다
  (`final_project_ui/CLAUDE.md` §0.2 가 금지하는 것이 바로 검증 모델 복제다).

★`/v1` 아래에 두지 않는다 — case 리소스가 아니라 조립 관리 메타데이터다.

★**이 파일은 어느 제품도 import 하지 않는다**(2026-09-06). 라우터를
  `create_composer_router(host)` 로 만들고, 스키마·등록표·저장소·인증·경로를
  전부 `ComposerHost` 에게서 받는다. 모듈 수준 `router` 를 두지 않는 이유는
  `auth` 와 같다 — import 시점에 어느 제품의 것인지가 굳어 버리고, 한 프로세스에
  두 호스트를 달 수 없다.
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
from acop_composer.auth import require_composer_scope
from acop_composer.host import ComposerHost, ConfigInvalid, HostIncomplete
from acop_composer.service import (
    RevisionConflict, apply_candidate, read_current, validate_candidate,
)
from acop_composer.stores import (
    AuditStore, ConfigStore, RevisionStore, StoreError, StoreTarget,
)

#: 설정 서비스가 "이 요청은 어느 대상의 것인가" 를 받는 헤더.
DEPLOYMENT_HEADER = "X-Deployment-Id"


class CandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]


class ApplyPayload(CandidatePayload):
    #: ★적용 직전에 서버가 다시 확인한다. 이게 없으면 "마지막에 쓴 사람이 이긴다" 가
    #:   조용히 일어난다 — 남이 그 사이 바꾼 걸 알아채지 못하고 덮어쓴다.
    base_revision: str
    reason: str = Field(min_length=1)


class RestorePayload(BaseModel):
    """이력의 revision 하나로 되돌린다 (D-011, 2026-09-06).

    ★"예전 설정 전체를 던져 넣기" 가 아니다 — 서버가 이력에서 그 revision 의
      선언을 꺼내 **새 revision 으로 다시 적용**한다. 그래서 UI 는 선언 구조를
      몰라도 되고, 이력에 없는 내용은 이 경로로 들어올 수 없다.
    """

    model_config = ConfigDict(extra="forbid")
    revision: str = Field(min_length=1)
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
    return HTTPException(status_code=status,
                         detail={"error": {"code": code, "message": message, **extra}})


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


def _apply_change(declaration: dict[str, Any], payload: ChangePayload,
                  host: ComposerHost) -> dict[str, Any]:
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
        created = {
            "team_id": target,
            "active": True if payload.active is None else payload.active,
            "implementation_ref": catalog_mod.ref_for(host, payload.implementation_id),
        }
        # ★코드형 Team 에는 `parameters` 키를 아예 만들지 않는다 — 호스트 codec 의
        #   직렬화와 같은 이유다(의미 없는 `parameters: null` 이 선언에 쌓인다).
        if payload.parameters is not None:
            created["parameters"] = payload.parameters
        teams.append(created)
        return result

    if index is None:
        raise KeyError(f"team '{target}' 이 선언에 없다")

    if op == "delete":
        teams.pop(index)
    elif op == "update":
        entry = teams[index]
        if payload.implementation_id is not None:
            entry["implementation_ref"] = catalog_mod.ref_for(host, payload.implementation_id)
        if payload.parameters is not None:
            entry["parameters"] = payload.parameters
        if payload.active is not None:
            entry["active"] = payload.active
    else:  # enable / disable
        teams[index]["active"] = op == "enable"
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_composer_router(host: ComposerHost) -> APIRouter:
    """이 호스트용 Composer 라우터."""
    router = APIRouter(prefix="/composer", tags=["composer-write"])

    # ── 요청 → 대상 ────────────────────────────────────────────────────

    def _multi(request: Request) -> bool:
        return bool(getattr(request.app.state, "multi_deployment", False))

    def _deployment_id(request: Request) -> str:
        """이 요청이 다루는 대상.

        ★단일 대상 빌드(대상 안에서 도는 Composer)는 자기 자신뿐이라 호스트가
          답한다. **설정 서비스**(중앙 1곳에서 수천 대상을 다루는 형태)는 자기
          설정이 아니라 **요청**이 대상을 지정해야 한다 — 그렇지 않으면 프로세스
          하나가 대상 하나만 관리할 수 있어 중앙화의 의미가 없다.

        ★설정 서비스 모드에서 헤더가 없으면 거부한다. 기본 대상으로 떨어지면
          **남의 설정을 건드리는 사고**가 조용히 일어난다.
        """
        if _multi(request):
            value = (request.headers.get(DEPLOYMENT_HEADER) or "").strip()
            if not value:
                raise _error(400, "deployment_required",
                             f"설정 서비스는 {DEPLOYMENT_HEADER} 헤더로 대상을 지정해야 한다")
            return value
        if host.default_deployment_id is None:
            raise HostIncomplete("호스트가 `default_deployment_id` 를 넘기지 않았다")
        return host.default_deployment_id()

    def _audit_dir() -> Path:
        if host.audit_dir is None:
            raise HostIncomplete("호스트가 `audit_dir` 를 넘기지 않았다")
        return host.audit_dir

    def _target(request: Request) -> StoreTarget:
        """이 요청이 다루는 선언 — **어디에 있는지는 호스트가 정한다.**

        ★경로 주입(`app.state.*`)은 파일 모드의 **테스트 장치**다. 이게 없으면
          pytest 를 돌릴 때마다 실제 `config/project.yaml` 과
          `var/audit/composer_events.jsonl` 에 테스트용 가짜 기록이 쌓인다
          (버그사냥 2026-08-18). 감사 로그는 "누가 언제 무엇을 적용했는지" 를
          남기는 것인데 테스트가 매번 오염시키면 감사로서 값이 없다.
        """
        state = request.app.state
        audit_dir = _audit_dir()
        return StoreTarget(
            deployment_id=_deployment_id(request),
            # ★`True` 면 중앙으로 강제, `None` 이면 호스트 설정이 정한다.
            central=True if _multi(request) else None,
            config_path=Path(getattr(state, "project_config_path", None)
                             or host.default_config_path),
            revisions_path=Path(getattr(state, "composer_revisions_path", None)
                                or audit_dir / "composer_revisions.jsonl"),
            audit_path=Path(getattr(state, "composer_audit_path", None)
                            or audit_dir / "composer_events.jsonl"),
        )

    def _stores():
        if host.stores is None:
            raise HostIncomplete("호스트가 `stores` 를 넘기지 않았다")
        return host.stores

    def _config_store(request: Request) -> ConfigStore:
        return _stores().config_store(_target(request))

    def _revision_store(request: Request) -> RevisionStore:
        """선언 이력. ★주입된 저장소가 있으면 그것이 이긴다 — 경로 주입만으로는
        중앙 모드를 검사할 수 없기 때문이다."""
        injected = getattr(request.app.state, "composer_revision_store", None)
        return injected if injected is not None else _stores().revision_store(_target(request))

    def _audit_store(request: Request) -> AuditStore:
        """감사 이벤트. ★`_revision_store` 와 같은 주입 규칙이다."""
        injected = getattr(request.app.state, "composer_audit_store", None)
        return injected if injected is not None else _stores().audit_store(_target(request))

    def _read_current(request: Request):
        """현재 선언. ★등록 안 된 대상은 500 이 아니라 404 로 답한다.

        "서버가 터졌다" 와 "그 대상은 등록돼 있지 않다" 는 운영자가 해야 할 일이
        전혀 다르다. 오류 메시지가 사실을 잘못 전하면 한참 헤맨다(`CLAUDE.md` §3).
        """
        try:
            return read_current(host, store=_config_store(request))
        except StoreError as exc:
            raise _error(404, "deployment_not_registered", str(exc)) from exc

    def _declaration(config: Any) -> dict[str, Any]:
        """저장·비교·응답에 쓰는 선언 dict. ★호스트 스키마가 만든다."""
        return host.codec.to_declaration(config)

    def _find_idempotent(key: str | None, store: AuditStore) -> dict[str, Any] | None:
        """같은 idempotency_key 로 이미 처리한 결과가 있으면 그것을 돌려준다.

        ★새 저장소를 만들지 않고 **감사 로그를 근거로 삼는다.** 감사는 이미
          append-only 로 영속되고, 프로세스가 죽어도 남는다. 메모리 dict 로 하면
          재시작하면 사라져서 "재시도했더니 두 번 적용" 이 그대로 살아난다.

        ★조회를 저장소에 위임한다(2026-08-30). 파일이면 전체 스캔, 중앙 DB 면
          인덱스 조회다 — 대상이 수천 개면 스캔은 감당이 안 된다.
        """
        if not key:
            return None
        event = store.find_by_idempotency_key(key)
        if event and event.get("result"):
            return dict(event["result"])
        return None

    def _append_audit(event: dict[str, Any], store: AuditStore) -> None:
        """감사 기록. ★실패를 삼키지 않는다 — 호출부가 500 으로 올린다."""
        store.append(event)

    # ── 라우트 ─────────────────────────────────────────────────────────

    @router.post("/toggle")
    def toggle(payload: TogglePayload, request: Request,
               _principal=Depends(require_composer_scope(host, "composer:write"))
               ) -> dict[str, Any]:
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
                _principal=Depends(require_composer_scope(host, "composer:read"))
                ) -> dict[str, Any]:
        """UI 가 고를 수 있는 구현 종류. ★Python 경로는 내보내지 않는다."""
        current_config = _read_current(request)
        try:
            entries = (catalog_mod.team_entries(host)
                       + catalog_mod.module_entries(current_config.modules))
        except catalog_mod.CatalogError as exc:
            # ★조용히 빈 목록을 주지 않는다 — 카탈로그가 깨졌으면 그렇다고 말한다.
            raise _error(500, "catalog_incomplete", str(exc)) from exc
        return {"config_revision": host.codec.revision(current_config),
                "implementations": entries}

    @router.post("/changes")
    def changes(payload: ChangePayload, request: Request,
                _principal=Depends(require_composer_scope(host, "composer:write"))
                ) -> dict[str, Any]:
        """카탈로그 기반 인스턴스 CRUD.

        ★성공해도 `activation_state` 는 `pending_restart` 다. 조립은 프로세스
          기동 때 한 번만 일어나므로, 저장됐다고 해서 이미 떠 있는 런타임이 그
          설정으로 도는 것이 아니다. "적용 완료" 처럼 응답하면 그건 조용한 성공
          위장이다(`CLAUDE.md` §0.1).
        """
        return _perform_change(request, _principal, payload)

    def _perform_change(request: Request, _principal: Any, payload: ChangePayload,
                        event_name: str = "composer.change") -> dict[str, Any]:
        """`/changes` 와 `/toggle` 이 공유하는 단일 저장 경로."""
        config_store = _config_store(request)
        audit_store = _audit_store(request)
        # 감사의 `subject` — 파일 모드면 경로, 중앙 모드면 대상 ID 다.
        subject = (getattr(config_store, "path", None)
                   or getattr(config_store, "deployment_id", "?"))

        cached = _find_idempotent(payload.idempotency_key, audit_store)
        if cached is not None:
            return cached

        previous = _read_current(request)
        declaration = _declaration(previous)
        previous_revision = host.codec.revision(previous)

        try:
            candidate = _apply_change(declaration, payload, host)
        except catalog_mod.CatalogError as exc:
            raise _error(422, "unknown_implementation", str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise _error(422, "invalid_change", str(exc).strip("'")) from exc

        if payload.dry_run:
            # ★대상 선언을 건드리지 않는다. 검증만 한다.
            outcome = validate_candidate(candidate, host, enforce_registry=True)
            if not outcome.valid:
                raise _error(422, "invalid_declaration", "; ".join(outcome.errors),
                             errors=outcome.errors)
            return {"change_id": str(uuid4()), "desired_revision": previous_revision,
                    "activation_state": "pending_restart", "dry_run": True, "errors": []}

        try:
            applied = apply_candidate(
                candidate, host, base_revision=payload.base_revision,
                store=config_store, enforce_registry=True,
                history=_revision_store(request), actor=_principal["sub"],
                reason=payload.reason,
                event="toggle" if event_name == "composer.toggle" else "change")
        except RevisionConflict as exc:
            raise _error(409, "revision_conflict",
                         "다른 변경이 먼저 적용됐다. 최신 구성을 다시 읽고 다시 시도하라.",
                         current_revision=exc.current_revision) from exc
        except ConfigInvalid as exc:
            raise _error(422, "invalid_declaration", str(exc)) from exc
        except StoreError as exc:
            raise _error(500, "history_failure",
                         "change was applied but revision history recording failed") from exc

        applied_revision = host.codec.revision(applied)
        result = {"change_id": str(uuid4()), "desired_revision": applied_revision,
                  "activation_state": "pending_restart", "dry_run": False, "errors": []}
        event = {
            "event": event_name, "actor": _principal["sub"], "subject": str(subject),
            "timestamp": _utc_now(),
            "operation": payload.operation, "resource_type": payload.resource_type,
            "instance_id": payload.instance_id, "implementation_id": payload.implementation_id,
            "previous_revision": previous_revision, "revision": applied_revision,
            "changed_fields": _changed_fields(declaration, _declaration(applied)),
            "reason": payload.reason, "idempotency_key": payload.idempotency_key,
            "correlation_id": result["change_id"], "result": result,
        }
        try:
            _append_audit(event, audit_store)
        except StoreError as exc:
            raise _error(500, "audit_failure",
                         "change was applied but audit recording failed") from exc
        return result

    @router.get("/current", tags=["composer-write"])
    def current(request: Request,
                _principal=Depends(require_composer_scope(host, "composer:read"))
                ) -> dict[str, Any]:
        """지금 선언의 revision·내용. apply 전 base_revision 을 여기서 얻는다."""
        config = _read_current(request)
        return {"revision": host.codec.revision(config), "config": _declaration(config)}

    @router.post("/validate")
    def validate(payload: CandidatePayload, request: Request,
                 _principal=Depends(require_composer_scope(host, "composer:validate"))
                 ) -> dict[str, Any]:
        """후보를 검증만 한다. **선언을 바꾸지 않는다.**

        ★활성 Team 의 `implementation_ref` 를 실제로 import 해서 검증한다.
          이건 **이미 그 서버 프로세스에 설치된** 모듈만 로드할 수 있다 —
          원격에서 새 코드를 주입하는 경로가 아니다.
        """
        result = validate_candidate(payload.config, host, enforce_registry=True)
        if not result.valid:
            return {"valid": False, "errors": result.errors}
        return {"valid": True, "errors": [], "revision": host.codec.revision(result.config)}

    @router.post("/apply")
    def apply(payload: ApplyPayload, request: Request,
              _principal=Depends(require_composer_scope(host, "composer:admin"))
              ) -> dict[str, Any]:
        """선언 **전체**를 검증 통과 + revision 일치 시에만 원자적으로 쓴다.

        ★scope 가 `composer:write` 가 아니라 **`composer:admin`** 이다 (D-011,
          2026-09-06). 운영자 화면은 항목 하나 단위(`/toggle`·`/changes`)만 쓴다.
          전체를 갈아끼우는 이 경로는 **처음 설치·복원·환경 간 이관** 용이라
          관리자에게만 열고, 운영 UI 에는 버튼을 두지 않는다 — 두 운영자가
          전체본을 동시에 보내면 한쪽이 남의 변경을 덮거나 항상 409 로 튕긴다.
        """
        return _apply_whole(request, _principal, payload.config,
                            base_revision=payload.base_revision, reason=payload.reason,
                            event="composer.apply", history_event="apply")

    @router.get("/revisions")
    def revisions(request: Request, limit: int = 50,
                  _principal=Depends(require_composer_scope(host, "composer:read"))
                  ) -> dict[str, Any]:
        """이 대상의 선언 이력, 최신부터. **선언 전문은 내보내지 않는다** —
        되돌리기는 `/restore` 가 서버 안에서 한다. UI 가 전문을 받으면 다시
        통째 교체로 돌아간다."""
        if not 0 <= limit <= 500:
            raise _error(422, "invalid_limit", "limit 은 0 이상 500 이하여야 한다")
        current_config = _read_current(request)
        try:
            entries = _revision_store(request).recent(limit)
        except StoreError as exc:
            raise _error(500, "history_failure", str(exc)) from exc
        return {
            "current_revision": host.codec.revision(current_config),
            "revisions": [{k: e.get(k) for k in ("revision", "previous_revision", "actor",
                                                 "reason", "event", "timestamp")}
                          for e in entries],
        }

    @router.post("/restore")
    def restore(payload: RestorePayload, request: Request,
                _principal=Depends(require_composer_scope(host, "composer:admin"))
                ) -> dict[str, Any]:
        """이력의 revision 하나로 되돌린다 — 앞으로 한 칸 더 가는 새 적용이다."""
        try:
            entry = _revision_store(request).find(payload.revision)
        except StoreError as exc:
            raise _error(500, "history_failure", str(exc)) from exc
        if entry is None:
            raise _error(404, "revision_not_found",
                         f"이력에 없는 revision 이다: {payload.revision}")
        if payload.revision == payload.base_revision:
            raise _error(422, "already_at_revision",
                         "지금이 그 revision 이다. 되돌릴 것이 없다")
        result = _apply_whole(request, _principal, entry["declaration"],
                              base_revision=payload.base_revision, reason=payload.reason,
                              event="composer.restore", history_event="restore",
                              extra={"restored_from": payload.revision})
        return {**result, "restored_from": payload.revision}

    def _apply_whole(request: Request, _principal: Any, declaration: dict[str, Any], *,
                     base_revision: str, reason: str, event: str, history_event: str,
                     extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """`/apply` 와 `/restore` 가 공유하는 전체 적용 경로."""
        try:
            config_store = _config_store(request)
            subject = (getattr(config_store, "path", None)
                       or getattr(config_store, "deployment_id", "?"))
            previous = _read_current(request)
            applied = apply_candidate(declaration, host, base_revision=base_revision,
                                      store=config_store, enforce_registry=True,
                                      history=_revision_store(request),
                                      actor=_principal["sub"],
                                      reason=reason, event=history_event)
        except RevisionConflict as exc:
            # ★409 다. 400 이 아니다 — 요청 자체는 유효했고, 그 사이 상태가 바뀐 것이다.
            raise _error(409, "revision_conflict",
                         "다른 변경이 먼저 적용됐다. 최신 구성을 다시 읽고 다시 시도하라.",
                         current_revision=exc.current_revision) from exc
        except ConfigInvalid as exc:
            raise _error(422, "invalid_declaration", str(exc)) from exc
        except StoreError as exc:
            raise _error(500, "history_failure",
                         "config was applied but revision history recording failed") from exc
        previous_revision = host.codec.revision(previous)
        applied_revision = host.codec.revision(applied)
        audit_event = {
            "event": event, "actor": _principal["sub"], "subject": str(subject),
            "timestamp": _utc_now(),
            "previous_revision": previous_revision, "revision": applied_revision,
            "changed_fields": _changed_fields(_declaration(previous), _declaration(applied)),
            "reason": reason, "correlation_id": str(uuid4()), **(extra or {}),
        }
        try:
            _append_audit(audit_event, _audit_store(request))
        except StoreError as exc:
            raise _error(500, "audit_failure",
                         "config was applied but audit recording failed") from exc
        return {"revision": applied_revision, "applied": True,
                "previous_revision": previous_revision}

    return router


__all__ = [
    "ApplyPayload", "CandidatePayload", "ChangePayload", "DEPLOYMENT_HEADER",
    "RestorePayload", "TogglePayload", "create_composer_router",
]
