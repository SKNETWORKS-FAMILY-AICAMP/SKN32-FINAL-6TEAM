"""선언의 **이력** — 적용된 revision 을 순서대로 남겨 되돌릴 수 있게 한다.

★왜 이 층이 생겼나 (D-011, 2026-09-06)

  `project_configs` 는 대상 하나당 **현재 행 하나**만 둔다. 그래서 잘못 바꾼
  설정을 되돌리려면 예전 선언 전체를 다시 던져 넣는 수밖에 없었고, 그 통로가
  "아무 설정이나 통째로 갈아끼우는" `/composer/apply` 였다. 그 통로는 운영자
  손에 쥐어 주면 안 되는 도구다 — 두 운영자가 동시에 작업하면 한쪽이 남의
  변경을 덮거나 항상 409 로 튕긴다.

  그래서 **적용될 때마다 선언 전문을 여기 한 줄 더 남기고**, 되돌리기는
  "이력에서 골라 새 revision 으로 다시 적용" 으로 한다. 이력을 덮어쓰지
  않는다 — 되돌린 것도 앞으로 한 칸 더 간 기록이다.

★revision 은 내용에서 계산한 값이라(`ProjectConfig.compute_revision`) 같은
  내용으로 되돌리면 같은 revision 이 다시 나온다. 그래서 `revision` 은 이
  표에서 고유 키가 아니다. 순서는 `revision_id`(DB) / 줄 순서(파일)다.

★감사 로그(`audit_store`)와 다르다. 감사는 "누가 무엇을 왜 바꿨나" 의 요약이고
  선언 전문을 갖지 않는다. 이력은 **되돌리기 위한 전문**이다. 둘을 합치면
  감사 이벤트가 커지고, 감사를 지우면 복원도 사라진다.

★이 모듈은 도메인을 모른다. 선언을 dict 로만 다룬다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class RevisionStoreError(RuntimeError):
    """이력을 기록하거나 읽을 수 없다."""


class RevisionStore(Protocol):
    """이력을 남기고 찾는 통로. 파일이든 중앙 DB 든 이 창으로만 본다."""

    def append(self, entry: dict[str, Any]) -> None:
        """이력 한 줄 추가. `entry` 는 `revision`·`declaration` 을 반드시 갖는다."""
        ...

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """이 대상의 최신 이력부터 최대 `limit` 건."""
        ...

    def find(self, revision: str) -> dict[str, Any] | None:
        """그 revision 으로 **가장 최근에** 남긴 이력. 없으면 `None`."""
        ...


def _require_shape(entry: dict[str, Any]) -> None:
    if not isinstance(entry.get("revision"), str) or not entry["revision"]:
        raise RevisionStoreError("이력에는 revision 이 있어야 한다")
    if not isinstance(entry.get("declaration"), dict):
        raise RevisionStoreError("이력에는 선언 전문(dict)이 있어야 한다")


class FileRevisionStore:
    """파일 모드 — 선언 파일 곁의 JSONL 한 줄이 이력 한 건이다."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, entry: dict[str, Any]) -> None:
        _require_shape(entry)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush()
        except OSError as exc:
            raise RevisionStoreError(f"이력 파일에 기록하지 못했다: {self.path}") from exc

    def _entries(self) -> list[dict[str, Any]]:
        try:
            with self.path.open(encoding="utf-8") as stream:
                entries: list[dict[str, Any]] = []
                for line in stream:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # 손상된 줄이 나머지 이력을 막아서는 안 된다
                    if isinstance(entry, dict):
                        entries.append(entry)
                return entries
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise RevisionStoreError(f"이력 파일을 읽지 못했다: {self.path}") from exc

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 0:
            raise RevisionStoreError("recent limit 은 0 이상이어야 한다")
        if limit == 0:
            return []
        return list(reversed(self._entries()[-limit:]))

    def find(self, revision: str) -> dict[str, Any] | None:
        if not revision:
            return None
        for entry in reversed(self._entries()):
            if entry.get("revision") == revision:
                return entry
        return None


#: 중앙 이력 테이블. 대상별 이력이 append-only 로 쌓인다.
PROJECT_CONFIG_REVISIONS_TABLE = "project_config_revisions"


class PostgresRevisionStore:
    """중앙 저장소 — 여러 대상의 이력을 한 테이블에 격리해 둔다.

    ★모든 읽기와 쓰기는 `deployment_id` 를 조건으로 삼는다. 같은 revision 이
      여러 줄일 수 있으므로(되돌리면 같은 내용이 다시 나온다) 조회는 최신
      한 줄을 고른다.
    """

    def __init__(self, connection_factory: Any, deployment_id: str) -> None:
        if not deployment_id:
            raise RevisionStoreError("중앙 이력 저장소를 쓰려면 deployment_id 가 있어야 한다")
        self.connection_factory = connection_factory
        self.deployment_id = deployment_id

    def append(self, entry: dict[str, Any]) -> None:
        _require_shape(entry)
        declaration = json.dumps(entry["declaration"], ensure_ascii=False)
        with self.connection_factory() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {PROJECT_CONFIG_REVISIONS_TABLE} "
                    "(deployment_id, revision, previous_revision, declaration, "
                    " actor, reason, event) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (self.deployment_id, entry["revision"], entry.get("previous_revision"),
                     declaration, str(entry.get("actor") or ""),
                     str(entry.get("reason") or ""), str(entry.get("event") or "apply")))

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 0:
            raise RevisionStoreError("recent limit 은 0 이상이어야 한다")
        if limit == 0:
            return []
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT revision, previous_revision, declaration, actor, reason, event, "
                    f"created_at FROM {PROJECT_CONFIG_REVISIONS_TABLE} "
                    "WHERE deployment_id = %s "
                    "ORDER BY revision_id DESC LIMIT %s",
                    (self.deployment_id, limit))
                rows = cur.fetchall()
        return [self._entry(row) for row in rows]

    def find(self, revision: str) -> dict[str, Any] | None:
        if not revision:
            return None
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT revision, previous_revision, declaration, actor, reason, event, "
                    f"created_at FROM {PROJECT_CONFIG_REVISIONS_TABLE} "
                    "WHERE deployment_id = %s AND revision = %s "
                    "ORDER BY revision_id DESC LIMIT 1",
                    (self.deployment_id, revision))
                row = cur.fetchone()
        return None if row is None else self._entry(row)

    def _entry(self, row: Any) -> dict[str, Any]:
        revision, previous, declaration, actor, reason, event, created_at = row
        if isinstance(declaration, str):
            declaration = json.loads(declaration)
        if not isinstance(declaration, dict):
            raise RevisionStoreError(f"이력의 선언이 mapping 이 아니다: {self.deployment_id}")
        return {
            "revision": revision, "previous_revision": previous, "declaration": declaration,
            "actor": actor, "reason": reason, "event": event,
            "timestamp": created_at.isoformat() if created_at is not None else None,
        }


__all__ = ["RevisionStore", "RevisionStoreError", "FileRevisionStore",
           "PostgresRevisionStore", "PROJECT_CONFIG_REVISIONS_TABLE"]
