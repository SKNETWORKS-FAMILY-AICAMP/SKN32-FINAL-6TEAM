"""Composer 가 쓰는 저장소 — **이 제품의 구현**.

★파일만 있다. cs 는 direct(pip) 방식이라 선언이 이 저장소의 로컬 파일이다
  (v9 §8-D, D-007: "기본은 direct(pip), central 은 UI 옵션"). 중앙 저장소를
  쓰게 되면 그때 여기에 Postgres 구현을 더한다 — **지금 없는 것을 있는 척
  만들지 않는다.**

★모양은 `acop_composer.stores` 의 Protocol 이 정한다. 이 파일은 그 Protocol 을
  import 하지 않는다 — 선택 패키지를 안 깔아도 이 모듈은 열려야 하기 때문이다.
  이어 붙이는 곳은 `app/composer_host.py` 하나다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml


class StoreError(RuntimeError):
    """저장소가 요청을 수행하지 못했다."""


class RevisionMismatch(StoreError):
    """쓰려는 순간 저장소의 revision 이 base_revision 과 달랐다."""

    def __init__(self, current_revision: str) -> None:
        super().__init__(f"revision mismatch: store has {current_revision}")
        self.current_revision = current_revision


class FileConfigStore:
    """선언 YAML 파일 하나."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise StoreError(f"선언 파일을 읽지 못했다: {self.path}") from exc
        except yaml.YAMLError as exc:
            raise StoreError(f"선언 파일이 YAML 이 아니다: {self.path}") from exc
        if not isinstance(raw, dict):
            raise StoreError(f"선언은 mapping 이어야 한다: {self.path}")
        return raw

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        """★원자적 교체 — 쓰다가 죽어도 원본이 반쪽으로 남지 않는다.

        revision 대조는 호출자(`acop_composer.service`)가 잠금 아래에서 이미
        했다. 파일 모드는 **단일 writer 전제**라 여기서 다시 하지 않는다 —
        여러 프로세스가 같은 파일을 쓰는 형태가 되면 그때는 파일 락이나 중앙
        저장소의 조건부 쓰기가 필요하다.

        ★staged 파일은 `finally` 로 지운다. `os.replace()` 가 실패하면(디스크
          오류·권한) 남아서 쌓인다(sample 버그사냥 2026-08-17 라운드 07).
        """
        staged = self.path.with_name(f".{self.path.stem}.store.{uuid4().hex}.yaml")
        try:
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            backup.write_bytes(self.path.read_bytes())
            staged.write_text(
                yaml.safe_dump(declaration, sort_keys=False, allow_unicode=True),
                encoding="utf-8")
            os.replace(staged, self.path)  # POSIX·Windows 모두 원자적
        finally:
            staged.unlink(missing_ok=True)


class _JsonlStore:
    """append-only JSONL. ★고치거나 지우지 않는다."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, entry: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            # ★삼키지 않는다 — 부르는 쪽이 500 으로 올린다. 감사를 못 남겼는데
            #   성공으로 답하면 그게 조용한 성공 위장이다.
            raise StoreError(f"기록하지 못했다: {self.path}") from exc

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise StoreError(f"읽지 못했다: {self.path}") from exc
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                # ★깨진 줄을 건너뛰지 않는다. 이 파일은 감사·이력이고, 우리만
                #   append 한다 — 깨진 줄이 있다는 건 뭔가 잘못됐다는 뜻이다.
                #   조용히 넘기면 "이력에 없다" 와 "이력을 못 읽는다" 가 같은
                #   모습이 되고, 되돌리기가 **없는 이유를 모른 채** 실패한다.
                raise StoreError(f"{self.path}:{number} 줄이 JSON 이 아니다") from exc
            if not isinstance(row, dict):
                raise StoreError(f"{self.path}:{number} 줄이 object 가 아니다")
            rows.append(row)
        return rows


class FileRevisionStore(_JsonlStore):
    """선언 이력."""

    def recent(self, limit: int) -> list[dict[str, Any]]:
        rows = self._rows()
        return list(reversed(rows))[:limit] if limit else []

    def find(self, revision: str) -> dict[str, Any] | None:
        for row in reversed(self._rows()):
            if row.get("revision") == revision:
                return row
        return None


class FileAuditStore(_JsonlStore):
    """누가 언제 무엇을 바꿨는가."""

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        for row in reversed(self._rows()):
            if row.get("idempotency_key") == key:
                return row
        return None


__all__ = [
    "FileAuditStore", "FileConfigStore", "FileRevisionStore",
    "RevisionMismatch", "StoreError",
]
