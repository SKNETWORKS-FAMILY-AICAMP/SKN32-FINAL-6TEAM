"""빌드·상태 검사 실패 시 이전 실행판을 보존하는지 검사한다(Linux)."""
import importlib.util
import io
import json
from pathlib import Path
import os
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch


class DeploymentFailureSafety(unittest.TestCase):
    def test_failures_keep_previous_images(self):
        for failed_at in ("build", "health"):
            with self.subTest(failed_at=failed_at), tempfile.TemporaryDirectory() as tmp:
                with patch.dict(os.environ, {"DEPLOY_BASE": tmp}):
                    spec = importlib.util.spec_from_file_location("cd", Path(__file__).with_name("deploy.py"))
                    cd = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(cd)
                old, new = "a" * 40, "b" * 40
                cd.STATE.write_text(json.dumps({"current": old}))
                data = cd.BASE / "mobility" / "processed" / "mobility"
                data.mkdir(parents=True)
                for name in ("line_station_order_v1.json", "transfer_walk_v1.json", "bus_route_v1.jsonl",
                             "bus_stops_v1.jsonl", "station_coords.json", "timetable_v1.jsonl.gz"):
                    (data / name).touch()
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as tar:
                    info = tarfile.TarInfo("final_project_cs")
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    tar.addfile(info)

                def run(*args, **kwargs):
                    if "archive" in args:
                        return subprocess.CompletedProcess(args, 0, stdout=buffer.getvalue())
                    if failed_at == "build" and "buildx" in args:
                        raise subprocess.CalledProcessError(1, args)
                    return subprocess.CompletedProcess(args, 0)

                with patch.object(cd, "git", return_value=new), patch.object(cd, "run", side_effect=run), \
                     patch.object(cd.shutil, "disk_usage", return_value=type("Disk", (), {"free": 20*1024**3})()), \
                     patch.object(cd, "compose") as compose, patch.object(cd, "healthy", side_effect=([RuntimeError("health"), None] if failed_at == "health" else [None])):
                    with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                        cd.main()
                    compose.assert_any_call(old[:12], "up", "-d", "--wait", "--wait-timeout", "360", "db", "model-adapter", "api", "web")
                    compose.assert_any_call(old[:12], "up", "-d", "worker")
                    state = json.loads(cd.STATE.read_text())
                    self.assertEqual((state["current"], state["failed"]), (old, new))

    def test_worker_excluded_from_http_wait_but_all_services_verified(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DEPLOY_BASE": tmp}):
            spec = importlib.util.spec_from_file_location("cd", Path(__file__).with_name("deploy.py"))
            cd = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cd)
            with patch.object(cd, "compose") as compose, patch.object(cd, "healthy") as healthy:
                cd.start_app("test")
                waited = compose.call_args_list[0].args
                self.assertIn("--wait", waited)
                self.assertNotIn("worker", waited)
                compose.assert_any_call("test", "up", "-d", "worker")
                healthy.assert_called_once_with("test")


if __name__ == "__main__":
    unittest.main()
