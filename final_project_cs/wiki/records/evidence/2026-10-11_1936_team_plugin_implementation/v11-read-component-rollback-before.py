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
source=source.replace('case = dict(case_id=uuid4()', 'item.place = {"name": "경복궁"}\n    decision.fact = snapshot["fact"] = state["decision"]["fact"] = "detail"\n    case = dict(case_id=uuid4()')
source=source.replace('events = []', 'initial = deepcopy(case)\n    events = []')
source=source.replace('conn = Conn()', 'conn = Conn()\n    def component_rollback(connection, *args):\n        assert connection is conn\n        case.clear()\n        case.update(deepcopy(initial))\n        connection.rollback()\n        return ""\n    monkeypatch.setattr(trip_messages, "_place_extras", component_rollback)')
exec(source,ns)
from app.core.contracts import InvalidTransition
with pytest.MonkeyPatch.context() as mp:
 try:
  ns["test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit"](mp,saved,"classifying")
 except InvalidTransition as exc:
  print("REPRODUCED: detail enrichment rollback reset pending read transitions; completing from classifying raised",type(exc).__name__)
 else:
  raise AssertionError("rollback gap did not reproduce")
print("Actual functions: retry_read, _run_decision, classify_case, apply_event; _place_extras rollback is a component seam, not a real DB schema-failure test.")
