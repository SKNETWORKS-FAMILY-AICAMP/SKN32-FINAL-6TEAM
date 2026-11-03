"""Offline tests for tools/disk_guard.py; no git, network or deletion of real data.

Run: DISK_GUARD_TEST_DIR=<scratch dir> python tools/tests/test_disk_guard.py
Temporary files stay beneath DISK_GUARD_TEST_DIR (required, so nothing lands in the system temp dir).
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import disk_guard as dg  # noqa: E402

GB = 10**9


class Usage:
    def __init__(self, free):
        self.free = free


class DiskGuardTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ["DISK_GUARD_TEST_DIR"]) / uuid.uuid4().hex
        self.managed = self.root / "clones"
        self.managed.mkdir(parents=True)
        self.cfg_file = self.root / "cfg.json"
        self.write_cfg()
        self.free = 500 * GB
        patcher = mock.patch.object(dg.shutil, "disk_usage", side_effect=lambda p: Usage(self.free))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_cfg(self, **over):
        cfg = {"min_free_bytes": 30 * GB, "target_free_bytes": 400 * GB, "below_target_policy": "reuse_first",
               "ledger_path": "ledger.json", "managed_roots": [str(self.managed)]}
        cfg.update(over)
        self.cfg_file.write_text(json.dumps({k: v for k, v in cfg.items() if v is not None}), encoding="utf-8")

    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = dg.main(["--config", str(self.cfg_file), *argv])
        return code, json.loads(buf.getvalue())

    def reserve(self, name, owner="w1", expected=None):
        argv = ["reserve", "--source", "C:/src", "--dest", str(self.managed / name), "--owner", owner, "--purpose", "t"]
        if expected is not None:
            argv += ["--expected-bytes", str(expected)]
        return self.run_cli(*argv)

    def make_clone(self, name, size=1000):
        code, _ = self.reserve(name, expected=5 * GB)
        self.assertEqual(code, 0)
        dest = self.managed / name
        dest.mkdir()
        (dest / "f.bin").write_bytes(b"x" * size)
        self.assertEqual(self.run_cli("complete", "--dest", str(dest))[0], 0)
        return dest

    # configuration: fail closed, never default
    def test_missing_config_refuses(self):
        self.cfg_file.unlink()
        code, out = self.run_cli("check", "--path", str(self.root), "--need-bytes", "1")
        self.assertEqual(code, 2)
        self.assertIn("not found", out["error"])

    def test_missing_threshold_key_refuses(self):
        self.write_cfg(min_free_bytes=None)
        code, out = self.run_cli("check", "--path", str(self.root), "--need-bytes", "1")
        self.assertEqual(code, 2)
        self.assertIn("min_free_bytes", out["error"])

    def test_invalid_values_refused(self):
        for bad in ({"min_free_bytes": "30"}, {"min_free_bytes": True}, {"target_free_bytes": 1},
                    {"below_target_policy": "warn"}):
            self.write_cfg(**bad)
            self.assertEqual(self.run_cli("check", "--path", str(self.root), "--need-bytes", "1")[0], 2, bad)

    def test_env_config_used_when_no_flag(self):
        with mock.patch.dict(os.environ, {"TRIPILOT_DISK_GUARD_CONFIG": str(self.cfg_file)}):
            self.assertEqual(dg.config_path(None), self.cfg_file)

    # preflight
    def test_check_allows_and_refuses_at_floor(self):
        self.free = 40 * GB
        self.assertEqual(self.run_cli("check", "--path", str(self.root), "--need-bytes", str(10 * GB))[0], 0)
        code, out = self.run_cli("check", "--path", str(self.root), "--need-bytes", str(10 * GB + 1))
        self.assertEqual(code, 3)
        self.assertEqual(out["free_after_bytes"], 30 * GB - 1)

    def test_check_requires_size(self):
        self.assertEqual(self.run_cli("check", "--path", str(self.root))[0], 2)

    def test_library_require_free(self):
        self.free = 31 * GB
        with self.assertRaises(dg.GuardError) as ctx:
            dg.require_free(str(self.root), 2 * GB, str(self.cfg_file))
        self.assertEqual(ctx.exception.code, 3)

    # reservations and reuse
    def test_unknown_clone_size_refused(self):
        code, out = self.reserve("a")
        self.assertEqual(code, 3)
        self.assertIn("size unknown", out["error"])

    def test_outside_managed_root_refused(self):
        code, _ = self.run_cli("reserve", "--source", "C:/src", "--dest", str(self.root / "elsewhere"),
                               "--owner", "w", "--purpose", "t", "--expected-bytes", "1")
        self.assertEqual(code, 3)

    def test_pending_reservations_count_against_free(self):
        self.free = 50 * GB
        self.assertEqual(self.reserve("a", expected=15 * GB)[0], 0)
        code, out = self.reserve("b", expected=15 * GB)
        self.assertEqual(code, 3)
        self.assertEqual(out["pending_reserved_bytes"], 15 * GB)

    def test_measured_size_reused_as_estimate(self):
        self.make_clone("a", size=1234)
        code, out = self.reserve("b")  # above target, no --expected-bytes: uses measured clone size
        self.assertEqual(code, 0)
        self.assertEqual(out["need_bytes"], 1234)

    def test_below_target_requires_reuse_then_acquire(self):
        dest = self.make_clone("a")
        self.assertEqual(self.run_cli("release", "--dest", str(dest), "--owner", "w1")[0], 0)
        self.free = 100 * GB
        code, out = self.reserve("b", expected=GB)
        self.assertEqual(code, 3)
        self.assertEqual(out["idle"], [str(dest)])
        code, out = self.run_cli("acquire", "--source", "C:/src", "--owner", "w2", "--purpose", "next")
        self.assertEqual((code, out["dest"]), (0, str(dest)))
        self.assertEqual(self.run_cli("acquire", "--source", "C:/src", "--owner", "w3", "--purpose", "x")[0], 3)
        self.assertEqual(self.run_cli("release", "--dest", str(dest), "--owner", "w1")[0], 3)  # not lessee

    def test_below_target_allows_new_when_nothing_reusable(self):
        self.free = 100 * GB
        self.assertEqual(self.reserve("a", expected=GB)[0], 0)

    def test_deny_new_policy(self):
        self.write_cfg(below_target_policy="deny_new")
        self.free = 100 * GB
        self.assertEqual(self.reserve("a", expected=GB)[0], 3)

    def test_existing_destination_refused_and_abandon_rules(self):
        (self.managed / "x").mkdir()
        self.assertEqual(self.reserve("x", expected=1)[0], 3)
        self.assertEqual(self.reserve("y", expected=1)[0], 0)
        self.assertEqual(self.run_cli("abandon", "--dest", str(self.managed / "y"), "--owner", "other")[0], 3)
        self.assertEqual(self.run_cli("abandon", "--dest", str(self.managed / "y"), "--owner", "w1")[0], 0)

    def test_inventory_reports_unregistered(self):
        self.make_clone("a")
        (self.managed / "stray").mkdir()
        code, out = self.run_cli("inventory")
        self.assertEqual(code, 0)
        self.assertEqual(out["unregistered_dirs"], [str(self.managed / "stray")])
        self.assertEqual(out["bytes_by_state"], {"leased": 1000})

    def test_concurrent_reservations_do_not_oversubscribe(self):
        self.free = 60 * GB  # room for exactly two 10 GB clones above the 30 GB floor plus margin < 3
        codes = []

        def worker(i):
            cfg = dg.load_config(self.cfg_file)
            args = dg.parser().parse_args(["reserve", "--source", "C:/src", "--dest", str(self.managed / f"c{i}"),
                                           "--owner", f"w{i}", "--purpose", "t", "--expected-bytes", str(12 * GB)])
            try:
                dg.cmd_reserve(cfg, args)
                codes.append(0)
            except dg.GuardError as exc:
                codes.append(exc.code)
            except Exception as exc:  # surfaced in the assertion instead of vanishing with the thread
                codes.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(map(str, codes)), ["0", "0", "3", "3", "3", "3"])

    def test_guard_never_deletes(self):
        source = Path(dg.__file__).read_text(encoding="utf-8")
        for word in ("rmtree", "os.rmdir", ".unlink(", "Remove-Item", "git reset", "git clean"):
            self.assertNotIn(word, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
