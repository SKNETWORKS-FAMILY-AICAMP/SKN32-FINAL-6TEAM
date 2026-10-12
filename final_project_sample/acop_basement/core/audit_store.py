"""감사 이벤트를 어디에 두는가 — 파일이냐 중앙 저장소냐.

★설정과 같은 이유로 감사 로그도 중앙에 둔다. 대상마다 로컬 JSONL 파일을
  가지면 대상 수만큼 흩어져 조회·보존하기 어렵다. 저장 위치만 바꾸며 이벤트
  전문은 dict 그대로 보존한다.

★감사 이벤트는 append-only 다. 이 모듈에는 갱신·삭제 통로가 없다.

★이 모듈은 도메인을 모른다. 이벤트를 dict 로만 다룬다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class AuditStoreError(RuntimeError):
    """감사 이벤트를 기록하거나 읽을 수 없다."""


class AuditStore(Protocol):
    """감사 이벤트를 기록하고 찾는 통로. 파일이든 중앙 DB 든 이 창으로만 본다."""

    def append(self, event: dict[str, Any]) -> None:
        """이벤트 전문을 변경하지 않고 한 건 추가한다."""
        ...

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """이 대상의 최신 이벤트부터 최대 `limit` 건을 돌려준다."""
        ...

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        """같은 키로 처음 기록된 이벤트. 없으면 `None`."""
        ...


class FileAuditStore:
    """지금까지의 동작 — 로컬 JSONL 파일.

    ★append 형식과 flush 동작을 그대로 둔다. 조회 중 손상된 줄은 건너뛴다.
      한 줄의 손상이 뒤의 정상 이벤트나 idempotency 재시도를 막아서는 안 된다.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
        except OSError as exc:
            raise AuditStoreError(f"감사 로그 파일에 기록하지 못했다: {self.path}") from exc

    def _events(self) -> list[dict[str, Any]]:
        try:
            with self.path.open(encoding="utf-8") as stream:
                events: list[dict[str, Any]] = []
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # 손상된 줄이 조회를 막아서는 안 된다
                    if isinstance(event, dict):
                        events.append(event)
                return events
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise AuditStoreError(f"감사 로그 파일을 읽지 못했다: {self.path}") from exc

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 0:
            raise AuditStoreError("recent limit 은 0 이상이어야 한다")
        if limit == 0:
            return []
        return list(reversed(self._events()[-limit:]))

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        if not key:
            return None
        # ★기존 `_find_idempotent` 와 같은 전체 순방향 스캔이다. 중복 기록이
        #   있어도 최초 처리 결과를 재시도 근거로 삼는다.
        for event in self._events():
            if event.get("idempotency_key") == key:
                return event
        return None


#: 중앙 감사 저장소 테이블. 대상별 이벤트가 append-only 로 쌓인다.
COMPOSER_AUDIT_EVENTS_TABLE = "composer_audit_events"


class PostgresAuditStore:
    """중앙 저장소 — 여러 대상의 감사 이벤트를 한 테이블에 격리해 둔다.

    ★모든 읽기와 쓰기는 `deployment_id` 를 조건으로 삼는다. idempotency key 는
      고유 제약이 아니다. 감사 기록은 중복 요청도 지우지 않고 모두 남긴다.
    """

    def __init__(self, connection_factory: Any, deployment_id: str) -> None:
        if not deployment_id:
            raise AuditStoreError("중앙 감사 저장소를 쓰려면 deployment_id 가 있어야 한다")
        self.connection_factory = connection_factory
        self.deployment_id = deployment_id

    def append(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        with self.connection_factory() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {COMPOSER_AUDIT_EVENTS_TABLE} "
                    "(deployment_id, event, actor, payload, idempotency_key) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (self.deployment_id, event.get("event"), event.get("actor"),
                     payload, event.get("idempotency_key")))

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 0:
            raise AuditStoreError("recent limit 은 0 이상이어야 한다")
        if limit == 0:
            return []
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT payload FROM {COMPOSER_AUDIT_EVENTS_TABLE} "
                    "WHERE deployment_id = %s "
                    "ORDER BY created_at DESC, event_id DESC LIMIT %s",
                    (self.deployment_id, limit))
                rows = cur.fetchall()
        return [self._payload(row[0]) for row in rows]

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        if not key:
            return None
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT payload FROM {COMPOSER_AUDIT_EVENTS_TABLE} "
                    "WHERE deployment_id = %s AND idempotency_key = %s "
                    "ORDER BY event_id ASC LIMIT 1",
                    (self.deployment_id, key))
                row = cur.fetchone()
        return None if row is None else self._payload(row[0])

    def _payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise AuditStoreError(
                f"감사 이벤트가 mapping 이 아니다: {self.deployment_id}")
        return payload


__all__ = ["AuditStore", "AuditStoreError", "FileAuditStore",
           "PostgresAuditStore", "COMPOSER_AUDIT_EVENTS_TABLE"]
