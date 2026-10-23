"""Save a new dated ARM observation and register its diagnostic dataset."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
DAY = ROOT / "program/research/daily_rag_slm"
EVIDENCE = ROOT / "program/scripts/plan_qa_bench/results/heartbeat_20261009_0754"
REPORT = "final_project_cs/wiki/records/reports/2026-10-09_0800_six-hour-gpu-arm-report.md"


def main():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    obs = json.loads((EVIDENCE / "arm_observation_verified.json").read_text(encoding="utf-8"))
    counts = json.loads((EVIDENCE / "arm_counts_verified.json").read_text(encoding="utf-8"))
    registration = json.loads((EVIDENCE / "arm_cache_registered.json").read_text(encoding="utf-8"))
    state = {
        "date": "2026-10-09", "recorded_at_kst": now.isoformat(),
        "machine": "Oracle ARM", "authorization": "existing machine and models; continuous travel validation",
        "service": "tripilot-arm-serving.service", "active": True, "enabled": True,
        "worker_pid": 171515, "worker_restarted": False, "lock_held": True,
        "restart_count_observed": 0, "real_inference_verified": True,
        "cpu_cores_actual": 2, "host_memory_bytes_actual": 12503744512,
        "workload_memory_max_bytes": 10737418240, "workload_cpu_limit_cores": 1.8,
        "cpu_target_pct_of_two_cores": 20,
        "resource_observed_at_utc": obs["observed_at"],
        "resource_measurement": obs["resource_summary"], "free_bytes": obs["free_bytes"],
        "cpu_target_24h_proven": False,
        "current_job_at_observation": obs["active"]["job_id"],
        "saved_at_observation": obs["active"]["saved"],
        "expected_at_observation": obs["active"]["expected"],
        "completed_jobs": 1, "running_jobs": 1,
        "registered_jobs_after_refill": registration["manifest_jobs"],
        "pending_jobs_after_refill": registration["pending_jobs"],
        "registered_calls_after_refill": 7494,
        "completed_Q4_D3": counts,
        "Q4_completed_at_utc": obs["state"]["jobs"]["e4bt_q4_d3"]["finished"],
        "Q4_collection_is_new_not_completion_since_last_report": True,
        "completed_archive_hash_files": {"verified": 4, "expected": 4},
        "cache_diagnostic": {
            "registration": registration, "normal_unique": 20, "null_unique": 40,
            "cache_flags_in_order": [True, False, False, True],
            "completed_at_registration": 0, "planned_calls": 240,
            "hypothesis": "Long prefill dominates; grouping exact itinerary prefixes may improve prompt-cache reuse",
            "measured_improvement": False, "independent_holdout": False,
            "pass_rule": "Matched cache-on non-first-within-context median >=30% faster, no new errors or loss of correct choices; retain all60/cold5 results",
            "repeated_calls_do_not_expand_unique_accuracy_denominator": True,
        },
        "source_observation": str((EVIDENCE / "arm_observation_verified.json").relative_to(ROOT)).replace("\\", "/"),
        "raw_results": str(EVIDENCE.relative_to(ROOT)).replace("\\", "/"),
        "report": REPORT,
        "model_recipe_verified": False, "product_adoption": False,
        "cs_project_full_deployment_verified": False,
        "next_actions": [
            "Preserve active Q8 run; collect its completed answers and attempt/version/hash evidence",
            "Observe four registered ABBA diagnostics with existing worker; compare matched questions, cache tokens, prefill, latency, errors and CPU",
            "Keep remaining meaningful profiles and soak runs; do not combine repeated accuracy samples",
        ],
    }
    target = DAY / "arm_serving_2026-10-09.json"
    assert not target.exists(), "Use a new version or back up before overwriting"
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dataset_index = ROOT / "datasets/README.md"
    row = "| [travel/arm_cache_diagnostic_20261009/](travel/arm_cache_diagnostic_20261009/) | ARM 캐시 진단: 기존 D3에서 정상20·요청없음40의 원문60개를 일정 문맥별로 묶어 ABBA4회·240호출 예약. 독립 정확도 표본은60개이며 새 보류 자료가 아님 | 기존 자체 여행 가상 D3·원문 해시 보존 | 자체 생성 로컬 진단 자료, 외부 고객 자료 미사용 | 2026-10-09 |\n"
    text = dataset_index.read_text(encoding="utf-8")
    assert row not in text
    stamp = now.strftime("%Y-%m-%d_%H%M%S") + "_arm_cache_diagnostic_registration"
    backup = dataset_index.parent / "_backup" / stamp
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(dataset_index, backup / dataset_index.name)
    marker = "|---|---|---|---|---|\n"
    assert marker in text
    dataset_index.write_text(text.replace(marker, marker + row, 1), encoding="utf-8")
    (EVIDENCE / "arm_document_registration.json").write_text(json.dumps({
        "new_state": str(target.relative_to(ROOT)).replace("\\", "/"),
        "dataset_index_backup": str(backup.relative_to(ROOT)).replace("\\", "/"),
        "source_observation_utc": obs["observed_at"],
        "registered_at_utc": registration["registered_at_utc"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"new_state_saved": True, "dataset_registered": True, "backup": str(backup.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
