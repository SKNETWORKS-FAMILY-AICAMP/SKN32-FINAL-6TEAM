"""관리자웹앱 비공개 설정 도구가 값을 깨지 않고, 남의 계정을 지우지 않는지 검사한다."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


def load(env_file):
    with patch.dict(os.environ, {"ADMIN_ENV_FILE": str(env_file)}):
        spec = importlib.util.spec_from_file_location("admin_env", Path(__file__).with_name("admin_env.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class AdminEnvFile(unittest.TestCase):
    def test_hash_with_dollar_signs_round_trips_single_quoted_and_private(self):
        """해시의 `$` 를 Compose 가 변수로 읽지 않게 홑따옴표로 쓰고, 다시 읽으면 그대로다."""
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env.admin"
            tool = load(env)
            value = json.dumps([{"id": "op-a", "password_hash": "pbkdf2_sha256$600000$c2FsdA$ZGln", "scopes": []}])
            tool.write({"ACOP_UI_OPERATORS": value})
            self.assertEqual(env.read_text(encoding="utf-8"), f"ACOP_UI_OPERATORS='{value}'\n")
            self.assertEqual(tool.read()["ACOP_UI_OPERATORS"], value)
            self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)

    def test_remove_keeps_other_operators_and_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env.admin"
            tool = load(env)
            people = [{"id": "op-a", "password_hash": "x", "scopes": []}, {"id": "op-b", "password_hash": "y", "scopes": []}]
            tool.write({"ACOP_UI_OPERATORS": json.dumps(people), "ACOP_OPS_API_KEYS": '{"action:approve":"k"}'})
            with redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(["remove", "--id", "op-a"]), 0)
            rows = tool.read()
            self.assertEqual([row["id"] for row in json.loads(rows["ACOP_UI_OPERATORS"])], ["op-b"])
            self.assertEqual(rows["ACOP_OPS_API_KEYS"], '{"action:approve":"k"}')

    def test_list_never_prints_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env.admin"
            tool = load(env)
            tool.write({"ACOP_UI_OPERATORS": json.dumps([{"id": "op-a", "password_hash": "SECRET-HASH", "scopes": []}]),
                        "ACOP_OPS_API_KEYS": '{"action:approve":"SECRET-KEY"}'})
            out = io.StringIO()
            with redirect_stdout(out):
                tool.main(["list"])
            self.assertIn("op-a", out.getvalue())
            self.assertNotIn("SECRET", out.getvalue())


if __name__ == "__main__":
    unittest.main()
