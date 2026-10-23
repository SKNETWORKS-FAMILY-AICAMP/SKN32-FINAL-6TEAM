"""Linux 서비스 의존성 없이 실제 refill 함수를 추출해 대기 시간 불변식을 검사한다."""
import ast
import copy
import types
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("serving_queue.py")
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"estimate", "refill"}]
ns = {"MIN_ESTIMATE": 30, "HORIZON": 21600, "DEFAULT_SECONDS": 480, "MAX_PENDING": 720,
      "probe": types.SimpleNamespace(PROFILES=dict(context_cache=(), mixed_travel=(), language_style=()), PLANNED=tuple(range(11)))}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), ns)
refill = ns["refill"]


class ReadyHorizonTests(unittest.TestCase):
    def state(self):
        return {"jobs": [{"id": str(i), "profile": "context_cache" if i % 2 else "mixed_travel", "status": "pending"} for i in range(45)],
                "failed_profiles": {"context_cache": "current", "mixed_travel": "current"}, "estimates": {}}

    def test_blocked_work_does_not_fill_ready_horizon(self):
        state = self.state()
        before = copy.deepcopy(state["jobs"])
        self.assertEqual(refill(state, 100000, "current"), 45)
        self.assertEqual(state["jobs"][:45], before)
        self.assertTrue(all(j["profile"] == "language_style" for j in state["jobs"][45:]))
        self.assertEqual(state["estimated_pending_seconds"], 21600)
        self.assertEqual(state["blocked_pending_jobs"], 45)

    def test_second_refill_is_idempotent(self):
        state = self.state()
        refill(state, 100000, "current")
        self.assertEqual(refill(state, 100001, "current"), 0)

    def test_all_profiles_blocked_does_not_repeat_failures(self):
        state = self.state()
        state["failed_profiles"]["language_style"] = "current"
        self.assertEqual(refill(state, 100000, "current"), 0)
        self.assertEqual(state["estimated_pending_seconds"], 0)

    def test_new_revision_releases_existing_pending(self):
        state = self.state()
        self.assertEqual(refill(state, 100000, "new"), 0)
        self.assertEqual(state["blocked_pending_jobs"], 0)

    def test_running_elapsed_is_subtracted(self):
        state = self.state()
        state["jobs"] = [{"profile": "language_style", "status": "running", "started": 99900}]
        refill(state, 100000, "current")
        self.assertEqual(state["estimated_pending_seconds"], 21980)
        self.assertEqual(state["ready_pending_jobs"], 45)

    def test_missing_revision_does_not_enqueue(self):
        state = self.state()
        self.assertEqual(refill(state, 100000, ""), 0)


if __name__ == "__main__":
    unittest.main()
