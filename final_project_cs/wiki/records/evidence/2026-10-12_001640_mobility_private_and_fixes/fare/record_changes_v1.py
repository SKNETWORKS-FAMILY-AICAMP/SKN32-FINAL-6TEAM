import difflib
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
backup = root / (here / "backup-path-v1.txt").read_text(encoding="utf-8-sig").strip()
engine = root / "final_project_cs/app/domains/travel_ops/instances/mobility/engine"
diffs = []
for name in ("car.py", "plan.py"):
    before = (backup / name).read_text(encoding="utf-8").splitlines(keepends=True)
    after = (engine / name).read_text(encoding="utf-8").splitlines(keepends=True)
    diffs.extend(difflib.unified_diff(before, after, fromfile=f"before/{name}", tofile=f"after/{name}"))
(here / "changes-from-backup-v1.diff").write_text("".join(diffs), encoding="utf-8")
report = root / "final_project_cs/wiki/records/reports/2026-10-11_2335_택시예산_구성금액과옵션료_안내검증.md"
paths = [engine / "car.py", engine / "plan.py", report,
         root / "final_project_cs/tests/unit/travel/mobility/test_taxi_cost_components_v1.py",
         engine / "rules/rules_v0.3.json", backup / "car.py", backup / "plan.py"]
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(here / "final-sha256-v1.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"hashed_files": len(paths), "diff_lines": len(diffs)}, ensure_ascii=False))
