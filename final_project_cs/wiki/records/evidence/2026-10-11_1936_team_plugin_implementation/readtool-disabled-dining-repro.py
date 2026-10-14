"""Synthetic in-memory SQL cursor; never connects to a database."""
import json
from datetime import UTC, datetime
from uuid import uuid4
from app.core.contracts import ContextPack
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.core.team_availability import TeamUnavailable
from app.tools.read_tools import ReadToolbox

class Cursor:
    def __init__(self, calls): self.calls = calls
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, *args): self.calls.append("sql_executed")
    def fetchone(self): return (False,)

class Connection:
    def __init__(self, calls): self.calls = calls
    def __enter__(self): self.calls.append("connection_opened"); return self
    def __exit__(self, *args): return False
    def cursor(self): return Cursor(self.calls)

registry = TeamRegistry()
registry.declare_unavailable("dining", "disabled")
context = ContextPack(pack_id=uuid4(), case_id=uuid4(), tenant_id="synthetic-review",
    team_id="activity", knowledge_scope=[], estimated_input_tokens=0,
    current_state={"customer_id": str(uuid4())})
calls = []
toolbox = ReadToolbox(lambda: Connection(calls))
results = []
with bind_services(BindingTable({}, registry, "disabled-dining-review")):
    for name, args in [("read.dining_state", {"place_id": "synthetic-place", "at": datetime(2026,10,12,3,tzinfo=UTC)}),
                       ("read.dining_states", {"slots": [{"place_id": "synthetic-place", "at": datetime(2026,10,12,3,tzinfo=UTC)}]})]:
        before = len(calls)
        try:
            value = toolbox.call(name, context, args, [name], set())
            results.append({"tool":name,"rejected_unavailable":False,"returned":value,"connection_sql_events":len(calls)-before})
        except TeamUnavailable as exc:
            results.append({"tool":name,"rejected_unavailable":True,"reason":exc.reason,"connection_sql_events":len(calls)-before})
print(json.dumps({"registry":registry.availability(),"results":results},default=str,indent=2))
