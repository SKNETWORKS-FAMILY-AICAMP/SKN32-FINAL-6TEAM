"""Recheck saved web controls and statistics; never request routes or write raw data."""
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scripts.mobility.summarise_fresh_web_experiment import analyse
from scripts.mobility.summarise_multi_provider_web import parse

RAW = ROOT.parent / "datasets/mobility/raw/kakao_golden"
ASSETS = ROOT / "wiki/records/reports/assets"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load(name):
    return {r["id"]: r for r in read(RAW / name)["rows"]}


fresh = read(ASSETS / "2026-10-08_mobility_fresh_100/summary.json")
rebuilt, joined = analyse(read(RAW / "fresh_web_100_v1.json"),
                          load("fresh_ours_transit_100_v1.json"),
                          load("fresh_ours_taxi_100_v1.json"),
                          load("fresh_ours_bus_100_v1.json"))
assert all(fresh[k] == v for k, v in rebuilt.items())
assert joined == read(RAW / "fresh_comparison_rows_v1.json")
fresh_hashes = fresh["input_sha256"]
assert all(hashlib.sha256((RAW / n).read_bytes()).hexdigest() == h for n, h in fresh_hashes.items())

folder = RAW / "multi_provider_2026-10-08"
multi = read(ASSETS / "2026-10-08_mobility_multi_provider_12/summary.json")
proof = read(ASSETS / "2026-10-08_mobility_multi_provider_12/evidence.json")
hashes = proof["raw_file_sha256"]
assert all(hashlib.sha256((folder / n).read_bytes()).hexdigest() == h for n, h in hashes.items())
records = read(folder / "comparison-v1.json")
original = read(folder / "readings-v1.json")
corrected = read(folder / "google-coordinate-readings-v2.json")
active = [r for r in original if r["provider"] != "google"] + corrected
indexed = {r["id"]: r for r in records}
for observation in active:
    expected = indexed[observation["id"]][observation["provider"]]
    if observation["provider"] == "naver":
        expected = expected[observation["mode"]]
    assert parse(observation) == expected

checked = []


def check(label, ours, reference, expected, tolerance=5):
    differences = [a-b for a, b in zip(ours, reference, strict=True)]
    percents = [(a/b-1)*100 for a, b in zip(ours, reference, strict=True)]
    values = {"n": len(differences), "median": statistics.median(differences),
              "mae": statistics.mean(abs(x) for x in differences),
              "within": sum(abs(x) <= tolerance for x in differences),
              "percent_median": statistics.median(percents)}
    for k in ("n", "median", "mae", "within"):
        assert math.isclose(values[k], expected["absolute"][k], abs_tol=1e-9), (label, k)
    assert math.isclose(values["percent_median"], expected["percent"]["median"], abs_tol=1e-9)
    checked.append({"metric": label, **values})


for provider in ("naver", "google"):
    reference = [r["naver"]["transit"]["min"] if provider == "naver" else r["google"]["min"] for r in records]
    for mode in ("with_wait", "without_wait"):
        ours = [r[provider+"_planned"]["eta_min"] - (r[provider+"_planned"]["wait_min"] if mode == "without_wait" else 0) for r in records]
        check(provider+"_"+mode, ours, reference, multi["transit"][provider][mode])
check("naver_taxi_meter", [r["ours"]["taxi"]["meter_won"]+r["ours"]["taxi"]["toll_won"] for r in records],
      [r["naver"]["car"]["fare_won"] for r in records], multi["taxi_meter"], 1000)
check("naver_taxi_budget", [r["ours"]["taxi"]["fare_won"] for r in records],
      [r["naver"]["car"]["fare_won"] for r in records], multi["taxi_budget"], 1000)
covered = sum(r["ours"]["taxi"]["fare_won"] >= r["naver"]["car"]["fare_won"] for r in records)
assert covered == multi["taxi_budget_coverage"]
rules = ROOT / "app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json"
rules_hash = hashlib.sha256(rules.read_bytes()).hexdigest()
result = {"fresh_groups_reproduced": len(rebuilt), "fresh_rows_reproduced": len(joined),
          "fresh_input_hashes_verified": len(fresh_hashes), "multi_input_hashes_verified": len(hashes),
          "multi_web_values_reparsed": len(active), "multi_metrics_independently_verified": checked,
          "naver_taxi_budget_coverage": covered, "current_rules_match_experiment": rules_hash == multi["rules_sha256"],
          "scope": "saved web observations and saved local engine results; not new driving, deployed API or live rerouting tests"}
output = Path(__file__).with_name("readiness-check.json")
if output.exists():
    raise FileExistsError("Use a fresh evidence folder instead of overwriting existing output.")
output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
