"""Update current records with backups; keep dated earlier evidence intact."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
DAY = ROOT / "program/research/daily_rag_slm"
RAW = ROOT / "program/scripts/plan_qa_bench/results/heartbeat_20261009_0754"
REPORT = "final_project_cs/wiki/records/reports/2026-10-09_0800_six-hour-gpu-arm-report.md"
GPU_REPORT = "final_project_cs/wiki/records/reports/2026-10-09_0810_gpu-saluki-cosine-completion-finch-refill.md"
NOW = datetime.now(ZoneInfo("Asia/Seoul"))
STAMP = NOW.strftime("%Y-%m-%d_%H%M%S") + "_six_hour_verified_results"
BACKUPS = []


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, text):
    old = path.read_text(encoding="utf-8")
    backup = path.parent / "_backup" / STAMP / path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    assert not backup.exists()
    shutil.copy2(path, backup)
    assert path.read_text(encoding="utf-8") == old
    path.write_text(text, encoding="utf-8")
    BACKUPS.append(str(backup.relative_to(ROOT)).replace("\\", "/"))


def write_json(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    verified = read_json(RAW / "parent_results_verification.json")
    assert verified["saved_rows"] == 27555 and verified["archive_files_verified"] == 72
    preservation_path = ROOT / "program/scripts/plan_qa_bench/results/gpu_backlog_20261008/saluki_preservation_resume_hb0754_20261009/resume_verification.json"
    preservation = read_json(preservation_path)["result"]
    assert preservation["saved"] == preservation["expected"] == 7898369152
    assert preservation["sha256"] == "4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb"
    preservation_ref = str(preservation_path.relative_to(ROOT)).replace("\\", "/")
    day = read_json(DAY / "2026-10-09.json")
    day["updated_at_kst"] = NOW.isoformat()
    day["measurement"].update(Saluki_project_model_evaluation_completed=True, Saluki_completed_rows=9425,
                              Saluki_failed_unparsed_missing_rows=0, Saluki_result_parent_recount_verified=True)
    day["Saluki_queue"].update(main_completed_rows=9425, main_completed_suites=5,
        state="All five fixed developer suites complete; E false-pick and subtype gates failed; no adoption or final ranking",
        weight_persistence="Existing GPU B disk copy whole-SHA verified; failed prior attempt and partial file preserved; no off-machine weight archive",
        runtime_verification="program/scripts/plan_qa_bench/results/heartbeat_20261009_0754/parent_results_verification.json")
    day["E_corpus_audit"].update(human_gold_review_completed=False, human_review_filled=0, human_review_expected=158,
        independent_holdout_created=False, independent_holdout_target=720,
        evidence="program/scripts/plan_qa_bench/results/heartbeat_20261009_0754/e_maturity_audit.json")
    day["six_hour_status"] = {"report": REPORT, "GPU_report": GPU_REPORT,
        "ARM_state": "program/research/daily_rag_slm/arm_serving_2026-10-09.json",
        "GPU_answers_collected": 27555, "GPU_hash_files_verified": 72,
        "ARM_cache_diagnostic_jobs": 4, "ARM_cache_unique_questions": 60, "ARM_cache_repeated_calls": 240,
        "ARM_speed_improvement_measured": False, "Saluki_E_aggregate_gates": {"passed": 3, "total": 4},
        "product_adoption": False, "full_service_deployment": False, "weight_preservation_evidence": preservation_ref}
    day["reports"] += [f for f in [REPORT, GPU_REPORT] if f not in day["reports"]]
    day["resume"] = [s for s in day["resume"] if "main jobs" not in s and "existing relay/receiver" not in s]
    day["resume"] += ["Saluki all five main suites complete: never duplicate them. Read verified B weight preservation record; original failed transfer preserved.",
        "Collect registered FINCH evaluations and compare to cosine on the same base, quantization and questions; do not claim one seed as final improvement.",
        "Observe existing ARM Q8 and four cache ABBA diagnostics without restart; collect errors, cache tokens, prefill, latency and resources.",
        "Prepare independent normal240/null480 travel holdout and E human review; AI/code checks do not equal human adjudication."]
    write_json(DAY / "2026-10-09.json", day)

    watch = read_json(DAY / "model_release_watchlist.json")
    candidate = next(c for c in watch["candidates"] if "Saluki" in c["repo_id"])
    candidate.update(status="five_original_suites_completed; E_false_pick_and_MX3_MX4_failed; not_adopted",
        original_benchmark_completed=True, main_completed_rows=9425, main_completed_suites=5,
        failed_unparsed_missing_rows=0, upper_tier=None, product_adoption=False,
        korean_travel_measurement_scope="Five frozen developer/regression suites, one run; not independent holdout or final ranking",
        runtime_report=GPU_REPORT, runtime_verification="program/scripts/plan_qa_bench/results/heartbeat_20261009_0754/parent_results_verification.json",
        required_next_action="Preserve complete original answers; no repeated main suites. Matched original comparison and human-reviewed independent holdout precede ranking/adoption. Outside current approximately8B SLM automatic training scope.")
    candidate["weight_storage"].update(permanent_copy_status="Existing GPU B root disk whole-SHA verified; prior failed transfer and partial file preserved; no off-machine durable weight copy",
        preservation_progress_evidence=preservation_ref)
    write_json(DAY / "model_release_watchlist.json", watch)

    path = DAY / "2026-10-09.md"
    text = path.read_text(encoding="utf-8")
    start = text.index("GPU 서버 A의 빈 대기열을 보충")
    end = text.index("\n\n", start)
    text = text[:start] + "Saluki 원본의 다섯 개발 시험을 완료·회수했으나 E의 요청 없음 오지목 기준에 실패해 채택하지 않는다. GPU 서버 A에 FINCH 추가 평가를 보충했고 Oracle ARM의 실제 지연을 확인할 캐시 대조를 등록했다. 독립 보류 검증과 오늘 오전10시 최신 논문 조사는 아직 완료되지 않았다." + text[end:]
    text = text.replace("| Saluki 여행 질의 본 비교 | 실행 중·부분 관측 | 184/9425 = 1.95% |", "| Saluki 여행 질의 본 비교 | 완료·채택 기준 실패 | 9425/9425 = 100% |")
    text = text.replace("## 아직 끝나지 않은 일", "## 01시 단계의 미완료 기록（역사）")
    text += "\n## 08시 정기 회수·보충\n\n[6시간 설명·현황](../../../" + REPORT + ") · [GPU 완료·집계·후속 시험](../../../" + GPU_REPORT + ") · [ARM 최신 관측](arm_serving_2026-10-09.json). 앞 절의 부분 관측과 미확인 보관 상태는 당시 기록이며 최신 수치로 쓰지 않는다. [이번 수정 직전 백업](_backup/" + STAMP + "/).\n"
    write(path, text)

    path = DAY / "index.md"
    text = path.read_text(encoding="utf-8").replace("GPU 대기열 보충·Saluki 다운로드와 시험 등록·E 구성 감사, 전체 논문 조사와 모델 최종 비교는 대기", "Saluki 개발 시험 완료·채택 기준 실패·GPU 보충·ARM 회수; 독립 검증과 일일 논문 조사는 대기")
    text = text.replace("[ARM 지속 서빙 상태](arm_serving_2026-10-08.json)", "[ARM 최신 서빙 상태](arm_serving_2026-10-09.json) · [초기 기록](arm_serving_2026-10-08.json)")
    text += "\n- [6시간 정기 설명·현황](../../../" + REPORT + "): 완료·실패·검증 대기를 구분한다. [기존 예약 변경 검증](six_hour_reporting_2026-10-09.json), 중복 예약은 만들지 않는다.\n"
    write(path, text)

    path = ROOT / "final_project_cs/wiki/operations/arm-serving-queue.md"
    text = path.read_text(encoding="utf-8").replace("daily_rag_slm/arm_serving_2026-10-08.json", "daily_rag_slm/arm_serving_2026-10-09.json")
    text += "\n`[실측 2026-10-09]` 첫 완료 답안 회수에서 CPU 목표 충족과 긴 응답 지연을 구분했다. 동일 원문·같은 모델의 캐시 교대 진단을 기존 실행기에 추가했고 개선 실측은 대기다. [회수·관측·등록 근거](../records/reports/2026-10-09_0800_six-hour-gpu-arm-report.md).\n"
    write(path, text)
    path = ROOT / "final_project_cs/wiki/operations/gpu-work-queue.md"
    text = path.read_text(encoding="utf-8").replace("daily_rag_slm/gpu_backlog_2026-10-08.json", "daily_rag_slm/gpu_backlog_2026-10-09.json")
    old = "매일 한국 시간 오전 10시 연구 확인과 10분마다 대기열 확인은 같은 실행 기록을 공유한다. 의미 있는 완료·실패·비교 결과·필요한 사용자 조치가 있을 때만 보고한다. 기존 자동 확인 종료 조건보다 지속적인 일감 보충 지시가 우선한다."
    new = "매일 한국 시간 오전 10시 연구와 6시간마다 설명·현황을 보고하는 기존 예약은 같은 실행 기록을 공유한다. 사용자가 요청한 6시간 회차에는 변화가 없어도 관측 시각·완료·실패·검증 대기와 다음 작업을 보고한다. 각 기계의 지속 실행기는 회차 사이에도 등록한 작업을 순서대로 처리한다. 지속적인 일감 보충 지시를 유지한다. [예약 변경 검증](../../../program/research/daily_rag_slm/six_hour_reporting_2026-10-09.json)."
    assert old in text
    text = text.replace(old, new)
    text += "\n`[실측 2026-10-09]` 완료 원본·학습판 답안을 회수하고 빈 GPU 서버 A 대기열에 FINCH 누락 평가를 보충해 실제 계산을 재확인했다. [회수·집계·등록 근거](../records/reports/2026-10-09_0810_gpu-saluki-cosine-completion-finch-refill.md).\n"
    write(path, text)
    path = ROOT / "final_project_cs/wiki/quality/slm-model-evaluation.md"
    text = path.read_text(encoding="utf-8") + "\n`[실측 2026-10-09]` Saluki 원본의 고정 개발 시험은 완료했으나 E 요청 없음 오지목과 지정 부류 기준에 실패했다. 최종 순위·독립 검증·제품 채택은 확정하지 않는다. [원본·집계·실행 조건](../records/reports/2026-10-09_0810_gpu-saluki-cosine-completion-finch-refill.md).\n"
    write(path, text)
    path = ROOT / "final_project_cs/wiki/log.md"
    text = path.read_text(encoding="utf-8")
    marker = "# 문서 변경 이력 (cs)\n"
    entry = "\n## 2026-10-09 — 6시간 GPU·ARM 회수와 후속 진단\n\n완료 원본 비교의 채택 기준 실패를 보관하고 FINCH 누락 평가를 GPU 대기열에 보충했다. Oracle ARM의 첫 완료 답안을 회수하고 실제 CPU 목표와 지연을 구분해 캐시 교대 진단을 예약했다. [정기 현황·원본·백업](records/reports/2026-10-09_0800_six-hour-gpu-arm-report.md). 독립 검증과 전체 서비스 배포는 대기다.\n"
    assert marker in text
    write(path, text.replace(marker, marker + entry, 1))
    (RAW / "document_backups.json").write_text(json.dumps({"changed_artifact_backups": BACKUPS, "report": REPORT,
        "created_at_kst": NOW.isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifacts_updated_with_backups": len(BACKUPS), "backup_stamp": STAMP}, ensure_ascii=False))


if __name__ == "__main__":
    main()
