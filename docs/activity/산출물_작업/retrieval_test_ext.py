# -*- coding: utf-8 -*-
"""확장 코퍼스(travel_ext) 적재 후 검색 시험 — 활동 scope 4개, top-3. (OpenAI 임베딩 질문당 1회)

    cd final_project_cs
    PYTHONPATH=. python ../docs/activity/산출물_작업/retrieval_test_ext.py
"""
import json
import time
from pathlib import Path

from app.infrastructure.db.session import get_connection
from app.infrastructure.rag.retriever import search_policy

SCOPES = ["travel_activity", "travel_weather", "travel_cancellation", "travel_access"]
CASES = [
    ("R-05", "무료 취소는 언제까지 가능한가요?", "t_ext_02 또는 t_ext_01 또는 기존 72시간 절"),
    ("E-01", "여행사 사정으로 취소되면 얼마를 배상받나요?", "t_ext_02 여행사 사유로 취소하는 경우"),
    ("E-02", "공연 3일 전에 취소하면 얼마를 돌려받나요?", "t_ext_03 관객이 환급을 요구하는 경우"),
    ("E-03", "스키장 시설이 고장 나서 이용을 못 했어요. 환불되나요?", "t_ext_03 시설을 정상적으로 이용할 수 없을 때"),
    ("E-04", "천재지변으로 일정이 취소되면 위약금을 내야 하나요?", "t_ext_01 위약금 없이 해제 / t_ext_02 인원 미달과 불가항력"),
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
        out.append({"id": cid, "query": q, "expect": expect, "ms": ms, "top3": rows})
        print(cid, q, f"[{ms}ms]  기대: {expect}")
        for r in rows:
            print("   ", r["score"], r["scope"], "|", r["document"], "·", r["section"])
Path("retrieval_results_ext.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
