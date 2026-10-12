"""선언(declaration)을 어디에 두는가 — 파일이냐 중앙 저장소냐.

★왜 이 층이 생겼나 (`program/plan/A-COP_Composer_중앙설정저장소_결정.md`)

  설정이 **대상마다의 로컬 파일**이면 그 파일을 고치는 코드(Composer)가 대상
  안에 있어야 한다. 그런데 고객 릴리즈에 쓰기 코드를 넣을 수 없다(보안).
  "관리할 때만 다시 넣는다" 는 대상이 수천 개면 성립하지 않는다.

  그래서 선언을 **중앙 저장소 한 곳**에 둔다. 대상은 자기 선언을 **읽기만**
  하므로 쓰기 코드가 필요 없고, 관리는 중앙에서 한 번에 한다.

★revision 은 **어느 저장소에서든 내용에서 계산한다**(`ProjectConfig.
  compute_revision`). DB 의 `revision` 컬럼은 그 값을 조건부 쓰기(CAS)에
  쓰려고 같이 저장해 두는 것이지, 별도의 진실이 아니다 — 둘이 어긋나면
  내용이 맞다.

★이 모듈은 도메인을 모른다. 선언을 dict 로만 다룬다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import yaml


class ConfigStoreError(RuntimeError):
    """선언을 읽거나 쓸 수 없다."""


class RevisionMismatch(ConfigStoreError):
    """쓰려는 순간 저장소의 revision 이 base_revision 과 달랐다.

    ★"마지막에 쓴 사람이 이긴다" 를 막는다 — 남이 그 사이 바꾼 것을 모르고
      덮어쓰지 않는다.
    """

    def __init__(self, current_revision: str) -> None:
        super().__init__(f"revision mismatch: store has {current_revision}")
        self.current_revision = current_revision


class ConfigStore(Protocol):
    """선언을 읽고 쓰는 통로. 파일이든 중앙 DB 든 이 창으로만 본다."""

    def read(self) -> dict[str, Any]:
        """선언 원본(dict). 없으면 `ConfigStoreError`."""
        ...

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        """`base_revision` 이 지금 값과 같을 때만 원자적으로 바꾼다."""
        ...


class FileConfigStore:
    """지금까지의 동작 — 로컬 YAML 파일.

    ★중앙 저장소로 옮겨도 이 구현은 남긴다. 개발·테스트·단일 배포에서는
      파일이 더 간단하고, 마이그레이션 기간에 두 모드가 공존해야 한다.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigStoreError(f"선언 파일을 읽지 못했다: {self.path}") from exc
        except yaml.YAMLError as exc:
            raise ConfigStoreError(f"선언 파일이 YAML 이 아니다: {self.path}") from exc
        if not isinstance(raw, dict):
            raise ConfigStoreError(f"선언은 mapping 이어야 한다: {self.path}")
        return raw

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        # ★원자적 교체 — 쓰다가 죽어도 원본이 반쪽으로 남지 않는다.
        #   revision 대조는 호출자(`acop_composer.service`)가 잠금 아래에서
        #   이미 했다. 파일 모드는 단일 writer 전제이기 때문이다.
        #
        # ★버그사냥 2026-08-17 (라운드 07) — `os.replace()` 가 실패하면(디스크
        #   오류·권한 문제) staged 파일이 안 지워지고 남았다. `finally` 로
        #   정리한다. 성공했으면 이미 옮겨져 없으므로 `missing_ok=True` 가
        #   조용히 넘어간다.
        staged = self.path.with_name(f".{self.path.stem}.store.{uuid4().hex}.yaml")
        try:
            # 직전 상태 복구용 백업(`docs/handoff/13`). 이력·행위자 기록이
            # 아니므로 감사의 근거로 쓰지 않는다 — 그건 감사 로그가 한다.
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            backup.write_bytes(self.path.read_bytes())

            staged.write_text(
                yaml.safe_dump(declaration, sort_keys=False, allow_unicode=True),
                encoding="utf-8")
            os.replace(staged, self.path)  # POSIX·Windows 모두 원자적
        finally:
            staged.unlink(missing_ok=True)


#: 중앙 저장소 테이블. 대상 하나당 한 행이다.
PROJECT_CONFIGS_TABLE = "project_configs"


