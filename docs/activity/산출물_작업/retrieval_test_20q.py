# -*- coding: utf-8 -*-
"""검색 시험 20문항 — 활동 scope 4개, top-3. 정답 절은 결과를 보기 전에 정했다(질문마다 허용 절 목록).

    cd final_project_cs
    PYTHONPATH=. python ../docs/activity/산출물_작업/retrieval_test_20q.py
"""
import json
import time
from pathlib import Path

from app.infrastructure.db.session import get_connection
from app.infrastructure.rag.retriever import search_policy

SCOPES = ["travel_activity", "travel_weather", "travel_cancellation", "travel_access"]
DOM = "소비자분쟁해결기준 — 국내여행"
STD = "국내여행 표준약관 — 해제·변경·해지"
LEI = "소비자분쟁해결기준 — 체육시설·레저·공연"
ACT = "활동 취소·변경 접수와 시점 구간"
FREE = "무료·무예약 활동을 무엇으로 판정하나"
AIR = "대기질·폭염·한파·지진 경보와 야외 일정"
WTH = "기상 사유로 활동이 깨졌을 때의 순연과 취소"
ACC = "동행 조건을 확인하고 안내하는 기준"
CASES = [
 ("Q01", "여행 3일 전에 취소하려는데 수수료가 있나요?", [(DOM, "여행자 사유로 취소하는 경우"), (STD, "출발 전 계약 해제와 손해 배상")]),
 ("Q02", "숙박 여행을 하루 전에 취소하면 얼마나 떼나요?", [(DOM, "여행자 사유로 취소하는 경우")]),
 ("Q03", "여행사가 일정을 갑자기 취소했는데 보상은 어떻게 되나요?", [(DOM, "여행사 사유로 취소하는 경우")]),
 ("Q04", "여행사가 약속한 일정과 장소를 바꿨어요. 계약을 해지하면 어떻게 되나요?", [(DOM, "여행사가 계약 조건을 바꿔 해지하는 경우"), (STD, "여행 조건을 바꿀 수 있는 경우")]),
 ("Q05", "최소 인원이 안 차서 여행이 취소됐다는데 출발 하루 전에야 연락을 받았어요", [(STD, "최저 인원이 채워지지 않았을 때"), (DOM, "인원 미달과 불가항력으로 취소하는 경우")]),
 ("Q06", "태풍 때문에 여행이 취소됐는데 위약금을 내야 하나요?", [(DOM, "인원 미달과 불가항력으로 취소하는 경우"), (STD, "위약금 없이 해제할 수 있는 사유")]),
 ("Q07", "감염병이 퍼져서 취소하려는데 위약금은요?", [(DOM, "감염병과 재난으로 해제를 요청하는 경우")]),
 ("Q08", "여행 중에 버스가 많이 늦어서 일정을 못 했어요. 배상받을 수 있나요?", [(STD, "교통 지연으로 생긴 손해")]),
 ("Q09", "여행 도중에 그만두고 돌아가고 싶은데 추가 비용은 누가 내나요?", [(STD, "여행 도중 계약을 해지할 때")]),
 ("Q10", "가까운 가족이 돌아가셔서 여행을 못 가요. 위약금 없이 취소되나요?", [(STD, "위약금 없이 해제할 수 있는 사유")]),
 ("Q11", "스키장 리프트가 고장 나서 못 탔어요. 환불되나요?", [(LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("Q12", "광고에서 본 것과 다르게 체험이 진행됐어요. 환불해 주세요", [(LEI, "광고나 계약 내용과 실제가 다른 경우")]),
 ("Q13", "요가 수강권을 중간에 해지하면 위약금이 얼마인가요?", [(LEI, "소비자 책임으로 해제하는 경우의 반환 금액")]),
 ("Q14", "공연이 취소됐는데 티켓값을 돌려받을 수 있나요?", [(LEI, "공연이 취소되거나 연기된 경우")]),
 ("Q15", "콘서트를 하루 전에 취소하면 환불이 얼마나 되나요?", [(LEI, "관객이 환급을 요구하는 경우")]),
 ("Q16", "예약 시각이 72시간 안인데 일정을 바꿀 수 있나요?", [(ACT, "무료 구간은 72시간이다"), (ACT, "72시간 안쪽에서 벌어지는 일")]),
 ("Q17", "미세먼지가 심하면 야외 일정은 어떻게 되나요?", [(AIR, "초미세먼지 경보가 걸렸을 때"), (AIR, "대기질 단계는 발표된 이름으로 옮긴다")]),
 ("Q18", "휠체어를 쓰는 부모님과 같이 갈 수 있는 곳인가요?", [(ACC, "휠체어 이용과 이동 보조"), ("동행자의 이용 조건 확인", "동행자의 이용 조건 확인")]),
 ("Q19", "비 와서 야외 활동이 안 되면 비용은 누가 부담하나요?", [(WTH, "우천으로 야외 활동이 깨진 경우의 부담"), (WTH, "순연과 취소를 가르는 기준")]),
 ("Q20", "입장료가 없는 공원도 취소 처리를 해야 하나요?", [(FREE, "무료·무예약이면 취소 대상이 아니다")]),
]
out = []
with get_connection() as conn, conn.cursor() as cur:
    def title(doc_id, no):
        cur.execute("""SELECT d.title, k.metadata_json->>'section_title' FROM knowledge_chunks k
                       JOIN knowledge_documents d USING(document_id)
                       WHERE k.metadata_json->>'document_id'=%s AND k.chunk_no=%s LIMIT 1""", (doc_id, no))
        r = cur.fetchone()
        return (r[0], r[1]) if r else (None, None)

    for cid, q, expect in CASES:
        t0 = time.time()
        hits = search_policy("demo", q, SCOPES, top_k=3)
        ms = int((time.time() - t0) * 1000)
        rows = []
        for h in hits:
            dt, st = title(h.document_id, h.chunk_no)
            rows.append({"scope": h.scope, "document": dt, "section": st, "score": round(h.score, 3)})
        rank = next((i for i, r in enumerate(rows, 1) if (r["document"], r["section"]) in expect), None)
        out.append({"id": cid, "query": q, "expect": [f"{d} · {s}" for d, s in expect], "ms": ms, "rank": rank, "top3": rows})
        print(cid, "적중" if rank else "미적중", f"rank={rank}", f"[{ms}ms]", q)
        for r in rows:
            print("    ", r["score"], "|", r["document"], "·", r["section"])
n = sum(1 for o in out if o["rank"])
print(f"\nHit@3 {n}/{len(out)} = {n/len(out):.0%} · Hit@1 {sum(1 for o in out if o['rank']==1)}/{len(out)}")
Path("../docs/activity/산출물_작업/retrieval_results_20q_2026-10-14.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
