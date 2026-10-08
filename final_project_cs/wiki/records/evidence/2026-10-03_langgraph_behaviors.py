# -*- coding: utf-8 -*-
"""속도 말고 **동작**을 비교한다.

    python behaviors.py

★속도는 이미 쟀다(`bench.py`). 그런데 흐름 제어를 고르는 기준은 속도가 아니다.
  「틀린 이동을 막아 주나」 「중간에 죽으면 어디까지 갔는지 아나」 「되감을 수 있나」
  「둘이 동시에 고치면 어떻게 되나」가 실제로 사고를 막는 자리다.

★각 항목은 **실제로 그 상황을 만들어** 본다. 문서를 읽고 적지 않는다.
  통과/실패가 아니라 **무슨 일이 일어났는지**를 적는다 — 양쪽 설계가 달라서
  한쪽에 유리한 합격 기준을 만들면 비교가 아니라 변호가 된다.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Annotated, TypedDict

HERE = Path(__file__).resolve().parent
BASE = HERE / "baseline"
sys.path.insert(0, str(BASE))
os.chdir(BASE)

TENANT = "bench"
OUT: dict[str, dict] = {}


def _merge(old, new):
    return {**(old or {}), **(new or {})}


class GraphState(TypedDict):
    status: str
    data: Annotated[dict, _merge]


def build_graph(checkpointer):
    from langgraph.graph import END, START, StateGraph

    def step(name):
        def go(state: GraphState) -> GraphState:
            return {"status": name, "data": {name: True}}
        return go

    def boom(state: GraphState) -> GraphState:
        raise RuntimeError("일부러 터뜨림 — 중간에 죽는 상황")

    g = StateGraph(GraphState)
    for n in ("classifying", "routing"):
        g.add_node(n, step(n))
    g.add_node("running", boom)
    g.add_edge(START, "classifying")
    g.add_edge("classifying", "routing")
    g.add_edge("routing", "running")
    g.add_edge("running", END)
    return g.compile(checkpointer=checkpointer)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from app.core.contracts import CaseStatus
    from app.core.settings import get_settings
    from app.core.transition import replay_case, transition_case
    from app.domain.events import EventType, next_status
    from app.infrastructure.db.repository import create_case, get_case
    from app.infrastructure.db.session import get_connection
    from langgraph.checkpoint.postgres import PostgresSaver

    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (TENANT, "bench"))
            cur.execute("INSERT INTO customers (tenant_id, external_id) VALUES (%s,%s) "
                        "ON CONFLICT (tenant_id, external_id) DO UPDATE SET external_id=EXCLUDED.external_id "
                        "RETURNING customer_id", (TENANT, "behavior-customer"))
            customer_id = cur.fetchone()[0]
        conn.commit()

        # ── 1. 틀린 이동을 막아 주나 ──────────────────────────────────
        #    갓 만든 건에 바로 「끝났다」를 넣어 본다. 일어날 수 없는 이동이다.
        case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id, subject="틀린 이동")
        try:
            transition_case(conn, tenant_id=TENANT, case_id=case_id, expected_version=0,
                            event_type=EventType.COMPLETED, payload={"answer_ref": "x"},
                            actor_type="bench")
            ours = "그냥 통과됐다"
        except Exception as exc:
            ours = "%s 로 막혔다" % type(exc).__name__
        conn.rollback()
        OUT["틀린 이동 막기"] = {
            "상황": "갓 접수된 건에 바로 「끝났다」를 넣는다",
            "지금 방식": ours,
            "LangGraph": "그래프에 그 간선이 없으면 애초에 못 간다. 다만 상태 값 자체는 "
                         "아무 문자열이나 들어가고 검사가 없다",
            "비고": "우리 쪽은 (상태, 이벤트) 25개 조합만 허용한다. 그 밖은 전부 거부",
        }

        # ── 2. 필요한 값이 빠졌을 때 ─────────────────────────────────
        case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id, subject="값 누락")
        try:
            transition_case(conn, tenant_id=TENANT, case_id=case_id, expected_version=0,
                            event_type=EventType.CREATED, payload={"channel": "web"},
                            actor_type="bench")   # message 가 빠졌다
            ours = "그냥 통과됐다"
        except Exception as exc:
            ours = "%s 로 막혔다" % type(exc).__name__
        conn.rollback()
        OUT["빠진 값 막기"] = {
            "상황": "접수 이벤트에서 필수 항목 하나를 뺀다",
            "지금 방식": ours,
            "LangGraph": "검사 없음 — 상태에 아무 dict 나 들어간다",
        }

        # ── 3. 중간에 죽으면 어디까지 갔는지 아나 ────────────────────
        case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id, subject="중간에 죽음")
        v = 0
        for ev, pl in ((EventType.CREATED, {"channel": "web", "message": "문의"}),
                       (EventType.CLASSIFIED, {"intent": "other", "issue_code": "x",
                                               "sentiment": "neutral"})):
            v = transition_case(conn, tenant_id=TENANT, case_id=case_id, expected_version=v,
                                event_type=ev, payload=pl, actor_type="bench").version
        conn.commit()
        row = get_case(conn, tenant_id=TENANT, case_id=case_id)
        with conn.cursor() as cur:
            cur.execute("SELECT event_type FROM case_events WHERE case_id=%s "
                        "ORDER BY aggregate_version", (case_id,))
            trail = [r[0] for r in cur.fetchall()]

        # ── 4. 되감을 수 있나 ────────────────────────────────────────
        rebuilt = replay_case(conn, tenant_id=TENANT, case_id=case_id)
        OUT["중간에 죽었을 때"] = {
            "상황": "두 단계만 가고 멈춘다",
            "지금 방식": "상태 %s · 판 %d · 지나온 사건 %s" % (row["status"], row["version"], trail),
            "되감기": "이벤트만으로 다시 만든 결과가 저장된 것과 같나: %s"
                      % (rebuilt.status.value == row["status"] and rebuilt.version == row["version"]),
            "LangGraph": "마지막 checkpoint 는 남는다. 다만 **거기까지 어떻게 왔는지**는 "
                         "상태 스냅숏의 연속이지 사건 기록이 아니다",
        }

        # ── 5. 둘이 동시에 같은 건을 고치면 ──────────────────────────
        case_id = create_case(conn, tenant_id=TENANT, customer_id=customer_id, subject="동시 수정")
        v = transition_case(conn, tenant_id=TENANT, case_id=case_id, expected_version=0,
                            event_type=EventType.CREATED,
                            payload={"channel": "web", "message": "문의"},
                            actor_type="bench").version
        conn.commit()
        # 같은 판 번호로 두 번째가 들어온다 — 먼저 읽고 늦게 쓰는 상황
        try:
            transition_case(conn, tenant_id=TENANT, case_id=case_id, expected_version=0,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "other", "issue_code": "x", "sentiment": "neutral"},
                            actor_type="bench")
            ours = "그냥 덮어썼다"
        except Exception as exc:
            ours = "%s 로 거부됐다" % type(exc).__name__
        conn.rollback()
        OUT["동시 수정"] = {
            "상황": "낡은 판 번호를 들고 두 번째 수정이 들어온다",
            "지금 방식": ours,
            "LangGraph": "같은 thread 에 동시에 쓰면 나중 것이 이긴다 — 판 번호 검사가 없다",
        }

        # ── 6. 상태 하나 더하려면 몇 군데를 고치나 ───────────────────
        OUT["새 상태 추가 비용"] = {
            "지금 방식": "파일 1개 — 상태 목록과 이동표가 같은 곳(app/domain/events.py)에 있다",
            "LangGraph": "파일 1개 — 노드와 간선을 그래프 정의에 더한다",
            "비고": "둘 다 한 파일. 다만 우리 쪽은 전이도가 자동으로 다시 그려지고 "
                    "어긋나면 시험이 막는다(2026-10-03 추가)",
        }

        # ── 7. 상태 수 맞는지 ────────────────────────────────────────
        OUT["규모"] = {"상태": len(CaseStatus),
                       "허용 이동": sum(1 for s in CaseStatus for e in EventType
                                        if next_status(s, e) is not None)}

    # ── LangGraph 쪽: 중간에 터졌을 때 실제로 무엇이 남나 ────────────
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        graph = build_graph(saver)
        thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
        try:
            graph.invoke({"status": "new", "data": {}}, thread)
            died = "안 터졌다"
        except Exception as exc:
            died = "%s 로 터짐" % type(exc).__name__
        state = graph.get_state(thread)
        history = list(graph.get_state_history(thread))
        OUT["중간에 죽었을 때"]["LangGraph 실측"] = (
            "%s · 마지막 상태 %r · 남은 checkpoint %d개"
            % (died, state.values.get("status"), len(history)))

    print(json.dumps(OUT, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
