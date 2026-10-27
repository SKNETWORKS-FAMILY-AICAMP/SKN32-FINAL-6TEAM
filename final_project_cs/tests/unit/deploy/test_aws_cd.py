"""AWS 배포의 검사 관문·자료 보존·교체 실패 복구를 외부 호출 없이 검증한다."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

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

    def test_publish_gate_needs_only_main_but_never_a_failed_check(self):
        main_only = ("CI (main)",)
        self.assertTrue(cd.checked_runs([run(), run("CI (web)", status="in_progress")], SHA, required=main_only))
        self.assertFalse(cd.checked_runs([run("CI (web)")], SHA, required=main_only))
        with self.assertRaises(cd.DeploymentError):
            cd.checked_runs([run(), run("CI (web)", conclusion="failure")], SHA, required=main_only)

    def test_publish_gate_reports_ready_without_waiting_for_web(self):
        replies = [{"commit": {"sha": SHA}},
                   {"total_count": 2, "workflow_runs": [run(), run("CI (web)", status="in_progress")]}]
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/repo", "CD_TRIGGER_SHA": SHA}), \
             patch.object(cd, "command", return_value=SHA), \
             patch.object(cd, "github", side_effect=replies), \
             patch.object(cd.time, "sleep", side_effect=AssertionError("must not wait for web")), \
             patch.object(cd, "output") as out:
            cd.gate(main_only=True)
        out.assert_any_call("ready", "true")

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

    def test_migration_bounds_lock_and_statement_waits_inside_the_deadline(self):
        j = cd.migration_job(document(), IMAGE, SHA, "123")
        c = j["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(c["command"][3:], [cd.MIGRATION_RESULT_PATH, cd.MIGRATION_LOCK_TIMEOUT,
                                             cd.MIGRATION_STATEMENT_TIMEOUT])
        self.assertEqual(c["terminationMessagePath"], cd.MIGRATION_RESULT_PATH)
        self.assertLess(cd.seconds(cd.MIGRATION_LOCK_TIMEOUT), cd.seconds(cd.MIGRATION_STATEMENT_TIMEOUT))
        self.assertLess(cd.seconds(cd.MIGRATION_STATEMENT_TIMEOUT), j["spec"]["activeDeadlineSeconds"])

    def test_duration_settings_must_be_explicit_units(self):
        self.assertEqual(cd.seconds("5s"), 5)
        self.assertEqual(cd.seconds("2min"), 120)
        for value in ["5", "0s", "-1s", "five"]:
            with self.subTest(value=value), self.assertRaises(cd.DeploymentError):
                cd.seconds(value)

    def run_migration_script(self, *, error=None, shown=None, commit_error=False):
        """Run the Job script against fake DB modules; return (raised, recorded result, SQL calls)."""
        import sys
        import types

        class FakeDatabaseError(Exception):
            sqlstate = "55P03"

        calls = []
        configured = {}

        class Conn:
            def execute(self, sql, params=()):
                calls.append(sql)
                if "set_config" in sql:
                    configured[params[0]] = params[1]
                    return types.SimpleNamespace(fetchone=lambda: (params[1],))
                value = (shown or {}).get(params[0], configured.get(params[0]))
                return types.SimpleNamespace(fetchone=lambda: (value,))

        class Session:
            def __enter__(self):
                return Conn()

            def __exit__(self, *exc):
                if commit_error and exc[0] is None:
                    raise FakeDatabaseError("connection lost during commit")
                return False

        def apply_all(conn):
            calls.append("apply_all")
            if error:
                raise error("migration statement failed")

        modules = {
            "psycopg": types.SimpleNamespace(Error=FakeDatabaseError),
            "app": types.ModuleType("app"), "app.infrastructure": types.ModuleType("app.infrastructure"),
            "app.infrastructure.db": types.ModuleType("app.infrastructure.db"),
            "app.infrastructure.db.migrate": types.SimpleNamespace(apply_all=apply_all, safety_manifest=lambda: {}),
            "app.infrastructure.db.session": types.SimpleNamespace(get_connection=Session),
        }
        command = cd.migration_job(document(), IMAGE, SHA, "1")["spec"]["template"]["spec"]["containers"][0]["command"]
        with tempfile.TemporaryDirectory(dir=os.environ.get("CD_TEST_ROOT")) as tmp:
            result = Path(tmp) / "termination-log"
            raised = None
            with patch.dict(sys.modules, modules), \
                 patch.object(sys, "argv", ["-c", str(result), "5s", "5min"]), \
                 patch("builtins.print"):
                try:
                    exec(compile(command[2], "<migration>", "exec"), {"__name__": "__main__"})
                except Exception as exc:  # noqa: BLE001 - the script's own failure is under test
                    raised = exc
            recorded = json.loads(result.read_text(encoding="utf-8")) if result.exists() else None
        return raised, recorded, calls, FakeDatabaseError

    def test_migration_commits_after_the_server_accepts_both_bounds(self):
        raised, recorded, calls, _ = self.run_migration_script()
        self.assertIsNone(raised)
        self.assertEqual(recorded, {"migration": "committed"})
        self.assertLess(max(i for i, c in enumerate(calls) if "current_setting" in c), calls.index("apply_all"))

    def test_lock_wait_failure_is_recorded_as_failed_before_commit(self):
        raised, recorded, _, _ = self.run_migration_script(error=type("LockNotAvailable", (Exception,), {"sqlstate": "55P03"}))
        self.assertIsNotNone(raised)
        self.assertEqual(recorded, {"migration": "failed_before_commit", "error": "LockNotAvailable", "sqlstate": "55P03"})

    def test_lost_commit_is_recorded_as_unknown_not_rolled_back(self):
        raised, recorded, _, _ = self.run_migration_script(commit_error=True)
        self.assertIsNotNone(raised)
        self.assertEqual(recorded["migration"], "commit_unknown")

    def test_migration_refuses_when_the_server_did_not_accept_the_bounds(self):
        raised, recorded, calls, _ = self.run_migration_script(shown={"lock_timeout": "0"})
        self.assertIsNotNone(raised)
        self.assertNotIn("apply_all", calls)
        self.assertEqual(recorded["migration"], "failed_before_commit")

    def test_failed_job_block_names_the_recorded_outcome(self):
        failed = {"metadata": {"name": "job-1"}, "status": {"failed": 1}}
        with self.assertRaisesRegex(cd.DeploymentError, "job-1.*failed_before_commit.*55P03"):
            cd.require_clean_jobs([failed], {"job-1": {"migration": "failed_before_commit", "sqlstate": "55P03"}})
        with self.assertRaisesRegex(cd.DeploymentError, "job-1.*unknown"):
            cd.require_clean_jobs([failed], {})

    def test_job_outcome_reads_only_the_allowed_termination_fields(self):
        message = {"migration": "failed_before_commit", "sqlstate": "55P03", "error": "LockNotAvailable",
                   "detail": "row values must never be copied"}
        pods = {"items": [{"status": {"containerStatuses": [{"state": {"terminated": {
            "exitCode": 1, "reason": "Error", "message": json.dumps(message)}}}]}}]}
        with patch.object(cd, "kubectl", return_value=pods) as kube:
            outcome = cd.job_outcome("unit", "job-1")
        kube.assert_called_once_with("unit", "get", "pods", "-l", "job-name=job-1", "-o", "json")
        self.assertEqual(outcome, {"migration": "failed_before_commit", "sqlstate": "55P03",
                                   "error": "LockNotAvailable", "exit_code": 1, "reason": "Error"})
        pods["items"][0]["status"]["containerStatuses"][0]["state"]["terminated"]["message"] = "not json"
        with patch.object(cd, "kubectl", return_value=pods):
            self.assertEqual(cd.job_outcome("unit", "job-1")["migration"], "unknown")
        with patch.object(cd, "kubectl", return_value={"items": []}):
            self.assertEqual(cd.job_outcome("unit", "job-1"), {"migration": "unknown", "reason": "no-pod"})

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

    def test_rollout_wait_uses_only_named_get(self):
        pending = document()
        pending["status"]["availableReplicas"] = 0
        with patch.object(cd, "kubectl", side_effect=[pending, document()]) as kube, \
             patch.object(cd, "command", side_effect=AssertionError("A rollout command must not list deployments")), \
             patch.object(cd.time, "sleep") as sleep:
            cd.wait_for_rollout("unit", "tripilot-api", timeout=2)
        self.assertEqual(kube.call_args_list, [call("unit", "get", "deployment", "tripilot-api", "-o", "json")] * 2)
        sleep.assert_called_once_with(3)

    def test_rollout_wait_stops_when_the_named_deployment_stays_unready(self):
        pending = document()
        pending["status"]["availableReplicas"] = 0
        with patch.object(cd, "kubectl", return_value=pending), \
             patch.object(cd.time, "monotonic", side_effect=[0, 3]), \
             patch.object(cd.time, "sleep") as sleep, self.assertRaises(cd.DeploymentError):
            cd.wait_for_rollout("unit", "tripilot-api", timeout=2)
        sleep.assert_not_called()

    def test_public_probe_identifies_itself_to_the_edge(self):
        requests = []

        def opened(request, *, timeout):
            requests.append(request)
            response = io.BytesIO(b'{"status":"ok"}' if request.full_url.endswith("/health") else b"home")
            response.status = 200
            return response

        with patch.object(cd.urllib.request, "urlopen", side_effect=opened):
            self.assertEqual(cd.public_health("https://example.invalid"), {"/health": 200, "/": 200})
        self.assertEqual([r.full_url for r in requests], ["https://example.invalid/health", "https://example.invalid/"])
        self.assertTrue(all(r.get_header("User-agent") == "Guguroute-Deployment/1.0" for r in requests))

    def test_identified_probe_still_rejects_unhealthy_api(self):
        response = io.BytesIO(b'{"status":"degraded"}')
        response.status = 200
        with patch.object(cd.urllib.request, "urlopen", return_value=response) as opened, \
             self.assertRaises(cd.DeploymentError):
            cd.public_health("https://example.invalid")
        self.assertEqual(opened.call_count, 1)


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

        writes = {}

        def written(path, text, *args, **kwargs):
            writes[Path(path).name] = json.loads(text)

        with tempfile.TemporaryDirectory(dir=os.environ.get("CD_TEST_ROOT", os.environ.get("RUNNER_TEMP"))) as tmp, \
             patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/repo", "GITHUB_RUN_ID": "42", "RUNNER_TEMP": tmp}), \
             patch.object(cd, "github", return_value={"commit": {"sha": SHA}}), \
             patch.object(cd, "deployment", side_effect=lambda ns, name: copy.deepcopy(state[name])), \
             patch.object(cd, "check_database_backup", return_value="verified"), \
             patch.object(cd, "kubectl", side_effect=kube), \
             patch.object(cd, "job_outcome", return_value={"migration": "failed_before_commit", "sqlstate": "55P03"}), \
             patch.object(cd, "command", return_value=""), \
             patch.object(cd, "verify", side_effect=verify), \
             patch.object(cd, "public_health", side_effect=cd.DeploymentError("HTTP failed") if health_failure else None,
                          return_value={"/": 200, "/health": 200}), \
             patch.object(Path, "write_text", autospec=True, side_effect=written):
            if health_failure or patch_reply_lost or migration_failure:
                with self.assertRaises(cd.DeploymentError):
                    cd.deploy(SHA, "unit", images, "https://example.invalid", "example", settle=0)
            else:
                cd.deploy(SHA, "unit", images, "https://example.invalid", "example", settle=0)
        self.writes = writes
        return state, before, events

    def test_success_records_stage_durations(self):
        self.exercise()
        result = self.writes["aws-deploy-result.json"]
        self.assertEqual(list(result["timings"]), ["preflight", "migration", "worker-pause", *[f"rollout:{n}" for n in cd.APPS],
                                                   "verify"])
        self.assertTrue(all(isinstance(v, float) and v >= 0 for v in result["timings"].values()))
        self.assertNotIn("aws-deploy-failure.json", self.writes)

    def test_failed_migration_records_its_stage_and_outcome(self):
        self.exercise(migration_failure=True)
        failure = self.writes["aws-deploy-failure.json"]
        self.assertEqual(failure["stage"], "migration")
        self.assertEqual(failure["migration"], {"migration": "failed_before_commit", "sqlstate": "55P03"})
        self.assertEqual(failure["recovery"], "not-needed")

    def test_public_failure_records_stage_and_restoration(self):
        self.exercise(health_failure=True)
        failure = self.writes["aws-deploy-failure.json"]
        self.assertEqual(failure["stage"], "verify")
        self.assertEqual(failure["error"], "DeploymentError: HTTP failed")
        self.assertEqual(failure["recovery"], "restored")

    def test_failure_record_never_copies_foreign_exception_text(self):
        record = cd.failure_record(SHA, "rollout:tripilot-api", RuntimeError("https://private.invalid/token=1"), {}, None, "restored")
        self.assertEqual(record["error"], "RuntimeError")

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


class WorkflowTests(unittest.TestCase):
    def test_publication_overlaps_ci_but_deployment_waits_for_the_full_gate(self):
        text = (SOURCE.parents[2] / ".github/workflows/cd-aws.yml").read_text(encoding="utf-8")
        order = [text.index(marker) for marker in (
            "aws_cd.py gate --main-only", "aws_cd.py publish", "aws_cd.py gate\n", "aws_cd.py deploy")]
        self.assertEqual(order, sorted(order))
        deploy_step = text[text.index("- name: Migrate atomically"):text.index("aws_cd.py deploy")]
        self.assertIn("steps.gate.outputs.ready == 'true'", deploy_step)
        self.assertIn("steps.gate.outputs.sha == steps.publishable.outputs.sha", deploy_step)


if __name__ == "__main__":
    unittest.main()
