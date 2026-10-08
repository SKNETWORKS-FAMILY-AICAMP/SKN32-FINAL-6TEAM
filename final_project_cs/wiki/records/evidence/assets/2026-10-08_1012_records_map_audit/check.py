"""Audit the five recent mobility reports without accessing any network service."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
REPORTS = [
    "2026-10-08_0245_이동_중단작업_재개와_200쌍_대조.md",
    "2026-10-08_0343_택시_예산여유_보정과_시각일치_검증.md",
    "2026-10-08_0503_이동_새100쌍_카카오웹_성능조사.md",
    "2026-10-08_0924_택시_공식요율과_네이버_구글_대조.md",
    "2026-10-08_0954_이동_네이버_구글_웹_12쌍_대조.md",
]
wiki = (REPO / "wiki/teams/mobility.md").read_text(encoding="utf-8-sig")
rows = []
for name in REPORTS:
    path = REPO / "wiki/records/reports" / name
    body = path.read_text(encoding="utf-8-sig")
    links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", body)
    local = [link for link in links if not re.match(r"(?:https?://|#|mailto:)", link)]
    broken = [link for link in local if not (path.parent / link.split("#")[0]).resolve().exists()]
    rows.append({"report": name, "exists": path.exists(), "wiki_link": name in wiki,
                 "timestamp_name": bool(re.match(r"\d{4}-\d{2}-\d{2}_\d{4}_", name)),
                 "local_links": len(local), "broken_links": broken,
                 "direct_evidence_md_links": [link for link in local if "/evidence/" in link and link.endswith(".md")],
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
raw_base = REPO.parent / "datasets/mobility/raw/kakao_golden"
raw = {name: (raw_base / name).exists() for name in [
    "compare_resume_200_v5.json", "taxi_time_aligned_v1.json",
    "taxi_budget_calibration_v1.json", "taxi_time_aligned_v2.json",
]}
sources = [
    "frontend/apps/web/src/features/map/config.ts",
    "frontend/apps/web/src/features/map/trip-map.tsx",
    "frontend/apps/web/src/features/map/providers/naver.ts",
    "frontend/apps/web/src/features/map/providers/osm.ts",
    "frontend/apps/web/src/features/map/providers/lines.ts",
    "frontend/apps/web/src/features/map/route-lines.ts",
    "frontend/apps/web/src/features/map/use-route-detail.ts",
    "app/domains/travel_ops/instances/mobility/route_shape.py",
]
result = {"observed_at_local": datetime.now().isoformat(timespec="seconds"),
          "scope": "five listed reports, their local links, four named raw files, eight source files; not a repository-wide audit",
          "reports": rows, "raw_files_exist": raw,
          "source_sha256": {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in sources}}
out = Path(__file__).with_name("result.json")
if out.exists():
    raise FileExistsError("Use a fresh output folder; audit evidence must not be overwritten.")
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"reports": len(rows), "wiki_links": sum(row["wiki_link"] for row in rows),
                  "timestamp_names": sum(row["timestamp_name"] for row in rows),
                  "local_links_checked": sum(row["local_links"] for row in rows),
                  "broken_links": sum(len(row["broken_links"]) for row in rows),
                  "raw_files_exist": raw, "source_files_hashed": len(sources)}, ensure_ascii=False))
