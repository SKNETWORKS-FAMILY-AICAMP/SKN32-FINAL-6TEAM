"""완료된 전체 E2E 로그·JUnit·시작 해시를 집계한다. 실행 중에는 결과를 만들지 않는다."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


folder = Path(__file__).resolve().parent
target = folder / "e2e-full-v4-classification.json"
assert not target.exists(), "기존 집계는 덮지 않습니다"
log = (folder / "e2e-full-v4.log").read_text(encoding="utf-8", errors="replace")
collected = int(re.search(r"collected (\d+) items", log)[1])
root = ET.parse(folder / "e2e-full-v4.xml").getroot()
cases = list(root.iter("testcase"))
failures, skips, ids = [], [], []
for case in cases:
    classname = case.attrib["classname"]
    parts = classname.split(".")
    for n in range(len(parts), 0, -1):
        module = Path(*parts[:n]).with_suffix(".py")
        if module.exists():
            node = "::".join([module.as_posix(), *parts[n:], case.attrib["name"]])
            break
    else:
        raise AssertionError(f"시험 모듈 경로를 확인하지 못했습니다: {classname}")
    ids.append(node)
    for failed in case.findall("failure") + case.findall("error"):
        failures.append({"test": node, "reason": failed.attrib.get("message", "")})
    for skipped in case.findall("skipped"):
        skips.append({"test": node, "reason": skipped.attrib.get("message", "")})
start = json.loads((folder / "e2e-full-v4-source-start.json").read_text(encoding="utf-8"))
changed = [row["file"] for row in start["files"]
           if not Path(row["file"]).exists()
           or hashlib.sha256(Path(row["file"]).read_bytes()).hexdigest() != row["sha256"]]
prior = set(re.findall(r"^tests/e2e/.*::.*$", (folder / "e2e-full-v2-collection.log").read_text(
    encoding="utf-8", errors="replace"), flags=re.MULTILINE))
prior = {s.rstrip("\r") for s in prior}
result = {
    "collected": collected, "executed": len(cases),
    "passed": len(cases) - len(failures) - len(skips),
    "failed": len(failures), "skipped": len(skips), "unexecuted": collected - len(cases),
    "failures": failures, "skips": skips,
    "skip_reason_counts": dict(Counter(row["reason"] for row in skips)),
    "source_files_at_start": len(start["files"]), "source_changed_since_start": changed,
    "added_nodeids_since_v2_collection": sorted(set(ids) - prior),
    "removed_nodeids_since_v2_collection": sorted(prior - set(ids)),
    "note": "별도 격리 DB 재실행은 이 전체 실행 결과에 합산하지 않습니다.",
}
assert len(cases) == collected, "끝까지 실행하지 못한 구간이 있습니다"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: result[k] for k in ("collected", "executed", "passed", "failed", "skipped", "unexecuted",
                                        "source_files_at_start", "source_changed_since_start")}))
