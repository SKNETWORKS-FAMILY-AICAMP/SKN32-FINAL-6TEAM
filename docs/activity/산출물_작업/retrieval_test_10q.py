# -*- coding: utf-8 -*-
"""검색 시험 10문항(레저·공연 구어체 반영 후 새 질문) — 활동 scope 4개, top-3. 정답 절은 결과를 보기 전에 정했다(질문마다 허용 절 목록).

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
 ("N01", "리프트가 멈춰서 스키를 못 탔는데 이용권 환불이 되나요?", [(LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("N02", "헬스장 회원권을 이사 때문에 해지하려는데 얼마나 돌려받나요?", [(LEI, "소비자 책임으로 해제하는 경우의 반환 금액")]),
 ("N03", "예약한 패러글라이딩 체험이 광고 영상과 완전히 달랐어요", [(LEI, "광고나 계약 내용과 실제가 다른 경우")]),
 ("N04", "뮤지컬 일주일 전에 예매를 취소하면 수수료가 얼마예요?", [(LEI, "관객이 환급을 요구하는 경우")]),
 ("N05", "비 때문에 야외 공연이 취소됐어요. 표값은 어떻게 되나요?", [(LEI, "공연이 취소되거나 연기된 경우")]),
 ("N06", "주연 배우가 바뀌었는데 환불받을 수 있나요?", [(LEI, "공연이 취소되거나 연기된 경우")]),
 ("N07", "수영장에 갔더니 정원이 꽉 차서 못 들어갔어요", [(LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("N08", "시설 사정으로 이용권을 해지하면 남은 기간만큼 돌려주나요?", [(LEI, "사업자 책임으로 해제하는 경우의 반환 금액")]),
 ("N09", "여행사가 최소 인원 미달로 취소하면서 늦게 알려줬어요. 배상은요?", [(STD, "최저 인원이 채워지지 않았을 때"), (DOM, "인원 미달과 불가항력으로 취소하는 경우")]),
 ("N10", "공기가 나쁜 날에는 야외 체험 일정을 바꿔 주나요?", [(AIR, "초미세먼지 경보가 걸렸을 때"), (AIR, "대기질 단계는 발표된 이름으로 옮긴다"), ("날씨로 활동을 바꾸는 경우", "날씨로 활동을 바꾸는 경우")]),
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
Path("../docs/activity/산출물_작업/retrieval_results_10q_after_colloquial_2026-10-14.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
