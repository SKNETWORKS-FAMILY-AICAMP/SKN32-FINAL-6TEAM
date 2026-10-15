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
                     patch.object(cd, "has_admin_image", return_value=False), \
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
            with patch.object(cd, "compose") as compose, patch.object(cd, "healthy") as healthy, \
                 patch.object(cd, "has_admin_image", return_value=False):
                cd.start_app("test")
                waited = compose.call_args_list[0].args
                self.assertIn("--wait", waited)
                self.assertNotIn("worker", waited)
                compose.assert_any_call("test", "up", "-d", "worker")
                healthy.assert_called_once_with("test", False)

    def _load(self, tmp):
        with patch.dict(os.environ, {"DEPLOY_BASE": tmp}):
            spec = importlib.util.spec_from_file_location("cd", Path(__file__).with_name("deploy.py"))
            cd = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cd)
        return cd

    def test_admin_started_and_checked_with_the_app_when_its_image_exists(self):
        """관리자웹앱도 고객 웹·API 와 같은 기동 대기·건강 검사를 받는다."""
        with tempfile.TemporaryDirectory() as tmp:
            cd = self._load(tmp)
            with patch.object(cd, "compose") as compose, patch.object(cd, "healthy") as healthy, \
                 patch.object(cd, "has_admin_image", return_value=True):
                cd.start_app("test")
                self.assertEqual(compose.call_args_list[0].args[-5:], ("db", "model-adapter", "api", "web", "admin"))
                self.assertFalse(any("rm" in call.args for call in compose.call_args_list))
                healthy.assert_called_once_with("test", True)

    def test_rollback_to_a_release_without_admin_stops_only_admin(self):
        """관리자웹앱이 없던 옛 판으로 되돌릴 때 나머지는 띄우고 관리자웹앱만 멈춘다."""
        with tempfile.TemporaryDirectory() as tmp:
            cd = self._load(tmp)
            with patch.object(cd, "compose") as compose, patch.object(cd, "healthy") as healthy, \
                 patch.object(cd, "has_admin_image", return_value=False):
                cd.start_app("old")
                self.assertNotIn("admin", compose.call_args_list[0].args)
                compose.assert_any_call("old", "rm", "-s", "-f", "admin")
                healthy.assert_called_once_with("old", False)

    def test_admin_build_uses_same_sha_api_stage_and_skips_runner_without_host_choice(self):
        """제한 빌더는 이 기계 이미지를 못 본다 — API 단계를 bake 의 target:api 로 끼운다.
        받는 주소를 못 고르는 옛 실행기면 0.0.0.0 으로 열리므로 만들지 않는다."""
        with tempfile.TemporaryDirectory() as tmp:
            cd = self._load(tmp)
            release = Path(tmp) / "release"
            src = release / "final_project_cs"
            (src / "deploy").mkdir(parents=True)
            runner = src / "deploy" / "admin_runner.py"
            runner.write_text("host = '0.0.0.0'\n", encoding="utf-8")
            with patch.object(cd, "run") as run:
                self.assertFalse(cd.build_admin(src, release, "abc"))
                run.assert_not_called()
                runner.write_text("host = os.environ.get('ADMIN_HOST', '0.0.0.0')\n", encoding="utf-8")
                self.assertTrue(cd.build_admin(src, release, "abc"))
                args = run.call_args.args
                self.assertEqual((args[:3], args[-1]), (("docker", "buildx", "bake"), "admin"))
                self.assertIn("tripilot-arm", args)
                admin = json.loads((release / "admin-bake.json").read_text())["target"]["admin"]
                self.assertEqual(admin["contexts"], {"tripilot-api:local": "target:api"})
                self.assertEqual(admin["tags"], ["tripilot-arm-admin:abc"])

    def test_health_check_counts_admin_and_its_ports_only_when_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            cd = self._load(tmp)
            opened = []

            class Ok:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *exc): return False

            def urlopen(url, timeout):
                opened.append(url)
                return Ok()

            rows = [{"State": {"Running": True}, "RestartCount": 0}] * 6
            with patch.object(cd.urllib.request, "urlopen", side_effect=urlopen), patch.object(cd.time, "sleep"), \
                 patch.object(cd.subprocess, "check_output", side_effect=["a b c d e f", json.dumps(rows)]):
                cd.healthy("test", True)
            self.assertIn("http://127.0.0.1:3300/", opened)
            self.assertIn("http://127.0.0.1:8070/health", opened)

    def test_overlay_conflict_blocks_sha_once_and_keeps_app(self):
        """덧씌움 충돌은 같은 SHA 를 5분마다 다시 시도하지 않고, 실행 중인 앱을 건드리지 않는다."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"DEPLOY_BASE": tmp}):
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
            cd.CONTROL.mkdir(parents=True)
            cd.OVERLAY.write_text("raise SystemExit(1)\n")
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as tar:
                info = tarfile.TarInfo("final_project_cs")
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            calls = []

            def run(*args, **kwargs):
                calls.append(args)
                if "archive" in args:
                    return subprocess.CompletedProcess(args, 0, stdout=buffer.getvalue())
                if str(cd.OVERLAY) in args:
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(args, 0)

            with patch.object(cd, "git", return_value=new), patch.object(cd, "run", side_effect=run), \
                 patch.object(cd.shutil, "disk_usage", return_value=type("Disk", (), {"free": 20*1024**3})()), \
                 patch.object(cd, "compose") as compose:
                with self.assertRaises(subprocess.CalledProcessError):
                    cd.main()
                state = json.loads(cd.STATE.read_text())
                self.assertEqual((state["current"], state["overlay_blocked_sha"]), (old, new))
                compose.assert_not_called()
                calls.clear()
                cd.main()                              # 다음 회차: 같은 SHA 는 받지도 빌드하지도 않는다
                self.assertFalse(any("archive" in c or "buildx" in c for c in calls))
                compose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
