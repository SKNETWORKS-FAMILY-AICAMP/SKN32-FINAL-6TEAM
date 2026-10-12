"""이미지 빌드의 SQL 계획 검사는 DB 연결·SQL 실행을 하지 않는다."""
import json
from app.infrastructure.db import migrate


def test_build_check_validates_plan_without_database_access(monkeypatch,capsys):
    def forbidden(): raise AssertionError('build check opened a database connection')
    monkeypatch.setattr(migrate,'get_connection',forbidden)
    monkeypatch.setattr('sys.argv',['migrate','--check'])
    migrate.main()
    manifest=json.loads(capsys.readouterr().out)
    assert manifest['current'] and all(len(row['sha256'])==64 for row in manifest['current'])
    current,historical=migrate.migration_files(migrate.MIGRATION_DIR)
    assert {r['name'] for r in manifest['current']}=={p.name for p in current}
    assert set(manifest['historical'])=={p.name for p in historical}
