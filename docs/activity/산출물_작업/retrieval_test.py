import json, time
from app.infrastructure.rag.retriever import search_policy
from app.infrastructure.db.session import get_connection
SCOPES = ["travel_activity", "travel_weather", "travel_cancellation", "travel_access"]
CASES = [
 ("R-01", "예약 없는 산책도 일정에서 확인할 수 있나요?", "travel_activity"),
 ("R-02", "비 오면 야외 일정을 무조건 취소하나요?", "travel_weather"),
 ("R-03", "취소하면 위약금이 얼마인가요?", "travel_cancellation"),
 ("R-04", "휠체어로 이용할 수 있는 장소인가요?", "travel_access"),
 ("R-05", "무료 취소는 언제까지 가능한가요?", "travel_activity"),
 ("R-06", "휴관일에 가면 어떻게 되나요?", "travel_activity"),
 ("R-07", "오늘 주식 시장 전망 알려줘", "(범위 밖)"),
]
out = []
with get_connection() as conn, conn.cursor() as cur:
    def title(doc_id, no):
        cur.execute("""SELECT d.title, k.metadata_json->>'section_title' FROM knowledge_chunks k
                       JOIN knowledge_documents d USING(document_id)
                       WHERE k.metadata_json->>'document_id'=%s AND k.chunk_no=%s LIMIT 1""", (doc_id, no))
        r = cur.fetchone(); return (r[0], r[1]) if r else (None, None)
    for cid, q, expect in CASES:
        t0 = time.time(); hits = search_policy("demo", q, SCOPES, top_k=3); ms = int((time.time()-t0)*1000)
        rows = []
        for h in hits:
            dt, st = title(h.document_id, h.chunk_no)
            rows.append({"scope": h.scope, "document": dt, "section": st, "score": round(h.score, 3)})
        out.append({"id": cid, "query": q, "expect_scope": expect, "ms": ms, "top3": rows})
        print(cid, q, f"[{ms}ms]")
        for r in rows: print("   ", r["score"], r["scope"], "|", r["document"], "·", r["section"])
json.dump(out, open("retrieval_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
