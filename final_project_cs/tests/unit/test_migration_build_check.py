"""이미지 빌드·배포 도구가 같은 실제 SQL 안전 계약을 사용하며 DB는 열지 않는다."""
import hashlib
import json
from pathlib import Path

from app.infrastructure.db import migrate


def test_build_check_validates_native_deployment_contract_without_database_access(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("build check opened a database connection")
    monkeypatch.setattr(migrate, "get_connection", forbidden)
    monkeypatch.setattr("sys.argv", ["migrate", "--check"])
    migrate.main()
    manifest = json.loads(capsys.readouterr().out)
    assert manifest == migrate.safety_manifest()
    assert manifest["contract_version"] == 2
    current, historical = migrate.migration_files(migrate.MIGRATION_DIR)
    assert manifest["current_count"] == len(current) > 0
    assert set(manifest["historical"]) == {p.name for p in historical}
    assert len(historical) == 4
    paths = [Path(migrate.__file__), Path(migrate.__file__).with_name("migration_plan.py"),
             Path(migrate.__file__).with_name("migration_sql.py"),
             migrate.MIGRATION_DIR / "migration-plan.json", *current, *historical]
    assert manifest["sha256"] == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
