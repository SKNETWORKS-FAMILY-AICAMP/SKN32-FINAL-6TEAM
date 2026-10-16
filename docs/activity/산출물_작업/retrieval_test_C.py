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
 ("C01", "부모님이 갑자기 입원하셔서 3일 넘게 병원에 계셔야 해요. 예정된 여행을 취소해도 되나요?", [(STD, "위약금 없이 해제할 수 있는 사유"), (STD, "가족 사망·질병 등 개인 사유로 위약금 없이 해제하는 경우")]),
 ("C02", "눈이 많이 와서 케이블카가 운행을 안 한대요. 이럴 때 환불받을 수 있어요?", [(DOM, "인원 미달과 불가항력으로 취소하는 경우"), (DOM, "천재지변·정부 명령 같은 불가항력으로 취소하는 경우"), (STD, "위약금 없이 해제할 수 있는 사유"), (STD, "천재지변·정부 명령 등 위약금 없이 해제할 수 있는 공통 사유"), (LEI, "시설을 정상적으로 이용할 수 없을 때")]),
 ("C03", "여행사에서 최소 인원이 안 됐다고 이틀 전에 취소 연락이 왔어요", [(STD, "최저 인원이 채워지지 않았을 때"), (DOM, "인원 미달과 불가항력으로 취소하는 경우"), (DOM, "인원 미달로 여행사가 취소하는 경우")]),
 ("C04", "아이가 감기로 열이 나서 못 가게 됐는데 환불되나요?", [(STD, "위약금 없이 해제할 수 있는 사유"), (STD, "가족 사망·질병 등 개인 사유로 위약금 없이 해제하는 경우")]),
 ("C05", "골프연습장 3개월권을 끊었다가 한 달 쓰고 그만두려고요. 얼마 돌려받나요?", [(LEI, "소비자 책임으로 해제하는 경우의 반환 금액")]),
 ("C06", "회원권을 샀는데 시설이 설명이랑 달라요. 전액 돌려받을 수 있나요?", [(LEI, "광고나 계약 내용과 실제가 다른 경우")]),
 ("C07", "콘서트가 가수 사정으로 취소됐어요. 표값 말고 따로 받는 건 없나요?", [(LEI, "공연이 취소되거나 연기된 경우")]),
 ("C08", "공연 10일 전인데 지금 취소하면 전액 환불 맞죠?", [(LEI, "관객이 환급을 요구하는 경우")]),
 ("C09", "여행 중간에 사정이 생겨서 먼저 돌아가야 하는데 남은 일정 요금은 어떻게 되나요?", [(STD, "여행 도중 계약을 해지할 때")]),
 ("C10", "전염병 때문에 정부가 시설 문을 닫으라고 해서 예약한 체험을 못 했어요", [(DOM, "감염병과 재난으로 해제를 요청하는 경우"), (DOM, "인원 미달과 불가항력으로 취소하는 경우"), (DOM, "천재지변·정부 명령 같은 불가항력으로 취소하는 경우")]),
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
Path("../docs/activity/산출물_작업/retrieval_results_C_" + os.environ.get("TAG", "x") + ".json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
