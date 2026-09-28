"""Catalog & Verification Remote Team — 실제로 왕복하는 최소 원격 Agent (v7 §0 변경 6).

★왜 이게 필요한가 — 지금까지의 A2A 검증은 **고정 응답을 돌려주는 더미 Transport** 였다.

    class Transport:
        async def submit(self, endpoint, task): return self.response   # 고정 dict

  "상태 매핑이 맞다" 와 "원격과 주고받는다" 는 다른 주장이다.
  v7 DoD-26 은 **Card 발견 → working → input-required → 추가 입력 → Artifact 완료**
  라는 **왕복**을 요구한다.

★이 앱은 A-COP 본체와 **완전히 분리**된다. DB 도 Core 도 모른다.
  원격이 A-COP 내부를 알면 그건 원격이 아니다.

노출하는 것:
  GET  /.well-known/agent-card.json     Agent Card 발견
  POST /a2a/tasks                        Task 제출
  GET  /a2a/tasks/{task_id}              상태 조회
  POST /a2a/tasks/{task_id}/input        추가 입력 → 재개
  POST /a2a/tasks/{task_id}/cancel       취소
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

#: 이 원격 팀이 스스로 광고하는 능력
CARD = {
    "name": "Catalog & Verification Remote Team",
    "description": "카탈로그 조회와 주문 검증을 대행하는 독립 Agent",
    "version": "1.0",
    "capabilities": [
        {"team_id": "catalog_verification", "display_name": "Catalog & Verification",
         "capabilities": ["catalog.lookup", "order.verify"],
         "accepted_case_types": ["catalog", "order"],
         "contract_versions": ["1.0"]},
    ],
    "endpoints": {"submit": "/a2a/tasks", "poll": "/a2a/tasks/{task_id}"},
    "authentication": {"scheme": "bearer"},
}

#: 이 원격이 요구하는 토큰. ★없거나 틀리면 401 이다 — v7 DoD-27 의 "인증".
REMOTE_TOKEN = "remote-catalog-token"


def _require_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {REMOTE_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized",
                                                               "message": "invalid remote credential"}})


def create_remote_agent(*, behavior: str = "input_then_complete") -> FastAPI:
    """원격 Agent 앱을 만든다.

    `behavior` 로 시나리오를 고른다 — 실패·지연·즉시완료를 시험하기 위한 것이며
    ★**정상 경로는 `input_then_complete` 하나뿐이다.** 나머지는 오류 경로 재현용이다.
    """
    app = FastAPI(title="Catalog & Verification Remote Team")
    tasks: dict[str, dict[str, Any]] = {}
    app.state.tasks = tasks

    @app.get("/.well-known/agent-card.json")
    def agent_card() -> dict:
        """★Card 발견은 인증 없이 열어 둔다. 무엇을 할 수 있는지는 공개 정보다."""
        return CARD

    @app.post("/a2a/tasks")
    async def submit(request: Request, authorization: str | None = Header(default=None)) -> dict:
        _require_auth(authorization)
        payload = await request.json()
        task_id = str(uuid4())

        if behavior == "fail_immediately":
            tasks[task_id] = {"task_id": task_id, "status": "failed", "failure_code": "catalog_unavailable"}
        elif behavior == "never_finishes":
            # ★영원히 working — 호출자의 deadline 이 동작하는지 보기 위한 것이다
            tasks[task_id] = {"task_id": task_id, "status": "working"}
        elif behavior == "complete_immediately":
            tasks[task_id] = {"task_id": task_id, "status": "completed",
                              "artifact": _artifact(payload)}
        else:
            # 정상 경로: 먼저 working, 폴링하면 input-required 로 넘어간다
            tasks[task_id] = {"task_id": task_id, "status": "working", "_polls": 0,
                              "_request": payload}
        return tasks[task_id]

    @app.get("/a2a/tasks/{task_id}")
    def poll(task_id: str, authorization: str | None = Header(default=None)) -> dict:
        _require_auth(authorization)
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "unknown task"}})
        if task["status"] == "working" and behavior == "input_then_complete":
            task["_polls"] += 1
            if task["_polls"] >= 1:
                # ★추가 입력을 요구한다 — 이것이 v7 이 지정한 input-required 단계다
                task["status"] = "input-required"
                task["input_schema"] = {"type": "object",
                                        "required": ["order_id"],
                                        "properties": {"order_id": {"type": "string"}}}
        return task

    @app.post("/a2a/tasks/{task_id}/input")
    async def provide_input(task_id: str, request: Request,
                            authorization: str | None = Header(default=None)) -> dict:
        """★추가 입력을 받아 **재개**한다. 여기까지 와야 왕복이다."""
        _require_auth(authorization)
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "unknown task"}})
        if task["status"] != "input-required":
            raise HTTPException(status_code=409, detail={"error": {"code": "conflict",
                                                                   "message": f"task is {task['status']}"}})
        body = await request.json()
        if not body.get("order_id"):
            raise HTTPException(status_code=422, detail={"error": {"code": "validation_error",
                                                                   "message": "order_id is required"}})
        task["status"] = "completed"
        task["artifact"] = _artifact(task.get("_request") or {}, order_id=body["order_id"])
        return task

    @app.post("/a2a/tasks/{task_id}/cancel")
    def cancel(task_id: str, authorization: str | None = Header(default=None)) -> dict:
        """★취소는 실패와 다른 사건이다. 별도 상태로 남긴다 (v7 DoD-27)."""
        _require_auth(authorization)
        task = tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "unknown task"}})
        if task["status"] in {"completed", "failed"}:
            raise HTTPException(status_code=409, detail={"error": {"code": "conflict",
                                                                   "message": "task already finished"}})
        task["status"] = "cancelled"
        task["failure_code"] = "cancelled_by_caller"
        return task

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "error": {"code": "http_error", "message": str(exc.detail)}}
        return JSONResponse(status_code=exc.status_code, content=detail)

    return app


def _artifact(request_payload: dict[str, Any], *, order_id: str | None = None) -> dict[str, Any]:
    """원격이 돌려주는 Artifact.

    ★A-COP 의 `TeamResult` 모양으로 맞춰 준다. 실무에서는 어댑터가 변환하지만,
      여기서는 계약이 실제로 지켜지는지 보는 것이 목적이다.
    """
    evidence_id = "remote:catalog:" + (order_id or "unknown")
    return {
        "outcome": "completed",
        "answer": f"카탈로그 확인 완료 (order_id={order_id})" if order_id else "카탈로그 확인 완료",
        "confidence": 0.9,
        "evidence": [{
            "evidence_id": evidence_id,
            "source_type": "remote_agent",
            "source_id": order_id or "catalog",
            "claim": "원격 카탈로그에서 주문을 확인했다",
            "value": {"order_id": order_id},
            "confidence": 0.9,
            "observed_at": "2026-08-16T00:00:00+00:00",
        }],
        "next_action": "respond",
    }
