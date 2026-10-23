"""시험은 임시 폴더·mock 응답만 사용한다. 실제 HTTP 시험과 구분한다."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DEPLOY_BASE", tempfile.gettempdir())
import serving_queue as queue
import serving_checks as checks


def empty():
    return {"jobs": [], "estimates": {}, "failed_profiles": {}}


class QueueTests(unittest.TestCase):
    def test_six_hour_budget_and_no_duplicate_refill(self):
        state = empty()
        self.assertEqual(queue.refill(state, 21600, "a"), 45)
        self.assertEqual(queue.refill(state, 21600, "a"), 0)
        self.assertEqual(state["estimated_pending_seconds"], 21600)
        self.assertEqual(len({j["id"] for j in state["jobs"]}), 45)

    def test_completed_work_replenished_using_measurement(self):
        state = empty()
        queue.refill(state, 21600, "a")
        job = state["jobs"][0]
        job["sha"] = "a"
        queue.finish(state, job["id"], {"passed": 11, "total": 11, "seconds": 60}, 21660)
        self.assertEqual(state["estimates"][job["profile"]], 270)
        self.assertGreater(queue.refill(state, 21660, "a"), 0)
        self.assertGreaterEqual(state["estimated_pending_seconds"], queue.HORIZON)

    def test_failed_front_profile_skipped_not_retried(self):
        state = empty()
        queue.refill(state, 21600, "a")
        first = state["jobs"][0]
        first["sha"] = "a"
        queue.finish(state, first["id"], {"passed": 1, "total": 11, "seconds": 2}, 21602)
        self.assertNotEqual(queue.select_job(state, "a")["profile"], first["profile"])
        for profile in checks.PROFILES:
            state["failed_profiles"][profile] = "a"
        self.assertIsNone(queue.select_job(state, "a"))
        self.assertIsNotNone(queue.select_job(state, "b"))

    def test_crash_recovery_preserves_unfinished_failure(self):
        state = empty()
        queue.refill(state, 21600, "a")
        state["jobs"][0].update(status="running", sha="a")
        with tempfile.TemporaryDirectory() as tmp, patch.object(queue, "ROOT", Path(tmp)):
            queue.recover(state)
        self.assertEqual(state["jobs"][0]["status"], "interrupted")
        self.assertEqual(state["failed_profiles"][state["jobs"][0]["profile"]], "a")

    def test_lock_prevents_second_worker(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp, patch.object(queue, "ROOT", Path(tmp)), patch.object(queue, "step") as step:
            with (Path(tmp) / "worker.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                queue.worker(once=True)
            step.assert_not_called()

    def test_no_deployed_app_does_not_send_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "state.json").write_text(json.dumps({"blocked_on": "mobility_data_missing"}))
            with patch.object(queue, "BASE", base), patch.object(queue, "ROOT", base / "queue"), patch.object(queue.probe, "run") as run:
                self.assertFalse(queue.step())
                state = json.loads((base / "queue" / "queue.json").read_text())
                self.assertEqual(state["blocked_on"], "mobility_data_missing")
                self.assertEqual(len(state["jobs"]), 0)
                run.assert_not_called()


class ChecksTests(unittest.TestCase):
    def test_setup_failure_keeps_all_eleven_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "state.json").write_text('{"current":"a"}')
            with patch.object(checks, "BASE", base), patch.object(checks.probe, "call", side_effect=ConnectionError):
                summary = checks.run("context_cache", base / "output")
            self.assertEqual(summary["total"], 11)
            self.assertEqual(summary["attempted"], 4)
            self.assertEqual(summary["passed"], 0)
            rows = json.loads((base / "output" / "answers.json").read_text())
            self.assertEqual(sum(not r["attempted"] for r in rows), 7)

    def test_nested_secrets_removed(self):
        self.assertEqual(checks.redact({"x": [{"user_key": "secret", "answer": "ok"}]}), {"x": [{"answer": "ok"}]})

    def test_success_records_full_contract_denominator(self):
        results = [(200, {}, 0), (401, {}, 0), (201, {"user_key": "owner"}, 0),
                   (201, {"user_key": "other"}, 0), (201, {"trip_id": "trip"}, 0),
                   (200, {}, 0), (404, {}, 0)] + [
                       (200, {"answer": "경복궁 10:00~11:00", "status": "answered", "reason": "decision_answer_fact"}, 0),
                       (200, {"answer": "점심 12:00~13:00", "status": "answered", "reason": "decision_answer_fact"}, 0),
                       (200, {"answer": "여행 안내", "status": "answered", "reason": "decision_other"}, 0),
                       (200, {"answer": "경복궁 10:00, 점심 12:00", "status": "answered", "reason": "decision_answer_fact"}, 0)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "state.json").write_text('{"current":"a"}')
            with patch.object(checks, "BASE", base), patch.object(checks.probe, "call", side_effect=results):
                summary = checks.run("mixed_travel", base / "output")
            self.assertEqual((summary["passed"], summary["total"], summary["attempted"]), (11, 11, 11))

    def test_http200_model_error_is_not_success(self):
        response = {"answer": "지금 요청을 해석하지 못했어요", "status": "escalated",
                    "reason": "decision_failed", "failure": "OllamaContentError"}
        self.assertFalse(checks.valid_travel_answer(response, "language_style", 3))

    def test_http200_wrong_time_is_not_success(self):
        response = {"answer": "첫 일정은 12:00입니다", "status": "answered", "reason": "decision_answer_fact"}
        self.assertFalse(checks.valid_travel_answer(response, "language_style", 0))

    def test_mixed_request_requires_both_times(self):
        response = {"answer": "경복궁은 10:00입니다", "status": "answered", "reason": "decision_answer_fact"}
        self.assertFalse(checks.valid_travel_answer(response, "mixed_travel", 3))

    def test_real_escalation_keeps_all_checks_and_fails_batch(self):
        responses = [(200, {}, 0), (401, {}, 0), (201, {"user_key": "owner"}, 0),
                     (201, {"user_key": "other"}, 0), (201, {"trip_id": "trip"}, 0), (200, {}, 0), (404, {}, 0)]
        responses += [(200, {"answer": a, "status": "answered", "reason": r}, 1) for a,r in
                      [("경복궁 10:00~11:00", "decision_answer_fact"), ("점심 12:00~13:00", "decision_answer_fact"),
                       ("여행 안내", "decision_other")]]
        responses += [(200, {"answer": "해석 오류", "status": "escalated", "reason": "decision_failed",
                             "failure": "OllamaContentError"}, 1)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "state.json").write_text('{"current":"a"}')
            with patch.object(checks, "BASE", base), patch.object(checks.probe, "call", side_effect=responses):
                summary = checks.run("language_style", base / "output")
            self.assertEqual((summary["passed"], summary["total"], summary["attempted"]), (10, 11, 11))
            self.assertEqual(summary["validation_version"], checks.VALIDATION_VERSION)


if __name__ == "__main__":
    unittest.main()
