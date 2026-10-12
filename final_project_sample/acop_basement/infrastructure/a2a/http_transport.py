"""A2A HTTP transport — 실제로 원격과 주고받는다 (v7 DoD-26·27).

★지금까지의 A2A 검증은 고정 dict 를 돌려주는 더미였다.
  이 transport 는 **실제 HTTP 요청**을 보낸다 — 인증 헤더가 붙고, 401·404 를 받으며,
  Agent Card 를 **가져와서** 능력을 읽는다.

★`A2ATeamExecutor` 는 바뀌지 않는다. transport 만 갈아 끼운다 —
  그게 Port 를 둔 이유다 (DoD-20).

테스트에서는 `httpx.ASGITransport` 로 원격 앱을 in-process 로 붙인다.
프로세스 경계를 넘지는 않지만 **HTTP 의미(상태코드·헤더·직렬화)는 실제로 탄다.**
그 한계는 판정 문서에 적는다.
"""
from __future__ import annotations

from typing import Any

import httpx

from acop_basement.core.contracts import TeamTask


class A2AHttpTransport:
    """원격 Agent 와 HTTP 로 통신한다."""

    def __init__(self, client: httpx.AsyncClient, *, token: str | None = None) -> None:
        self.client = client
        self.token = token

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def discover(self, base_url: str = "") -> dict[str, Any]:
        """★Agent Card 를 **가져온다.** 만들어 두는 것과 가져오는 것은 다르다."""
        response = await self.client.get(f"{base_url}/.well-known/agent-card.json")
        response.raise_for_status()
        return response.json()

    async def submit(self, endpoint: str, task: TeamTask) -> dict[str, Any]:
        response = await self.client.post(
            endpoint or "/a2a/tasks", headers=self._headers,
            json={"task_id": str(task.task_id), "capability": task.capability,
                  "input_text": task.input_text,
                  # ★원격에 Context 전문을 넘기지 않는다. 필요한 것만 준다.
                  "case_ref": str(task.case_id)})
        if response.status_code == 401:
            return {"status": "failed", "failure_code": "remote_unauthorized"}
        response.raise_for_status()
        return response.json()

    async def poll(self, remote: dict[str, Any], task: TeamTask) -> dict[str, Any]:
        task_id = remote.get("task_id")
        response = await self.client.get(f"/a2a/tasks/{task_id}", headers=self._headers)
        if response.status_code == 401:
            return {"status": "failed", "failure_code": "remote_unauthorized"}
        if response.status_code == 404:
            return {"status": "failed", "failure_code": "remote_task_missing"}
        response.raise_for_status()
        return response.json()

    async def provide_input(self, remote: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """input-required 에 응답해 원격을 **재개**시킨다."""
        response = await self.client.post(
            f"/a2a/tasks/{remote.get('task_id')}/input", headers=self._headers, json=payload)
        if response.status_code == 401:
            return {"status": "failed", "failure_code": "remote_unauthorized"}
        response.raise_for_status()
        return response.json()

    async def cancel(self, remote: dict[str, Any]) -> dict[str, Any]:
        """★취소를 **보낸다.** 상태 enum 에 값이 있는 것과 취소가 되는 것은 다르다."""
        response = await self.client.post(
            f"/a2a/tasks/{remote.get('task_id')}/cancel", headers=self._headers)
        if response.status_code == 401:
            return {"status": "failed", "failure_code": "remote_unauthorized"}
        response.raise_for_status()
        return response.json()
