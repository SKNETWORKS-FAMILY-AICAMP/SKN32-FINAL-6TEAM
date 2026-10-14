"""Current teaching material must execute travel policies and preserve prior progress."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "acop_dojo"))
from acop_dojo import boss, progress, scenarios

def test_current_boss_points_to_an_existing_travel_policy_test():
    s = scenarios.get(boss.BOSS_SCENARIO)
    path, function = s.nodeid.split("::")
    source = (ROOT / "final_project_cs" / path).read_text(encoding="utf-8")
    assert "def " + function + "(" in source
    assert "engine-serves-another-domain-v1" not in scenarios.SCENARIOS
    assert "MALL_POLICY" not in source

def test_previous_boss_progress_is_archived_idempotently():
    data = copy.deepcopy(progress.EMPTY)
    old = {"status": "passed", "defect": "INV-VERIFY-001"}
    data["stages"]["4"] = old.copy()
    data["abilities"]["안 배운 코드로 전이"] = {"evidence": "boss:INV-VERIFY-001:6/6", "state": "confirmed"}
    progress._park_commerce(data)
    assert "4" not in data["stages"]
    assert data["archived"]["stages"]["4"] == old
    assert "안 배운 코드로 전이" not in data["abilities"]
    once = copy.deepcopy(data)
    progress._park_commerce(data)
    assert data == once
    data["stages"]["4"] = {"policy_revision": boss.BOSS_SCENARIO, "status": "passed"}
    progress._park_commerce(data)
    assert data["stages"]["4"]["status"] == "passed"

def test_generated_workshop_cases_run_the_real_engine_with_success_and_failure():
    outcomes = set()
    for seed in range(10):
        _, arguments, price = boss._lesson_case(random.Random(seed))
        spec = {"policy": boss._LESSON_POLICY, "workshops": {"W-7": {"workshop_id": "W-7", "price_won": price}}, "arguments": arguments}
        run = subprocess.run([sys.executable, "-X", "utf8", "-c", boss._ENGINE_PROBE, json.dumps(spec)], cwd=ROOT / "final_project_cs", capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
        problems = json.loads(run.stdout.strip().splitlines()[-1])
        outcomes.add(bool(problems))
        if "permit_id" in arguments:
            assert any(field == "permit_id" for field, _ in problems)
        if arguments.get("workshop_id") == "W-99":
            assert any(field == "workshop_id" for field, _ in problems)
    assert outcomes == {True, False}
