"""DB 필요 시험 목록(tests/conftest.py 의 DB_TEST_FILES)에 없어진 파일이 남지 않게 한다."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _db_test_files() -> tuple[str, ...]:
    tree = ast.parse((ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "DB_TEST_FILES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("tests/conftest.py 에 DB_TEST_FILES 가 없다")


def test_db_marked_files_all_exist():
    missing = [rel for rel in _db_test_files() if not (ROOT / rel).is_file()]
    assert not missing, f"DB_TEST_FILES 가 없는 파일을 가리킨다: {missing}"
