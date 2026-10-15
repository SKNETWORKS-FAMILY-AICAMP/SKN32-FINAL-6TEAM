"""Link this dated work into canonical documentation, backing up before edits."""
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKUP = "2026-10-09_1152_selection-answer-integration"
REPORT = "2026-10-09_1150_selection-answer-plan-and-training-review.md"


def replace(path, update):
    p = ROOT / path
    old = p.read_text(encoding="utf-8-sig")
    new = update(old)
    if new == old:
        return
    dest = p.parent / "_backup" / BACKUP / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert not dest.exists(), f"Backup already exists: {dest}"
    shutil.copy2(p, dest)
    p.write_text(new, encoding="utf-8")


def append(path, content):
    replace(path, lambda old: old if content in old else old.rstrip() + "\n\n" + content + "\n")


def main():
    replace("datasets/README.md", lambda old: old.replace("| 경로 | 내용 | 출처 | 라이선스 | 수집일 |\n|---|---|---|---|---|", "| 경로 | 내용 | 출처 | 라이선스 | 수집일 |\n|---|---|---|---|---|\n| [travel/selection_answer_bench/2026-10-09_pilot_v1/](travel/selection_answer_bench/2026-10-09_pilot_v1/REPORT.md) | 대상 선택·근거·답변의 가상 개발 예시24개·3일정군, 사람 검수/모델 실행 대기; 독립 보류 아님 | 자체 여행 예시·가상 사실 | 외부 고객/소개글/사진 미사용, 로컬 개발 진단 | 2026-10-09 |") if "selection_answer_bench" not in old else old)
    append("program/research/daily_rag_slm/index.md", "- [새 대상 선택·근거·답변 계획](selection_answer_plan_2026-10-09_v1.md) · [검토 상태](selection_answer_review_2026-10-09_v1.json): 최근 연구8개와 사람 검수 전 개발 예시를 연결합니다.\n- [Saluki 전담 학습 계획](saluki_finetune_plan_2026-10-09.md) · [준비 상태](saluki_finetune_2026-10-09.json): 사용자 승인 있음, 동일 모델 학습 표현·CUDA·공간 조건 대기입니다.\n- [새 통합 평가·학습 비교 리포트](../../../final_project_cs/wiki/records/reports/" + REPORT + "): Jev 관련5학습판 재계수와 기존 GPU 후속 작업도 연결합니다.")
    append("program/research/daily_rag_slm/2026-10-09.md", "## 새 통합 평가와 Saluki 추가 학습 준비\n\n[연구·계획·개발 예시·학습 재계수](../../../final_project_cs/wiki/records/reports/" + REPORT + ")를 완료했습니다. 예시 구조 검사는 완료했으나 사람 검수·검색/답변 실측·독립 보류 자료는 대기입니다. Saluki는 사용자 승인에 따라 전담 준비를 완료했고 동일 모델 학습 경로·CUDA·공간 조건을 재확인한 뒤 재개합니다. 기존 GPU 실행과 후속 보충은 [별도 회수 근거](../../../final_project_cs/wiki/records/reports/2026-10-09_1150_gpu-refill-valen-d2-failure-and-winnow-role.md)에 있습니다.\n\n[이번 문서·상태 수정 직전 백업](_backup/" + BACKUP + "/).")
    def day_update(old):
        x = json.loads(old)
        x["selection_answer_extension"] = dict(plan="program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v1.md", status="program/research/daily_rag_slm/selection_answer_review_2026-10-09_v1.json", pilot_schema="24/24", human_review="0/24", model_measurement="0/24", final_holdout=False, report="final_project_cs/wiki/records/reports/"+REPORT)
        x["Saluki_finetuning_preparation"] = dict(state="program/research/daily_rag_slm/saluki_finetune_2026-10-09.json", authorized=True, training_started=False, resume="Exact Saluki trainable representation, CUDA backward and existing storage/memory gates, then smoke and new adapter")
        x["updated_at_kst"] = datetime.now().astimezone().isoformat()
        return json.dumps(x, ensure_ascii=False, indent=2) + "\n"
    replace("program/research/daily_rag_slm/2026-10-09.json", day_update)
    def watch_update(old):
        x = json.loads(old)
        candidates = [r for r in x["candidates"] if r["repo_id"] == "ConwayResearch/Underdog-Saluki-27B-1.0"]
        assert len(candidates) == 1
        candidates[0].update(finetuning_authorized_by_user=True, finetuning_preparation_state="program/research/daily_rag_slm/saluki_finetune_2026-10-09.json", finetuning_status="preparation_blocked_not_started", required_next_action="Preserve completed original comparisons. Explicit user authorization allows separate Saluki27B training when identical trainable weights, CUDA backward, storage and reviewed-data gates pass. Do not substitute another model or block ready GPU jobs.")
        return json.dumps(x, ensure_ascii=False, indent=2) + "\n"
    replace("program/research/daily_rag_slm/model_release_watchlist.json", watch_update)
    append("final_project_cs/wiki/quality/slm-model-evaluation.md", "`[設計・準備 2026-10-09]`".replace("設計・準備", "설계·준비") + " 기존 D/E를 유지한 새 [대상 선택·근거·답변 계약](selection-grounded-answer-evaluation.md)을 초안으로 연결했습니다. Saluki의 별도 학습 승인은 반영됐으나 정확한 동일 모델 학습 경로·CUDA·공간 조건이 남았습니다. [검토·예시·학습 비교 근거](../records/reports/" + REPORT + ").")
    append("wiki/research/rag-slm-improvements.md", "`[검토 2026-10-09]` 최근 평가 연구를 선택·검색·답변 분리 계약과 가상 개발 예시에 연결했고 독립 검증·제품 적용은 대기입니다. Saluki 전담 학습 준비와 Jev 관련 모델 비교도 [새 리포트](../../final_project_cs/wiki/records/reports/" + REPORT + ")에서 확인합니다.")
    append("final_project_cs/wiki/operations/gpu-work-queue.md", "`[준비 2026-10-09]` Saluki27B는 별도 학습 승인 후 동일 모델의 학습 표현·CUDA·공간 조건 대기이며 실행 가능한 기존 일감을 막지 않습니다. [준비 근거](../records/reports/2026-10-09_1200_saluki-finetune-preflight.md). 기존 worker의 완료 회수·누락 역할 보충과 실패 보존은 [후속 운영 근거](../records/reports/2026-10-09_1150_gpu-refill-valen-d2-failure-and-winnow-role.md)에 연결합니다.")
    append("final_project_cs/wiki/log.md", "## 2026-10-09 — 대상 선택·근거·답변 평가와 학습 준비\n\n새 평가 계약과 사람 검수 전 개발 예시를 연결하고 Jev 관련 학습판을 재계수했습니다. [통합 리포트](records/reports/"+REPORT+"). Saluki는 같은 모델 학습 경로·CUDA·공간 조건 대기이며 [전담 준비](records/reports/2026-10-09_1200_saluki-finetune-preflight.md)를 보존했습니다. 기존 GPU 작업은 유지하고 [누락 시험 보충·로드 전 실패 수정](records/reports/2026-10-09_1150_gpu-refill-valen-d2-failure-and-winnow-role.md)을 기록했습니다.")
    replace("program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md", lambda old: old.replace("997/1,033 = 96.51%", "997/1,033 = 96.52%"))
    print("문서·상태 연결 완료; 기존 파일은 수정 직전 각 폴더에 백업했습니다.")


if __name__ == "__main__":
    main()
