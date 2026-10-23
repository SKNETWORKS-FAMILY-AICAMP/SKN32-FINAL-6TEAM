"""배포 성공 뒤 이미지 정리 연결을 검사한다(Linux). 정리가 깨져도 배포 결과를 바꾸면 안 된다."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load_deploy(base):
    with patch.dict(os.environ, {"DEPLOY_BASE": str(base)}):
        spec = importlib.util.spec_from_file_location("cd_retention", HERE / "deploy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class RetentionHook(unittest.TestCase):
    def test_prune_keeps_current_and_previous_and_removes_unreferenced_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            cd = load_deploy(tmp)
            sys.path.insert(0, str(HERE.parent))
            import image_retention as ir
            current, previous, old = "a" * 40, "b" * 40, "c" * 40
            for sha in (current, previous, old):
                (cd.BASE / "releases" / sha).mkdir(parents=True)
            seen = {}

            def fake_run(docker, **kw):
                seen.update(kw)
                return {"apps": {"keep": {current[:12]: "최근", previous[:12]: "최근"}}}
            with patch.object(ir, "run_retention", fake_run), patch.object(ir, "Docker", lambda: object()):
                cd.prune_old_releases({"current": current, "previous": previous,
                                       "history": [{"sha": current, "at": 1.0}]})
            self.assertEqual(seen["app_repos"], ["tripilot-arm-api", "tripilot-arm-web"])
            self.assertEqual(seen["protected_tags"], [current[:12], previous[:12]])
            self.assertTrue(seen["apply"])
            self.assertIn(current, {k for k in map(lambda d: d.name, (cd.BASE / "releases").iterdir())})
            self.assertEqual(sorted(p.name for p in (cd.BASE / "releases").iterdir()), sorted([current, previous]))

    def test_cleanup_failure_is_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cd = load_deploy(tmp)
            sys.path.insert(0, str(HERE.parent))
            import image_retention as ir
            with patch.object(ir, "run_retention", side_effect=RuntimeError("docker 없음")):
                cd.prune_old_releases({"current": "a" * 40})      # 예외 없이 끝나야 한다


if __name__ == "__main__":
    unittest.main()
