"""요식 다시 적재 도구가 코어 DB 를 지우지 않는다 (2026-09-28 cs, 09-30 팀 `--target core` 와 합침).

요식 표가 코어 DB(`acop_cs`)로 들어오면서, 이 도구의 기본 동작(「DB 를 지우고 새로 만들기」)이
옵션 하나 빠뜨리면 여행·고객·일정을 통째로 지울 수 있게 됐다. psql 을 부르지 않고 부르는 SQL 만 본다.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
_spec = importlib.util.spec_from_file_location("dining_rebuild", os.path.join(ROOT, "scripts", "dining", "rebuild.py"))
rebuild = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rebuild)

TABLE_T = "\n".join([" ?column? ", "----------", " t", "(1 row)", ""])
TABLE_F = "\n".join([" ?column? ", "----------", " f", "(1 row)", ""])


def _fake(monkeypatch, *, exists=True, disposable=False, core=True, broken=False, trips_empty=False):
    """DB 상태를 흉내 낸다 — 있나 · 이 도구가 만든 일회용인가 · 코어 표가 있나 · 확인이 실패하나 · 여행이 비었나."""
    asked: list[str] = []

    def yes(flag: bool) -> tuple[bool, str]:
        return True, TABLE_T if flag else TABLE_F

    def run_sql(db, path=None, sql=None, stop_on_error=True):
        asked.append(sql or os.path.basename(path or ""))
        text = sql or ""
        if "FROM pg_database WHERE datname =" in text and "EXISTS" in text:
            return yes(exists)
        if "shobj_description" in text:
            return (False, "권한 없음") if broken else yes(disposable)
        if "IS NULL OR NOT EXISTS (SELECT 1 FROM public.trips)" in text:
            return yes(trips_empty)
        if "IS NOT NULL OR to_regclass('public.trips')" in text.replace("\n", " ").replace("  ", " ") \
                or "to_regclass('public.places') IS NOT NULL OR" in text:
            return yes(core)
        if text.strip() == "SELECT to_regclass('public.places')":          # has_core_places
            return True, " to_regclass \n-------------\n places\n" if core else " to_regclass \n-------------\n \n"
        return True, ""
    monkeypatch.setattr(rebuild, "run_sql", run_sql)
    monkeypatch.setattr(rebuild, "check", lambda: True)
    monkeypatch.setattr(rebuild, "build_core", lambda db: asked.append("BUILD_CORE") or True)
    monkeypatch.setattr(rebuild, "run_py", lambda script: (False, "멈춤"))   # 적재 전에 끊는다
    monkeypatch.setattr(rebuild, "PG_USER", "postgres")
    return asked


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["rebuild.py", *argv])
    return rebuild.main()


def test_코어_DB_는_옵션_없이는_거부하고_지우지_않는다(monkeypatch):
    asked = _fake(monkeypatch)
    assert _run(monkeypatch, "--db", "acop_cs") == 1
    assert not any("DROP DATABASE" in a for a in asked)


def test_여행이_비어_있어도_코어_표가_있으면_지킨다(monkeypatch):
    """☆처음 판정은 「여행 행이 있나」여서 여행이 비면 지우는 쪽으로 갔다(코덱스 구현 검토)."""
    asked = _fake(monkeypatch, core=True)
    assert _run(monkeypatch, "--db", "empty_core") == 1
    assert not any("DROP DATABASE" in a for a in asked)


def test_확인이_실패하면_지킨다(monkeypatch):
    asked = _fake(monkeypatch, broken=True)
    assert _run(monkeypatch, "--db", "acop_cs") == 1
    assert not any("DROP DATABASE" in a for a in asked)


def test_코어_DB_에_keep_이면_코어_시드를_다시_넣지_않고_적재_계정으로_돈다(monkeypatch):
    asked = _fake(monkeypatch)
    _run(monkeypatch, "--db", "acop_cs", "--keep")
    assert not any("DROP DATABASE" in a or "DROP SCHEMA" in a for a in asked)
    assert "BUILD_CORE" not in asked                     # 여행 시드가 운영 DB 에 들어가지 않는다
    assert rebuild.PG_USER == rebuild.LOADER_USER


def test_이_도구가_만든_일회용_DB_는_지우고_새로_만들며_표시를_남긴다(monkeypatch):
    asked = _fake(monkeypatch, disposable=True)
    _run(monkeypatch, "--db", "dining_rebuild")
    assert any("DROP DATABASE" in a for a in asked)
    assert any(rebuild.DISPOSABLE in a and "COMMENT ON DATABASE" in a for a in asked)


def test_dining_으로_시작하는_DB_는_여행이_비었다고_확인될_때만_지운다(monkeypatch):
    """요식 팀 규칙(이름 접두어)을 받아 주되 이름만 믿지 않는다."""
    empty = _fake(monkeypatch, trips_empty=True)
    _run(monkeypatch, "--db", "dining_dev")
    assert any("DROP DATABASE" in a for a in empty)
    busy = _fake(monkeypatch, trips_empty=False)
    assert _run(monkeypatch, "--db", "dining_dev") == 1
    assert not any("DROP DATABASE" in a for a in busy)


def test_없는_DB_는_새로_만든다(monkeypatch):
    asked = _fake(monkeypatch, exists=False)
    _run(monkeypatch, "--db", "dining_brand_new")     # 팀 규칙: 새로 만드는 DB 이름은 dining_ 으로 시작
    assert any("CREATE DATABASE" in a for a in asked)


# ── `--target core` : 팀 방식(요식 칸만 지우고 다시 채운다) + 우리 안전장치 ─────────────

def test_target_core_는_DB_를_지우지_않고_요식_칸만_지운다(monkeypatch):
    asked = _fake(monkeypatch)
    _run(monkeypatch, "--db", "acop_cs", "--target", "core")
    assert any(a == "DROP SCHEMA IF EXISTS dining CASCADE" for a in asked)
    assert not any("DROP DATABASE" in a for a in asked)
    assert "BUILD_CORE" not in asked                     # 코어 마이그레이션·시드는 다시 돌리지 않는다


def test_target_core_는_칸을_새로_만든_뒤_적재_계정_권한을_다시_주고_그_계정으로_돈다(monkeypatch):
    """칸이 지워질 때 dining_loader 의 권한도 사라진다 — 223 을 다시 돌리지 않으면 이 뒤 적재가 권한 오류로 멈춘다."""
    asked = _fake(monkeypatch)
    _run(monkeypatch, "--db", "acop_cs", "--target", "core")
    grants = [i for i, a in enumerate(asked) if a == rebuild.LOADER_GRANTS]
    drop = asked.index("DROP SCHEMA IF EXISTS dining CASCADE")
    migrations = [i for i, a in enumerate(asked) if a.endswith("_dining_notice_scope.sql") or a.endswith("_dining_schema.sql")]
    assert grants and grants[0] > drop
    assert all(m < grants[0] for m in migrations)         # 표를 만든 다음에 권한을 준다
    assert rebuild.PG_USER == rebuild.LOADER_USER


def test_target_core_는_코어_표가_없으면_거부한다(monkeypatch):
    asked = _fake(monkeypatch, core=False)
    assert _run(monkeypatch, "--db", "only_dining", "--target", "core") == 1
    assert not any("DROP SCHEMA" in a for a in asked)


def test_테넌트_이름이_이상하면_SQL_을_만들지_않는다():
    for bad in ("demo'; DROP TABLE trips;--", "", None):
        with pytest.raises(SystemExit):
            rebuild.promote_sql(bad)
        with pytest.raises(SystemExit):
            rebuild.link_sql(bad)
