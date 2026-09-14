"""Place Verification Remote Team — 여행 도메인의 원격 Agent (v10).

★**왜 새로 만드나.** `remote_agent.py` 는 커머스(Catalog & Verification)다.
  2026-09-09 에 등록을 여행으로 갈아끼우면서 `catalog_verification` 이 미등록이
  됐고, 그 결과 **A2A 로 부를 대상이 하나도 없어졌다.** 엔드포인트 다섯은 그대로
  있는데 상대가 없는 상태였다.

★**왜 하필 장소 검증인가.** A2A 로 뺄 값이 있는 것은 **바깥 원장을 조회해 우리
  표시와 대조하는 일**이다 — 커머스에서 `catalog_verification` 이 그 자리였다.
  여행에서 같은 모양은 장소·운영 정보다. 그리고 이 일은 우리 DB 를 안 봐도 되므로
  **원격으로 떼기에 실제로 적합하다**(억지로 뗀 것이 아니다).

★**A-COP 본체와 완전히 분리된다.** DB 도 Core 도 모른다. import 하는 것은
  FastAPI 뿐이다 — 원격이 A-COP 내부를 알면 그건 원격이 아니다.
  이 파일이 `app/core/` 를 import 하는 순간 분리가 깨진다.

노출하는 것 — 커머스 원격과 같은 다섯 개다. 계약이 같아야 executor 가 그대로 돈다.

  GET  /.well-known/agent-card.json     Agent Card 발견
  POST /a2a/tasks                        Task 제출
  GET  /a2a/tasks/{task_id}              상태 조회
  POST /a2a/tasks/{task_id}/input        추가 입력 → 재개
  POST /a2a/tasks/{task_id}/cancel       취소

★**이것은 시뮬레이터다.** 실제 장소 원장(TourAPI·Places)에 붙지 않는다.
  증명하는 것은 **왕복과 계약**이지 장소 데이터의 정확성이 아니다.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

#: 이 원격 팀이 스스로 광고하는 능력.
#: ★`team_id` 는 A-COP 쪽 Registry 에 등록될 이름과 같아야 한다 — 그래야
#:  `capability_resolver` 가 이 원격으로 보낼 수 있다.
CARD = {
    "name": "Place Verification Remote Team",
    "description": "장소 실재·운영 정보를 외부 원장과 대조하는 독립 Agent",
    "version": "1.0",
    "capabilities": [
        {"team_id": "place_verification", "display_name": "Place Verification",
         "capabilities": ["place.lookup", "place.verify_hours"],
         "accepted_case_types": ["place"],
         "contract_versions": ["1.0"]},
    ],
    "endpoints": {"submit": "/a2a/tasks", "poll": "/a2a/tasks/{task_id}"},
    "authentication": {"scheme": "bearer"},
}

#: 이 원격이 요구하는 토큰. ★없거나 틀리면 401 이다.
#:  커머스 원격과 **다른 값**이다 — 같은 값을 쓰면 한쪽 토큰으로 양쪽이 열려
#:  원격별 인증이 실제로 걸리는지 시험할 수 없다.
REMOTE_TOKEN = "remote-place-token"


def _require_auth(authorization: str | None) -> None:
    if authorization != f"Bearer {REMOTE_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized",
                                                               "message": "invalid remote credential"}})


def create_travel_remote_agent(*, behavior: str = "input_then_complete") -> FastAPI:
    """원격 Agent 앱을 만든다.

    `behavior` 로 시나리오를 고른다. ★**정상 경로는 `input_then_complete` 하나뿐이고**
    나머지는 오류 경로 재현용이다 — 정상 경로를 여러 개 두면 무엇이 기본인지 흐려진다.
    """
    app = FastAPI(title="Place Verification Remote Team")
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
            tasks[task_id] = {"task_id": task_id, "status": "failed",
                              "failure_code": "place_registry_unavailable"}
        elif behavior == "never_finishes":
            # ★영원히 working — 호출자의 deadline 이 실제로 도는지 보기 위한 것이다
            tasks[task_id] = {"task_id": task_id, "status": "working"}
        elif behavior == "complete_immediately":
            tasks[task_id] = {"task_id": task_id, "status": "completed",
                              "artifact": _artifact(payload)}
        else:
            tasks[task_id] = {"task_id": task_id, "status": "working", "_polls": 0,
                              "_request": payload}
        return tasks[task_id]

    @app.get("/a2a/tasks/{task_id}")
    def poll(task_id: str, authorization: str | None = Header(default=None)) -> dict:
        _require_auth(authorization)
        task = _find(tasks, task_id)
        if task["status"] == "working" and behavior == "input_then_complete":
            task["_polls"] += 1
            if task["_polls"] >= 1:
                # ★추가 입력을 요구한다 — 왕복의 핵심 단계다.
                #   장소 이름만으로는 원장을 못 찾는다. 식별자를 달라고 되묻는다.
                task["status"] = "input-required"
                task["input_schema"] = {"type": "object",
                                        "required": ["place_id"],
                                        "properties": {
                                            "place_id": {"type": "string"},
                                            "visit_at": {"type": "string", "format": "date-time"},
                                        }}
        return task

    @app.post("/a2a/tasks/{task_id}/input")
    async def provide_input(task_id: str, request: Request,
                            authorization: str | None = Header(default=None)) -> dict:
        """★추가 입력을 받아 **재개**한다. 여기까지 와야 왕복이다."""
        _require_auth(authorization)
        task = _find(tasks, task_id)
        if task["status"] != "input-required":
            raise HTTPException(status_code=409, detail={"error": {"code": "conflict",
                                                                   "message": f"task is {task['status']}"}})
        body = await request.json()
        if not body.get("place_id"):
            raise HTTPException(status_code=422, detail={"error": {"code": "validation_error",
                                                                   "message": "place_id is required"}})
        task["status"] = "completed"
        task["artifact"] = _artifact(task.get("_request") or {},
                                     place_id=body["place_id"], visit_at=body.get("visit_at"))
        return task

    @app.post("/a2a/tasks/{task_id}/cancel")
    def cancel(task_id: str, authorization: str | None = Header(default=None)) -> dict:
        """★취소는 실패와 다른 사건이다. 별도 상태로 남긴다."""
        _require_auth(authorization)
        task = _find(tasks, task_id)
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


def _find(tasks: dict[str, dict[str, Any]], task_id: str) -> dict[str, Any]:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found",
                                                               "message": "unknown task"}})
    return task


def _artifact(request_payload: dict[str, Any], *, place_id: str | None = None,
              visit_at: str | None = None) -> dict[str, Any]:
    """원격이 돌려주는 Artifact — A-COP 의 `TeamResult` 모양으로 맞춘다.

    ★**확인 시각을 반드시 싣는다.** 여행 도메인의 규칙이다 — 재조회 시각을 현장
      관찰 시각처럼 표시하면 안 되므로, 원격도 `observed_at` 을 자기가 조회한
      시각으로 넣고 그 사실을 `claim` 에 적는다.

    ★**모르면 만들지 않는다.** `place_id` 가 없으면 확인했다고 말하지 않는다 —
      `input-required` 로 되묻는 이유가 그것이다.
    """
    observed_at = "2026-09-10T00:00:00+00:00"
    if place_id is None:
        return {
            "outcome": "waiting",
            "answer": None,
            "confidence": 0.0,
            "evidence": [],
            "next_action": "wait_for_input",
            "wait_reason": "customer_input",
        }
    return {
        "outcome": "completed",
        "answer": f"장소 원장에서 확인했습니다 (place_id={place_id})"
                  + (f", 방문 예정 {visit_at} 기준 운영합니다" if visit_at else ""),
        "confidence": 0.9,
        "evidence": [{
            "evidence_id": f"remote:place:{place_id}",
            "source_type": "remote_agent",
            "source_id": place_id,
            "claim": "원격 장소 원장을 조회해 실재와 운영 정보를 확인했다 "
                     "(조회 시각 기준이며 현장 관찰이 아니다)",
            "value": {"place_id": place_id, "visit_at": visit_at, "open": True},
            "confidence": 0.9,
            "observed_at": observed_at,
        }],
        "next_action": "respond",
    }
