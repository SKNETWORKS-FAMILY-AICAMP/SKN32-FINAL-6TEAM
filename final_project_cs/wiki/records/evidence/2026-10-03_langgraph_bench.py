# -*- coding: utf-8 -*-
"""지금 상태기계 vs LangGraph — 흐름 제어 비용만 가려서 잰다.

    python bench.py --rounds 30

★무엇을 재는가
  문의 한 건이 접수부터 종결까지 가는 동안 **흐름 제어가 쓰는 시간**이다.
  바깥 호출(모델·공공 API)은 양쪽 다 **아예 없앴다** — 그게 들어가면 그날
  날씨 서버가 느린지에 따라 결과가 뒤집힌다. 둘 다 같은 PostgreSQL 에 쓴다.

★왜 교대로 재는가 (A·B·A·B)
  A 를 다 재고 B 를 다 재면, 나중에 잰 쪽이 캐시·커넥션 데움의 덕이나 손해를
  본다. 한 회차 안에서 번갈아 재고, 회차마다 순서를 뒤집는다.

★왜 중앙값과 편차를 같이 적는가
  한두 번 재고 「A 가 낫다」고 하면 안 된다. 편차가 겹치면 **구분되지 않는다**
  고 적는 것이 맞다.

★공정하지 않은 자리를 숨기지 않는다
  - 우리 쪽은 전이마다 **허용 여부 검사 + payload 스키마 검사**를 한다.
    LangGraph 쪽에는 그 검사가 없다. 그만큼 우리 쪽이 일을 더 한다.
  - LangGraph 쪽은 checkpoint 를 쓰고, 우리 쪽은 이벤트 1행 + 투영 1행을 쓴다.
    쓰는 양이 다르므로 바이트 수도 같이 잰다.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Annotated, TypedDict

HERE = Path(__file__).resolve().parent
BASE = HERE / "baseline"
sys.path.insert(0, str(BASE))

TENANT = "bench"


# ────────────────────────────────────────────── 지금 판 (상태기계)
def run_ours(conn, customer_id) -> int:
    """접수 → 분류 → 담당 → 처리 → 종결. 전이 5회."""
    from app.domain.events import EventType
    from app.infrastructure.db.repository import create_case
    from app.core.transition import transition_case

    case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id,
                          subject="벤치마크용 문의")
    steps = [
        (EventType.CREATED, {"channel": "web", "message": "문의"}),
        (EventType.CLASSIFIED, {"intent": "other", "issue_code": "x", "sentiment": "neutral"}),
        (EventType.ROUTED, {"owner_team_id": "activity", "capability": "activity.check"}),
        (EventType.COMPLETED, {"answer_ref": str(uuid.uuid4())}),
    ]
    version = 0
    for event, payload in steps:
        result = transition_case(conn, tenant_id=TENANT, case_id=case_id,
                                 expected_version=version, event_type=event,
                                 payload=payload, actor_type="bench")
        version = result.version
    return version


def run_ours_wait(conn, customer_id) -> int:
    """접수 → 분류 → 담당 → 처리 → **대기 → 재개** → 처리 → 종결. 전이 6회.

    ★LangGraph 가 자기 강점(멈췄다 이어가기)을 쓸 수 있는 조건이다. 직선 경로만
      재면 그쪽이 불리한 자리에서만 잰 셈이 된다.
    """
    from app.domain.events import EventType
    from app.infrastructure.db.repository import create_case
    from app.core.transition import transition_case

    case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id,
                          subject="벤치마크용 문의(대기 포함)")
    steps = [
        (EventType.CREATED, {"channel": "web", "message": "문의"}),
        (EventType.CLASSIFIED, {"intent": "other", "issue_code": "x", "sentiment": "neutral"}),
        (EventType.ROUTED, {"owner_team_id": "activity", "capability": "activity.check"}),
        (EventType.MISSING_INPUT, {"required_input_schema": {"required": ["when"]}}),
        (EventType.VALID_INPUT, {"resume_token_hash": "x" * 64}),
        (EventType.RESUMED, {"resume_node": "validate_input"}),
        (EventType.COMPLETED, {"answer_ref": str(uuid.uuid4())}),
    ]
    version = 0
    for event, payload in steps:
        result = transition_case(conn, tenant_id=TENANT, case_id=case_id,
                                 expected_version=version, event_type=event,
                                 payload=payload, actor_type="bench")
        version = result.version
    return version


# ────────────────────────────────────────────── 비교 판 (LangGraph)
def _merge(old, new):
    """우리 쪽 `state_json` 병합 규칙과 같게 맞춘다 — 덮어쓰기가 아니라 합치기."""
    return {**(old or {}), **(new or {})}


#: ★모듈 수준에 둔다. `from __future__ import annotations` 가 켜져 있어 타입을
#   나중에 평가하는데, 함수 안에 두면 그때 `Annotated` 를 못 찾는다(실측).
class GraphState(TypedDict):
    status: str
    data: Annotated[dict, _merge]


def build_graph(checkpointer):
    """같은 다섯 자리를 그래프로. 각 칸이 하는 일은 상태를 한 칸 옮기는 것뿐이다."""
    from langgraph.graph import END, START, StateGraph

    S = GraphState

    def step(name, payload):
        def go(state: S) -> S:
            return {"status": name, "data": payload}
        return go

    g = StateGraph(S)
    g.add_node("classifying", step("classifying", {"channel": "web", "message": "문의"}))
    g.add_node("routing", step("routing", {"intent": "other", "issue_code": "x",
                                           "sentiment": "neutral"}))
    g.add_node("running", step("running", {"owner_team_id": "activity",
                                           "capability": "activity.check"}))
    g.add_node("resolved", step("resolved", {"answer_ref": "x"}))
    g.add_edge(START, "classifying")
    g.add_edge("classifying", "routing")
    g.add_edge("routing", "running")
    g.add_edge("running", "resolved")
    g.add_edge("resolved", END)
    return g.compile(checkpointer=checkpointer)


def build_graph_wait(checkpointer):
    """같은 길에 **대기 한 번**을 넣는다. LangGraph 의 interrupt 로 멈추고 이어간다."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    S = GraphState

    def step(name, payload):
        def go(state: S) -> S:
            return {"status": name, "data": payload}
        return go

    def waiting(state: S) -> S:
        # ★여기서 그래프가 멈추고 checkpoint 에 남는다. 다음 호출이 이어받는다.
        answer = interrupt({"required": ["when"]})
        return {"status": "resuming", "data": {"when": answer}}

    g = StateGraph(S)
    g.add_node("classifying", step("classifying", {"channel": "web", "message": "문의"}))
    g.add_node("routing", step("routing", {"intent": "other", "issue_code": "x",
                                           "sentiment": "neutral"}))
    g.add_node("running", step("running", {"owner_team_id": "activity",
                                           "capability": "activity.check"}))
    g.add_node("waiting_input", waiting)
    g.add_node("resolved", step("resolved", {"answer_ref": "x"}))
    g.add_edge(START, "classifying")
    g.add_edge("classifying", "routing")
    g.add_edge("routing", "running")
    g.add_edge("running", "waiting_input")
    g.add_edge("waiting_input", "resolved")
    g.add_edge("resolved", END)
    return g.compile(checkpointer=checkpointer)


