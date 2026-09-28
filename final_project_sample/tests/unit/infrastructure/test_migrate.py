from pathlib import Path

import pytest

from acop_basement.infrastructure.db import migrate


def _write_migration(directory: Path, filename: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text("-- test migration\n", encoding="utf-8")


def test_collect_migration_files_merges_and_sorts_core_and_domain(tmp_path, monkeypatch):
    core_dir = tmp_path / "core"
    domain_dir = tmp_path / "domain"
    _write_migration(core_dir, "003_core.sql")
    _write_migration(core_dir, "001_core.sql")
    _write_migration(domain_dir, "004_domain.sql")
    _write_migration(domain_dir, "002_domain.sql")
    monkeypatch.setattr(migrate, "CORE_MIGRATIONS_DIR", core_dir)
    monkeypatch.setattr(migrate, "DOMAIN_MIGRATIONS_DIR", domain_dir)

    files = migrate.collect_migration_files()

    assert [path.name for path in files] == [
        "001_core.sql",
        "002_domain.sql",
        "003_core.sql",
        "004_domain.sql",
    ]


def test_main_rejects_duplicate_filename_before_database_connection(
    tmp_path, monkeypatch
):
    core_dir = tmp_path / "core"
    domain_dir = tmp_path / "domain"
    _write_migration(core_dir, "001_schema.sql")
    _write_migration(domain_dir, "001_schema.sql")
    monkeypatch.setattr(migrate, "CORE_MIGRATIONS_DIR", core_dir)
    monkeypatch.setattr(migrate, "DOMAIN_MIGRATIONS_DIR", domain_dir)
    connection_calls = []
    monkeypatch.setattr(
        migrate, "get_connection", lambda: connection_calls.append(True)
    )

    with pytest.raises(RuntimeError, match=r"001_schema\.sql") as exc_info:
        migrate.main()

    message = str(exc_info.value)
    assert str(core_dir) in message
    assert str(domain_dir) in message
    assert connection_calls == []
