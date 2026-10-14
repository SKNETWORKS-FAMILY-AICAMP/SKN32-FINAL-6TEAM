"""후속 대화·필수 관문의 JUnit 결과와 사후 소스 해시를 기록한다."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree


evidence = Path(__file__).resolve().parent
root = evidence.parents[3]
runs = {}
for name in ("conversation-final-joint-v1", "conversation-final-joint-v2", "required-gates-v6"):
    xml = evidence / f"{name}.xml"
    suites = ElementTree.parse(xml)
    cases = suites.findall(".//testcase")
    counts = {"collected_and_executed": len(cases), "failed": 0, "errors": 0, "skipped": 0, "passed": 0}
    for case in cases:
        outcome = "failed" if case.find("failure") is not None else "errors" if case.find("error") is not None else \
                  "skipped" if case.find("skipped") is not None else "passed"
        counts[outcome] += 1
    runs[name] = {**counts, "junit_sha256": hashlib.sha256(xml.read_bytes()).hexdigest(),
                  "log_sha256": hashlib.sha256((evidence / f"{name}.log").read_bytes()).hexdigest()}
paths = (
    "app/application/case_intake.py", "app/application/controller.py",
    "app/domains/travel_ops/components/conversation/case_dispatch.py",
    "app/domains/travel_ops/components/conversation/trip_messages.py",
    "app/domains/travel_ops/components/watch/trip_watch_cases.py",
    "tests/e2e/test_web_conversation_isolation.py", "tests/e2e/test_web_conversation_resume.py",
)
result = {
    "created_at": datetime.now().astimezone().isoformat(),
    "scope": "JUnit execution counts; source hashes captured AFTER runs only, not a before/after freeze proof",
    "runs": runs,
    "post_run_source_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths},
}
destination = evidence / "parent-final-current-receipt-v1.json"
if destination.exists():
    raise FileExistsError("preserve previous evidence; use a new version")
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(runs, indent=2))
