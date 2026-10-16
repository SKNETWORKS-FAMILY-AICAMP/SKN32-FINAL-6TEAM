# -*- coding: utf-8 -*-
"""검색 시험 10문항(패턴 1~3 절 보강 후 새 질문) — 활동 scope 4개, top-3. 정답 절은 결과를 보기 전에 정했다(질문마다 허용 절 목록).

    cd final_project_cs
    PYTHONPATH=. python ../docs/activity/산출물_작업/retrieval_test_20q.py
"""
import json
import os
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
 ("M01", "체험 예약했는데 홍보 사진과 실제가 너무 달라서 환불받고 싶어요", [(LEI, "광고나 계약 내용과 실제가 다른 경우")]),
 ("M02", "서핑 강습 소개 영상과 다르게 진행됐는데 돈을 돌려받을 수 있나요?", [(LEI, "광고나 계약 내용과 실제가 다른 경우")]),
 ("M03", "예약하고 갔는데 수영장이 만원이라 입장을 못 했어요", [(LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("M04", "예약한 클라이밍장이 정원이 차서 이용을 못 했어요", [(LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("M05", "할머니가 돌아가셔서 여행을 못 가게 됐어요. 취소 수수료는요?", [(STD, "위약금 없이 해제할 수 있는 사유")]),
 ("M06", "삼촌 장례 때문에 일정을 취소하려고 해요. 위약금이 있나요?", [(STD, "위약금 없이 해제할 수 있는 사유")]),
 ("M07", "몸이 많이 아파서 여행 참가가 어려운데 위약금 없이 취소되나요?", [(STD, "위약금 없이 해제할 수 있는 사유")]),
 ("M08", "필라테스 센터 이용권을 사정이 생겨 해지하면 위약금이 얼마예요?", [(LEI, "소비자 책임으로 해제하는 경우의 반환 금액")]),
 ("M09", "공연 당일 오전에 표를 취소하면 얼마나 돌려받나요?", [(LEI, "관객이 환급을 요구하는 경우")]),
 ("M10", "여행사가 일정을 바꿔서 해지했어요. 통보 시점에 따라 보상이 다른가요?", [(DOM, "여행사가 계약 조건을 바꿔 해지하는 경우"), (STD, "여행 조건을 바꿀 수 있는 경우")]),
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
        if os.environ.get("EXPAND") == "1":
            from app.domains.travel_ops.instances.activity.policy_query import expand_policy_query
            qq = expand_policy_query(q)
        else:
            qq = q
        hits = search_policy("demo", qq, SCOPES, top_k=3)
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
Path("../docs/activity/산출물_작업/retrieval_results_10q_round2_2026-10-14.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
