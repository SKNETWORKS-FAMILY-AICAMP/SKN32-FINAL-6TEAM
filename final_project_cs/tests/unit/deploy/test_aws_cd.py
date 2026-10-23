"""AWS 배포의 검사 관문·자료 보존·교체 실패 복구를 외부 호출 없이 검증한다."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[3] / "deploy/aws_cd.py"
SPEC = importlib.util.spec_from_file_location("aws_cd_under_test", SOURCE)
cd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cd)
SHA = "a" * 40
IMAGE = "registry.example/app@sha256:" + "b" * 64
OLD = "registry.example/app@sha256:" + "c" * 64


def run(name="CI (main)", status="completed", conclusion="success", **extra):
    return {"name": name, "head_sha": SHA, "head_branch": "main", "event": "push",
            "id": 1, "status": status, "conclusion": conclusion, **extra}


def document():
    return {"metadata": {"resourceVersion": "9", "generation": 1},
            "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "unit"}},
                     "strategy": {"type": "Recreate"},
                     "template": {"metadata": {"labels": {"app": "unit"}, "annotations": {"existing": "kept"}},
                                  "spec": {"containers": [{"name": "api", "image": OLD,
                                           "env": [{"name": "DB", "valueFrom": {"secretKeyRef": {"name": "private", "key": "db"}}}],
                                           "envFrom": [{"configMapRef": {"name": "runtime"}}],
                                           "resources": {"limits": {"memory": "1536Mi"}},
                                           "readinessProbe": {"httpGet": {"path": "/health", "port": 8043}}}],
                                           "volumes": [{"name": "facts", "emptyDir": {}}]}}},
            "status": {"observedGeneration": 1, "updatedReplicas": 1,
                       "availableReplicas": 1, "replicas": 1}}


class GateTests(unittest.TestCase):
    def test_main_is_required(self):
        self.assertFalse(cd.checked_runs([run("CI (web)")], SHA))

    def test_pending_web_waits(self):
        self.assertFalse(cd.checked_runs([run(), run("CI (web)", status="in_progress")], SHA))

    def test_every_scheduled_check_must_succeed(self):
        with self.assertRaises(cd.DeploymentError):
            cd.checked_runs([run(), run("CI (admin)", conclusion="failure")], SHA)

    def test_optional_path_filtered_checks_can_be_absent(self):
        self.assertTrue(cd.checked_runs([run()], SHA))

    def test_pr_and_another_revision_cannot_open_gate(self):
        self.assertFalse(cd.checked_runs([run(event="pull_request"), run(head_sha="d" * 40)], SHA))

    def test_newer_failure_is_not_hidden_by_old_success(self):
        with self.assertRaises(cd.DeploymentError):
            cd.checked_runs([run(), run(id=2, conclusion="cancelled")], SHA)

    def test_stale_main_skips_without_reading_other_checks(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/repo", "CD_TRIGGER_SHA": SHA}), \
             patch.object(cd, "command", return_value=SHA), \
             patch.object(cd, "github", return_value={"commit": {"sha": "d" * 40}}) as api, \
             patch.object(cd, "output") as out:
            cd.gate()
        self.assertEqual(api.call_count, 1)
        out.assert_called_once_with("ready", "false")


class PlanTests(unittest.TestCase):
    def test_patch_retains_runtime_configuration_and_input(self):
        before = document()
        saved = copy.deepcopy(before)
        plan = cd.patch_for(before, IMAGE, SHA)
        after = plan[1]["value"]
        self.assertEqual(before, saved)
        self.assertEqual(plan[0], {"op": "test", "path": "/metadata/resourceVersion", "value": "9"})
        original = saved["spec"]["template"]["spec"]
        for key in ["resources", "envFrom", "readinessProbe"]:
            self.assertEqual(after["spec"]["containers"][0][key], original["containers"][0][key])
        self.assertEqual(after["spec"]["volumes"], original["volumes"])
        self.assertEqual(after["spec"]["containers"][0]["env"][0], original["containers"][0]["env"][0])

    def test_mutable_image_is_rejected(self):
        with self.assertRaises(cd.DeploymentError):
            cd.patch_for(document(), "registry.example/app:latest", SHA)

    def test_sidecars_require_explicit_review(self):
        d = document()
        d["spec"]["template"]["spec"]["containers"].append({"name": "sidecar"})
        with self.assertRaises(cd.DeploymentError):
            cd.patch_for(d, IMAGE, SHA)

    def test_migration_is_single_attempt_bounded_and_preserves_secret_refs(self):
        d = document()
        j = cd.migration_job(d, IMAGE, SHA, "123")
        self.assertEqual(j["spec"]["backoffLimit"], 0)
        self.assertEqual(j["spec"]["activeDeadlineSeconds"], 600)
        pod = j["spec"]["template"]["spec"]
        self.assertEqual(pod["restartPolicy"], "Never")
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertNotIn("readinessProbe", pod["containers"][0])
        self.assertEqual(pod["containers"][0]["env"], d["spec"]["template"]["spec"]["containers"][0]["env"])
        compile(pod["containers"][0]["command"][2], "<migration>", "exec")

    def test_failed_or_unknown_job_prevents_another_migration(self):
        for status in [{}, {"failed": 1}, {"active": 1}]:
            with self.subTest(status=status), self.assertRaises(cd.DeploymentError):
                cd.require_clean_jobs([{"status": status}])

    def test_successful_job_does_not_block_next_deployment(self):
        cd.require_clean_jobs([{"status": {"succeeded": 1}}])

    def test_old_database_recovery_point_blocks_deployment(self):
        db = {"DBInstances": [{"BackupRetentionPeriod": 7, "DBInstanceStatus": "available",
               "LatestRestorableTime": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}]}
        with patch.object(cd, "json_command", return_value=db), self.assertRaises(cd.DeploymentError):
            cd.check_database_backup("example")

    def test_short_backup_retention_blocks_deployment(self):
        db = {"DBInstances": [{"BackupRetentionPeriod": 1, "DBInstanceStatus": "available",
               "LatestRestorableTime": datetime.now(timezone.utc).isoformat()}]}
        with patch.object(cd, "json_command", return_value=db), self.assertRaises(cd.DeploymentError):
            cd.check_database_backup("example")

    def test_unobserved_generation_is_not_ready(self):
        d = document()
        d["metadata"]["generation"] = 2
        self.assertFalse(cd.ready(d))

    def test_old_surplus_replica_is_not_complete(self):
        d = document()
        d["status"]["replicas"] = 2
        self.assertFalse(cd.ready(d))


class RolloutTests(unittest.TestCase):
    def exercise(self, *, health_failure=False, patch_reply_lost=False, migration_failure=False):
        state = {name: document() for name in cd.APPS}
        for name, d in state.items():
            d["metadata"]["name"] = name
        before = copy.deepcopy(state)
        events = []
        images = dict.fromkeys(cd.APPS, IMAGE)

        def kube(namespace, action, *args, data=None):
            if action == "get" and args[0] == "jobs":
                return {"items": []}
            if action == "create":
                events.append("migration")
                return {"metadata": {"name": "unit-job"}}
            if action == "get" and args[0] == "job":
                return {"status": {"failed": 1} if migration_failure else {"succeeded": 1}}
            if action == "patch":
                name = args[1]
                operations = json.loads(args[args.index("-p") + 1])
                for operation in operations:
                    if operation["op"] == "replace":
                        field = "template" if operation["path"] == "/spec/template" else "replicas"
                        state[name]["spec"][field] = copy.deepcopy(operation["value"])
                events.append(("patch:" if any(o["path"] == "/spec/template" for o in operations) else "scale:") + name)
                if patch_reply_lost and len([e for e in events if e.endswith(name)]) == 1:
                    raise cd.DeploymentError("The remote patch reply was lost")
                return copy.deepcopy(state[name])
            raise AssertionError((action, args))

        def verify(namespace, expected, sha):
            self.assertTrue(all(state[name]["spec"]["template"]["spec"]["containers"][0]["image"] == IMAGE for name in cd.APPS))
            return {"verified": True}

        with tempfile.TemporaryDirectory(dir=os.environ.get("CD_TEST_ROOT", os.environ.get("RUNNER_TEMP"))) as tmp, \
             patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "42", "RUNNER_TEMP": tmp}), \
             patch.object(cd, "github", return_value={"commit": {"sha": SHA}}), \
             patch.object(cd, "deployment", side_effect=lambda ns, name: copy.deepcopy(state[name])), \
             patch.object(cd, "check_database_backup", return_value="verified"), \
             patch.object(cd, "kubectl", side_effect=kube), \
             patch.object(cd, "command", return_value=""), \
             patch.object(cd, "verify", side_effect=verify), \
             patch.object(cd, "public_health", side_effect=cd.DeploymentError("HTTP failed") if health_failure else None,
                          return_value={"/": 200, "/health": 200}), \
             patch.object(Path, "write_text"):
            if health_failure or patch_reply_lost or migration_failure:
                with self.assertRaises(cd.DeploymentError):
                    cd.deploy(SHA, "unit", images, "https://example.invalid", "example", settle=0)
            else:
                cd.deploy(SHA, "unit", images, "https://example.invalid", "example", settle=0)
        return state, before, events

    def test_success_updates_all_four_apps(self):
        state, _, events = self.exercise()
        self.assertEqual(len([x for x in events if x.startswith("patch:")]), 4)
        self.assertEqual(state["tripilot-worker"]["spec"]["replicas"], 1)
        self.assertTrue(all(d["spec"]["template"]["metadata"]["annotations"][cd.REVISION] == SHA for d in state.values()))

    def test_public_failure_restores_every_app_template(self):
        state, before, _ = self.exercise(health_failure=True)
        self.assertEqual(state, before)

    def test_lost_patch_reply_is_reconciled_and_restored(self):
        state, before, _ = self.exercise(patch_reply_lost=True)
        self.assertEqual(state, before)

    def test_failed_migration_never_changes_app_images(self):
        state, before, events = self.exercise(migration_failure=True)
        self.assertEqual(state, before)
        self.assertFalse(any(x.startswith("patch:") for x in events))


if __name__ == "__main__":
    unittest.main()
