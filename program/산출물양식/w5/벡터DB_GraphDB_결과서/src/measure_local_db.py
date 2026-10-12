"""벡터DB/GraphDB 결과서용 로컬 개발 DB 읽기 전용 측정 (2026-10-06).

- 모든 질의는 READ ONLY 트랜잭션 안에서 돈다(쓰기 0).
- 질문 임베딩 서버(Ollama)가 꺼져 있어, 저장된 청크 벡터를 질의 벡터로 쓴다.
  따라서 잰 시간은 'DB 안의 검색 시간'만이고 질문을 벡터로 바꾸는 시간은 빠진다.
결과: ../_재료/로컬DB_측정_2026-10-06.json
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import psycopg

CS = Path(__file__).resolve().parents[5] / "final_project_cs"
sys.path.insert(0, str(CS))
from app.infrastructure.graphstore.sql_adapter import SqlGraphAdapter  # noqa: E402

DSN = "postgresql://postgres@127.0.0.1:5433/acop_cs"
OUT = Path(__file__).resolve().parents[1] / "_재료" / "로컬DB_측정_2026-10-06.json"
SCOPES = ["travel_activity", "travel_weather", "travel_dining", "travel_mobility",
          "travel_cancellation", "travel_access"]
SEARCH = """SELECT kc.chunk_id, 1 - (kc.embedding_1024 <=> %s::vector) AS score
  FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
 WHERE kd.tenant_id = %s AND kd.scope = ANY(%s) AND kc.embedding_1024 IS NOT NULL
 ORDER BY kc.embedding_1024 <=> %s::vector LIMIT %s"""


def pct(xs, p):
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def main() -> None:
    res: dict = {"measured_at": time.strftime("%Y-%m-%d %H:%M"), "dsn_host": "로컬 개발 DB(5433)"}
    with psycopg.connect(DSN, autocommit=False) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        cur = conn.cursor()
        cur.execute("SELECT version()")
        res["pg_version"] = cur.fetchone()[0].split(",")[0]
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        row = cur.fetchone()
        res["pgvector"] = row[0] if row else None
        cur.execute("""SELECT kd.tenant_id, kd.scope, count(DISTINCT kd.document_id), count(*),
                              count(kc.embedding), count(kc.embedding_1024)
                         FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                        GROUP BY 1,2 ORDER BY 1,2""")
        res["corpus"] = [dict(zip(["tenant", "scope", "docs", "chunks", "dim1536", "dim1024"], r))
                         for r in cur.fetchall()]
        cur.execute("""SELECT indexname, indexdef FROM pg_indexes
                        WHERE tablename='knowledge_chunks' ORDER BY 1""")
        res["indexes"] = [dict(zip(["name", "def"], r)) for r in cur.fetchall()]

        cur.execute("""SELECT kc.chunk_id, kc.embedding_1024::text, kd.tenant_id
                         FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                        WHERE kd.scope = ANY(%s) AND kc.embedding_1024 IS NOT NULL
                        ORDER BY kc.chunk_id""", (SCOPES,))
        probes = cur.fetchall()
        res["probe_count"] = len(probes)
        if probes:
            tenant = probes[0][2]
            # 예열 1회, 이어서 모든 청크를 질의로 한 번씩 3바퀴
            cur.execute(SEARCH, (probes[0][1], tenant, SCOPES, probes[0][1], 3))
            cur.fetchall()
            times, self_hit = [], 0
            for rnd in range(3):
                for cid, vec, _ in probes:
                    t0 = time.perf_counter()
                    cur.execute(SEARCH, (vec, tenant, SCOPES, vec, 3))
                    rows = cur.fetchall()
                    times.append((time.perf_counter() - t0) * 1000)
                    if rnd == 0 and rows and str(rows[0][0]) == str(cid):
                        self_hit += 1
            res["search_ms"] = {
                "n": len(times), "rounds": 3, "top_k": 3,
                "mean": round(statistics.mean(times), 2), "p50": round(pct(times, 50), 2),
                "p95": round(pct(times, 95), 2), "max": round(max(times), 2),
                "note": "DB 안 검색 시간(파이썬 왕복 포함), 질문 임베딩 시간 제외",
            }
            res["self_top1"] = {"hit": self_hit, "of": len(probes)}
            cur.execute("EXPLAIN (ANALYZE, BUFFERS OFF, TIMING ON) " + SEARCH,
                        (probes[0][1], tenant, SCOPES, probes[0][1], 3))
            res["explain"] = [r[0] for r in cur.fetchall()]
            res["tenant"] = tenant

            # 관계 조회 어댑터를 실제로 실행
            g = SqlGraphAdapter(conn, tenant_id=tenant)
            cur.execute("""SELECT kd.document_id::text FROM knowledge_documents kd
                            WHERE kd.tenant_id=%s AND kd.scope = ANY(%s) ORDER BY 1 LIMIT 1""",
                        (tenant, SCOPES))
            doc = cur.fetchone()[0]
            gt = []
            for _ in range(20):
                t0 = time.perf_counter()
                nb = asyncio.run(g.neighbors(doc, ["contains", "in_document"], 2))
                gt.append((time.perf_counter() - t0) * 1000)
            res["graph_neighbors"] = {
                "start": "여행 정책 문서 1건", "edge_types": ["contains", "in_document"], "depth": 2,
                "rows": len(nb), "by_depth": {str(d): sum(1 for r in nb if r["depth"] == d) for d in (1, 2)},
                "ms_p50": round(pct(gt, 50), 2), "ms_p95": round(pct(gt, 95), 2), "n": 20,
            }
            cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (tenant,))
            res["customer_cases"] = cur.fetchone()[0]
            cur.execute("""SELECT cc.case_id::text FROM customer_cases cc
                             JOIN case_events ce ON ce.case_id=cc.case_id
                            WHERE cc.tenant_id=%s GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", (tenant,))
            row = cur.fetchone()
            if row:
                ct = []
                for _ in range(20):
                    t0 = time.perf_counter()
                    sg = asyncio.run(g.subgraph(row[0], 2))
                    ct.append((time.perf_counter() - t0) * 1000)
                edges = sg.get("edges", sg if isinstance(sg, list) else [])
                kinds: dict = {}
                for e in edges:
                    k = e.get("edge_type") if isinstance(e, dict) else None
                    kinds[k] = kinds.get(k, 0) + 1
                res["graph_subgraph"] = {
                    "start": "사건 1건(이벤트가 가장 많은 것)", "depth": 2,
                    "keys": list(sg.keys()) if isinstance(sg, dict) else None,
                    "edge_kinds": kinds, "ms_p50": round(pct(ct, 50), 2),
                    "ms_p95": round(pct(ct, 95), 2), "n": 20,
                }
        conn.rollback()
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str)[:6000])


if __name__ == "__main__":
    main()
