import re, json, numpy as np
from openai import OpenAI
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

def load_cases(path):
    src = open(path, encoding="utf-8").read()
    head = src[:src.index("out = []")]
    ns = {}
    exec(head.split("from app.infrastructure.rag.retriever import search_policy")[0].split("import json")[0] and "", ns)
    # CASES 정의부만 평가
    pre = src[src.index('SCOPES ='):src.index("out = []")]
    exec(pre, ns)
    return ns["CASES"]
CASES = load_cases("../docs/activity/산출물_작업/retrieval_test_20q.py") + load_cases("../docs/activity/산출물_작업/retrieval_test_10q.py")
with get_connection() as c, c.cursor() as cur:
    cur.execute("""SELECT d.title, k.metadata_json->>'section_title', k.content FROM knowledge_chunks k
      JOIN knowledge_documents d USING(document_id)
      WHERE d.scope IN ('travel_activity','travel_weather','travel_cancellation','travel_access')""")
    CH = cur.fetchall()
print("chunks", len(CH), "questions", len(CASES))
cl = OpenAI(api_key=get_settings().openai_api_key)
def emb(model, texts, dims=None):
    out = []
    for i in range(0, len(texts), 64):
        kw = {"dimensions": dims} if dims else {}
        r = cl.embeddings.create(model=model, input=texts[i:i+64], **kw)
        out += [d.embedding for d in r.data]
    a = np.array(out, dtype=np.float32); return a / np.linalg.norm(a, axis=1, keepdims=True)
def run(model, dims=None):
    C = emb(model, [x[2] for x in CH], dims); Q = emb(model, [q for _, q, _ in CASES], dims)
    S = Q @ C.T; res = []
    for qi, (cid, q, exp) in enumerate(CASES):
        top = np.argsort(-S[qi])[:3]
        rank = next((r for r, j in enumerate(top, 1) if (CH[j][0], CH[j][1]) in exp), None)
        res.append((cid, rank, float(S[qi][top[0]])))
    return res
rows = {}
for name, m, d in [("small-1536", "text-embedding-3-small", None), ("large-1536", "text-embedding-3-large", 1536), ("large-3072", "text-embedding-3-large", None)]:
    r = run(m, d); rows[name] = r
    n = lambda ids: (sum(1 for x in r if x[0] in ids and x[1]), sum(1 for x in r if x[0] in ids and x[1] == 1), len(ids))
    q20 = {c for c, _, _ in r if c.startswith("Q")}; q10 = {c for c, _, _ in r if c.startswith("N")}
    a, b = n(q20), n(q10)
    print(f"{name:11} 20문항 Hit@3 {a[0]}/{a[2]} Hit@1 {a[1]} | 새10문항 Hit@3 {b[0]}/{b[2]} Hit@1 {b[1]} | 전체 {a[0]+b[0]}/30")
print("미적중:", {k: [x[0] for x in v if not x[1]] for k, v in rows.items()})