class PostgresConfigStore:
    """중앙 저장소 — 대상 수천 개의 선언을 한 곳에 둔다.

    ★쓰기는 **조건부 UPDATE** 다. 프로세스 로컬 락으로는 여러 인스턴스를
      막을 수 없어서(`docs/handoff/13` 이 한계로 적어둔 문제), 조건을 DB 에
      맡긴다 — `WHERE revision = base_revision` 이 한 건도 못 바꾸면 그 사이
      남이 바꾼 것이다.
    """

    def __init__(self, connection_factory: Any, deployment_id: str) -> None:
        if not deployment_id:
            raise ConfigStoreError("중앙 저장소를 쓰려면 deployment_id 가 있어야 한다")
        self.connection_factory = connection_factory
        self.deployment_id = deployment_id

    def read(self) -> dict[str, Any]:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT declaration FROM {PROJECT_CONFIGS_TABLE} "
                    "WHERE deployment_id = %s", (self.deployment_id,))
                row = cur.fetchone()
        if row is None:
            # ★조용히 빈 선언을 주지 않는다. 등록 안 된 대상이 기본값으로
            #   도는 것이 가장 위험하다 — 무엇이 켜져 있는지 아무도 모른다.
            raise ConfigStoreError(
                f"중앙 저장소에 이 대상의 선언이 없다: {self.deployment_id}")
        declaration = row[0]
        if isinstance(declaration, str):
            declaration = json.loads(declaration)
        if not isinstance(declaration, dict):
            raise ConfigStoreError(f"선언이 mapping 이 아니다: {self.deployment_id}")
        return declaration

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        payload = json.dumps(declaration, ensure_ascii=False)
        with self.connection_factory() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {PROJECT_CONFIGS_TABLE} "
                    "SET declaration = %s, revision = %s, updated_at = now() "
                    "WHERE deployment_id = %s AND revision = %s",
                    (payload, new_revision, self.deployment_id, base_revision))
                if cur.rowcount == 1:
                    return
                # 못 바꿨다 — 행이 없거나 revision 이 다르다. 어느 쪽인지 말해준다.
                cur.execute(
                    f"SELECT revision FROM {PROJECT_CONFIGS_TABLE} "
                    "WHERE deployment_id = %s", (self.deployment_id,))
                row = cur.fetchone()
        if row is None:
            raise ConfigStoreError(
                f"중앙 저장소에 이 대상의 선언이 없다: {self.deployment_id}")
        raise RevisionMismatch(str(row[0]))

    def create(self, declaration: dict[str, Any], *, revision: str | None = None) -> None:
        """대상을 처음 등록한다. 이미 있으면 `ConfigStoreError`.

        ★관리 화면의 일상 경로가 아니라 **온보딩** 경로다. 실수로 남의 선언을
          덮어쓰지 않도록 갱신과 분리해 둔다.

        ★revision 을 안 주면 **선언 내용에서 계산한다**(2026-08-30). 예전에는
          호출자가 아무 문자열이나 넣을 수 있었는데, 그 값이 내용과 어긋나면
          이후 모든 쓰기가 CAS 에서 영구히 409 로 막힌다 — `read` 는 내용에서
          계산한 revision 을 돌려주는데 `write` 는 컬럼과 대조하기 때문이다.
          실제로 설정 서비스 테스트에서 이 증상이 났다. 계산 방법은
          `ProjectConfig.compute_revision` 하나뿐이어야 하므로 그것을 쓴다.
        """
        if revision is None:
            from acop_basement.core.project_config import config_from_declaration

            revision = config_from_declaration(
                declaration, source=f"<create:{self.deployment_id}>").revision
        payload = json.dumps(declaration, ensure_ascii=False)
        with self.connection_factory() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {PROJECT_CONFIGS_TABLE} "
                    "(deployment_id, declaration, revision) VALUES (%s, %s, %s) "
                    "ON CONFLICT (deployment_id) DO NOTHING",
                    (self.deployment_id, payload, revision))
                if cur.rowcount != 1:
                    raise ConfigStoreError(
                        f"이미 등록된 대상이다: {self.deployment_id}")


__all__ = ["ConfigStore", "ConfigStoreError", "RevisionMismatch",
           "FileConfigStore", "PostgresConfigStore", "PROJECT_CONFIGS_TABLE"]
