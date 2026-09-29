"""요식 다시 적재 도구가 코어 DB 를 지우지 않는다 (2026-09-28 cs).

요식 표가 코어 DB(`acop_cs`)로 들어오면서, 이 도구의 기본 동작(「DB 를 지우고 새로 만들기」)이
옵션 하나 빠뜨리면 여행·고객·일정을 통째로 지울 수 있게 됐다. psql 을 부르지 않고 부르는 SQL 만 본다.
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
_spec = importlib.util.spec_from_file_location("dining_rebuild", os.path.join(ROOT, "scripts", "dining", "rebuild.py"))
rebuild = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rebuild)

TABLE_T = "\n".join([" ?column? ", "----------", " t", "(1 row)", ""])
TABLE_F = "\n".join([" ?column? ", "----------", " f", "(1 row)", ""])


def _fake(monkeypatch, *, exists=True, disposable=False, core=True, broken=False):
    """DB 상태를 흉내 낸다 — 있나 · 이 도구가 만든 일회용인가 · 코어 표가 있나 · 확인이 실패하나."""
    asked: list[str] = []

    def run_sql(db, path=None, sql=None, stop_on_error=True):
        asked.append(sql or path or "")
        text = sql or ""
        if "FROM pg_database WHERE datname =" in text and "EXISTS" in text:
            return True, TABLE_T if exists else TABLE_F
        if "shobj_description" in text:
            return (False, "권한 없음") if broken else (True, TABLE_T if disposable else TABLE_F)
        if "to_regclass('public.places')" in text:
            return True, TABLE_T if core else TABLE_F
        return True, ""
    monkeypatch.setattr(rebuild, "run_sql", run_sql)
    monkeypatch.setattr(rebuild, "check", lambda: True)
    monkeypatch.setattr(rebuild, "build_core", lambda db: asked.append("BUILD_CORE") or True)
    monkeypatch.setattr(rebuild, "run_py", lambda script: (False, "멈춤"))   # 적재 전에 끊는다
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
    monkeypatch.setattr(rebuild, "PG_USER", "postgres")
    _run(monkeypatch, "--db", "acop_cs", "--keep")
    assert not any("DROP DATABASE" in a for a in asked)
    assert "BUILD_CORE" not in asked                     # 여행 시드가 운영 DB 에 들어가지 않는다
    assert rebuild.PG_USER == rebuild.LOADER_USER


def test_이_도구가_만든_일회용_DB_는_지우고_새로_만들며_표시를_남긴다(monkeypatch):
    asked = _fake(monkeypatch, disposable=True)
    _run(monkeypatch, "--db", "dining_rebuild")
    assert any("DROP DATABASE" in a for a in asked)
    assert any(rebuild.DISPOSABLE in a and "COMMENT ON DATABASE" in a for a in asked)


def test_없는_DB_는_새로_만든다(monkeypatch):
    asked = _fake(monkeypatch, exists=False)
    _run(monkeypatch, "--db", "brand_new")
    assert any("CREATE DATABASE" in a for a in asked)


def test_테넌트_이름이_이상하면_SQL_을_만들지_않는다():
    import pytest
    for bad in ("demo'; DROP TABLE trips;--", "", None):
        with pytest.raises(SystemExit):
            rebuild.promote_sql(bad)
        with pytest.raises(SystemExit):
            rebuild.link_sql(bad)
