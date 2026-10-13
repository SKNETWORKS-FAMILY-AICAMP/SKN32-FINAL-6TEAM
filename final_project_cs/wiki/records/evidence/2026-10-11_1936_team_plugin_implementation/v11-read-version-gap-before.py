"""같은Case 잠금 뒤 일정판이 바뀌는 간격을 실제 읽기함수+리듀서로 재현한다. DB IO0."""
from pathlib import Path
import inspect,runpy,sys
import pytest
root=Path(__file__).resolve().parents[4]
candidate=root/"legacy/deployment_candidates/2026-10-12_015017_plugin_v11"
sys.path.insert(0,str(candidate))
ns=runpy.run_path(str(candidate/"tests/unit/travel/test_fact_read_recovery.py"))
saved=ns["saved"].__wrapped__()
source=inspect.getsource(ns["test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit"])
source=source[source.index("def "):]
source=source.replace("latest=lambda *a: (trip, [item]), versions=lambda *a: [{\"version\": 1}]", "latest=lambda *a: ({**trip, \"version\": 2}, [item]), versions=lambda *a: [{\"version\": 2}]")
assert "version\": 2" in source
exec(source,ns)
with pytest.MonkeyPatch.context() as mp:
 ns["test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit"](mp,saved,"classifying")
print("REPRODUCED: snapshot=1; handle trip=1; locked execution latest=2; actual retry_read completed answered instead of rejecting version drift")
print("Actual functions: retry_read, restore, _run_decision, classify_case, apply_event. SQL/commit are memory seams; DB/HTTP0.")
