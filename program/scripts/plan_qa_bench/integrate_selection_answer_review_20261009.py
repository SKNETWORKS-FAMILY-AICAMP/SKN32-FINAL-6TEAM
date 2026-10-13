"""Preserve v1/v2 examples; register independently reviewed v3 development data."""
import json
from datetime import datetime
import integrate_selection_answer_20261009 as old

ROOT = old.ROOT
old.BACKUP = "2026-10-09_1159_independent-pilot-review"
RECORD = "2026-10-09_1158_pilot-independent-review-corrections.md"


def main():
    original = ROOT / "program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v1.md"
    updated = original.read_text(encoding="utf-8").replace("2026-10-09_pilot_v1", "2026-10-09_pilot_v3").replace("가상 사실과3개 일정군의8유형×3문장", "가상 사실과고유 일정1개의8유형×3문장(명목 범위ID3개이며 독립 일정3개가 아님)")
    updated += "\n\n## 독립 검토 후 보완\n\n초기 예시의 ID 정답 노출과 일정군 계수, 근거 상태 누락을 모델 전송 전에 바로잡았습니다. 현재 예시는v3이며 독립 일정 검증·대체/부재 근거·검색/답변 실행은 여전히 대기입니다. [수정·원본 보존 근거](../../../final_project_cs/wiki/records/reports/" + RECORD + ").\n"
    new_plan = original.with_name("selection_answer_plan_2026-10-09_v2.md")
    with new_plan.open("x", encoding="utf-8") as stream:
        stream.write(updated)
    state_path = ROOT / "program/research/daily_rag_slm/selection_answer_review_2026-10-09_v1.json"
    x = json.loads(state_path.read_text(encoding="utf-8"))
    x.update(plan="program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v2.md", dataset="datasets/travel/selection_answer_bench/2026-10-09_pilot_v3", pilot_nominal_family_ids=3, pilot_unique_itinerary_contents=1, pilot_independence_verified=False, evidence_status_counts={"sufficient":15, "not_required":9}, independent_agent_review=True, report="final_project_cs/wiki/records/reports/"+RECORD)
    x.pop("pilot_independent_families", None)
    x["resume"].append("Implement backup/unavailable evidence cases; current pilot does not implement full contract")
    x["limitations_corrected"] = ["Initial v1 ID contained gold scope; no model calls occurred", "Three nominal IDs were one itinerary; no independence claim", "Gold evidence_status and full citation IDs now present"]
    with state_path.with_name("selection_answer_review_2026-10-09_v2.json").open("x", encoding="utf-8") as stream:
        json.dump(x, stream, ensure_ascii=False, indent=2)
    old.replace("final_project_cs/wiki/quality/selection-grounded-answer-evaluation.md", lambda s: s.replace("selection_answer_plan_2026-10-09_v1.md", "selection_answer_plan_2026-10-09_v2.md").replace("2026-10-09_pilot_v1", "2026-10-09_pilot_v3").replace("十分", "충분").replace("충분·대체 근거 사용·필수 근거 조회 실패", "충분·대체 근거 사용·필수 근거 조회 실패·근거 불필요") + "\n평가의 request_scope는 진단용 정답 라벨이며 제품의 기존 intent·case_type을 교체하지 않습니다. 개발 예시의 초기 ID·일정군 표시를 모델 실행 전에 수정했습니다. [독립 검토·현재 판](../records/reports/"+RECORD+").\n")
    old.replace("program/research/daily_rag_slm/index.md", lambda s:s.replace("selection_answer_plan_2026-10-09_v1.md", "selection_answer_plan_2026-10-09_v2.md").replace("selection_answer_review_2026-10-09_v1.json", "selection_answer_review_2026-10-09_v2.json") + "\n- [예시 독립 검토와 현재v3](../../../final_project_cs/wiki/records/reports/"+RECORD+"): ID 정답 표시를 제거했으며 고유 일정은1개, 사람/모델 검증은 대기입니다.\n")
    old.replace("datasets/README.md", lambda s: s.replace("2026-10-09_pilot_v1/", "2026-10-09_pilot_v3/").replace("가상 개발 예시24개·3일정군", "가상 개발 예시24개·고유 일정1개·ID 정답 표시 제거"))
    def day_update(s):
        day = json.loads(s)
        day["selection_answer_extension"].update(plan=x["plan"], status="program/research/daily_rag_slm/selection_answer_review_2026-10-09_v2.json", report=x["report"], dataset=x["dataset"], unique_itinerary_contents=1, independent_agent_review=True)
        day["updated_at_kst"] = datetime.now().astimezone().isoformat()
        return json.dumps(day, ensure_ascii=False, indent=2) + "\n"
    old.replace("program/research/daily_rag_slm/2026-10-09.json", day_update)
    old.append("program/research/daily_rag_slm/2026-10-09.md", "독립 로컬 검토에서 초기 예시의 정답 ID·일정군 계수·근거 상태 누락을 발견해 새v3로 수정했습니다. 고유 일정은1개이며 예시 정확도·독립성은 주장하지 않습니다. [현재 판·보존 근거](../../../final_project_cs/wiki/records/reports/"+RECORD+"). [수정 직전 백업](_backup/"+old.BACKUP+"/).")
    old.append("final_project_cs/wiki/quality/slm-model-evaluation.md", "`[독립 검토 후 수정 2026-10-09]` 초기 개발 예시의 ID·일정군·근거 상태 표시를 바로잡았고, 사람 검수·실측 전 현재v3로 연결했습니다. [현재 평가 준비 근거](../records/reports/"+RECORD+").")
    old.append("wiki/research/rag-slm-improvements.md", "`[보완 2026-10-09]` 새 평가의 초기 예시 오류를 독립 검토로 수정했으며 고유 일정1개의 개발 자료로만 사용합니다. [수정된 계획·현재 판](../../final_project_cs/wiki/records/reports/"+RECORD+").")
    old.append("final_project_cs/wiki/log.md", "2026-10-09: 통합 평가 예시의 초기 ID 정답 표시·일정군 계수·근거 상태 누락을 모델 전송 전 새판으로 수정했습니다. 사람 검수·독립 검증은 계속 대기입니다. [수정 근거](records/reports/"+RECORD+").")
    print("새 계획v2·개발 자료v3를 현재 기록에 연결했고 초기 원본은 보존했습니다.")


if __name__ == "__main__":
    main()