def run_theirs_wait(graph) -> str:
    """멈추는 데까지 한 번, 이어가는 데 한 번 — 두 번 부른다."""
    from langgraph.types import Command

    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    graph.invoke({"status": "new", "data": {}}, thread)      # waiting_input 에서 멈춤
    out = graph.invoke(Command(resume="2026-10-05"), thread)  # 이어감
    return out["status"]


def run_theirs(graph) -> str:
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    out = graph.invoke({"status": "new", "data": {}}, thread)
    return out["status"]


# ────────────────────────────────────────────── 재기
def sizes(conn) -> dict:
    """양쪽이 디스크에 쓴 양. 표 이름이 다르므로 따로 센다."""
    out = {}
    with conn.cursor() as cur:
        for label, sql in (
            ("ours_bytes", "SELECT pg_total_relation_size('case_events') "
                            "+ pg_total_relation_size('customer_cases')"),
            ("lg_bytes", "SELECT COALESCE(SUM(pg_total_relation_size(c.oid)),0) "
                         "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                         "WHERE n.nspname='public' AND c.relname LIKE 'checkpoint%'"),
        ):
            cur.execute(sql)
            # ★pg_total_relation_size 는 Decimal 로 온다 — 그대로 두면 JSON 이 안 된다.
            out[label] = int(cur.fetchone()[0] or 0)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--throughput", type=int, default=0,
                    help="건수를 이만큼 연달아 밀어 넣어 처리량을 잰다")
    ap.add_argument("--tp-repeats", type=int, default=3,
                    help="처리량을 몇 번 반복해 평균낼지 — 한 번만 재면 그날 상태를 본 것이다")
    args = ap.parse_args()

    os.chdir(BASE)
    from app.infrastructure.db.session import get_connection
    from langgraph.checkpoint.postgres import PostgresSaver
    from app.core.settings import get_settings

    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s,%s) "
                        "ON CONFLICT DO NOTHING", (TENANT, "bench"))
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) "
                        "ON CONFLICT (tenant_id, external_id) DO UPDATE SET external_id=EXCLUDED.external_id "
                        "RETURNING customer_id", (TENANT, "bench-customer"))
            customer_id = cur.fetchone()[0]
        conn.commit()
        before = sizes(conn)

        with PostgresSaver.from_conn_string(url) as saver:
            saver.setup()
            graph = build_graph(saver)
            graph_wait = build_graph_wait(saver)

            # 데움 — 첫 호출은 연결·컴파일 비용이 섞인다
            run_ours(conn, customer_id); conn.commit()
            run_theirs(graph)
            run_ours_wait(conn, customer_id); conn.commit()
            run_theirs_wait(graph_wait)

            ours, theirs = [], []
            ours_w, theirs_w = [], []
            for i in range(args.rounds):
                order = ("ours", "theirs") if i % 2 == 0 else ("theirs", "ours")
                for who in order:
                    t0 = time.perf_counter()
                    if who == "ours":
                        run_ours(conn, customer_id); conn.commit()
                        ours.append((time.perf_counter() - t0) * 1000)
                    else:
                        run_theirs(graph)
                        theirs.append((time.perf_counter() - t0) * 1000)
                # ★대기·재개가 들어간 긴 경로도 같은 회차 안에서 번갈아 잰다.
                for who in order:
                    t0 = time.perf_counter()
                    if who == "ours":
                        run_ours_wait(conn, customer_id); conn.commit()
                        ours_w.append((time.perf_counter() - t0) * 1000)
                    else:
                        run_theirs_wait(graph_wait)
                        theirs_w.append((time.perf_counter() - t0) * 1000)

            # ── 처리량 — 건수를 연달아 밀어 넣는다 ──────────────────
            #   ★한 건씩 재는 것과 다른 질문이다. 「많이 들어오면 어떻게 되나」를 본다.
            tp = {}
            if args.throughput:
                n = args.throughput

                # ★`[2026-10-04 고침]` 전에는 우리 쪽만 **한 트랜잭션으로 묶어** 마지막에
                #   한 번 커밋하고 LangGraph 는 건마다 checkpoint 를 썼다. 조건이 달라
                #   비교가 아니라 변호였다. 이제 **건마다 커밋**해 맞춘다.
                #   ★참고로 묶어 커밋한 값도 같이 낸다 — 둘이 얼마나 다른지가 정보다.
                def ours_each():
                    for _ in range(n):
                        run_ours(conn, customer_id)
                        conn.commit()          # 건마다 — LangGraph 와 같은 조건

                def ours_batch():
                    for _ in range(n):
                        run_ours(conn, customer_id)
                    conn.commit()              # 묶어서 — 우리에게 유리한 조건

                def tp_theirs():
                    for _ in range(n):
                        run_theirs(graph)

                # ★교대로 잰다. 한쪽을 먼저 다 돌리면 뒤가 손해를 본다.
                # ★쌍마다 따로 재고 **중앙값과 사분위 범위**를 낸다 — 평균 하나로 뭉치면
                #   그날 한 번 튄 값이 결론을 흔든다(코덱스 지적, 2026-10-04).
                rates: dict[str, list[float]] = {"each": [], "theirs": [], "batch": []}
                ratios: list[float] = []
                for i in range(args.tp_repeats):
                    order = ([("each", ours_each), ("theirs", tp_theirs)] if i % 2 == 0
                             else [("theirs", tp_theirs), ("each", ours_each)])
                    for name, fn in order:
                        t0 = time.perf_counter()
                        fn()
                        rates[name].append(n / (time.perf_counter() - t0))
                    t0 = time.perf_counter()
                    ours_batch()
                    rates["batch"].append(n / (time.perf_counter() - t0))
                    ratios.append(rates["each"][-1] / rates["theirs"][-1])

                def spread(xs: list[float]) -> dict:
                    lo, hi = (statistics.quantiles(xs, n=4)[0],
                              statistics.quantiles(xs, n=4)[-1]) if len(xs) > 3 else (min(xs), max(xs))
                    return {"중앙값_초당건": round(statistics.median(xs), 1),
                            "사분위범위": [round(lo, 1), round(hi, 1)]}

                tp = {"건수": n, "쌍": args.tp_repeats,
                      "ours_건마다_커밋": spread(rates["each"]),
                      "langgraph": spread(rates["theirs"]),
                      "배수_중앙값": round(statistics.median(ratios), 2),
                      "ours_묶어_커밋(참고)": spread(rates["batch"]),
                      "비고": "건마다 커밋이 공정한 비교다. 묶어 커밋은 우리에게 유리한 조건이라 참고로만 둔다"}

        after = sizes(conn)

    def stat(xs):
        return {"n": len(xs), "median_ms": round(statistics.median(xs), 2),
                "mean_ms": round(statistics.mean(xs), 2),
                "stdev_ms": round(statistics.stdev(xs), 2) if len(xs) > 1 else 0.0,
                "min_ms": round(min(xs), 2), "max_ms": round(max(xs), 2)}

    report = {
        "rounds": args.rounds,
        "external_calls": "없음 (양쪽 다 제거)",
        "straight": {
            "scenario": "접수 → 분류 → 담당 → 처리 → 종결 (전이 4회)",
            "ours": stat(ours), "langgraph": stat(theirs),
        },
        "with_wait": {
            "scenario": "위에 **대기 → 재개** 한 번을 넣은 길 (전이 6회)",
            "note": "LangGraph 는 interrupt 로 멈추고 Command 로 이어간다 — 그쪽 강점 자리다",
            "ours": stat(ours_w), "langgraph": stat(theirs_w),
        },
        "throughput": tp,
        "bytes_written": {
            "ours": after["ours_bytes"] - before["ours_bytes"],
            "langgraph": after["lg_bytes"] - before["lg_bytes"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
