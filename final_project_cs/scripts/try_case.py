"""문장 하나로 Case 를 실제 경로대로 열고 돌린다 — 분류 → 담당 팀 → 팀 실행 → 결과. DB 가 떠 있어야 한다.

- 서버(HTTP)는 띄우지 않는다. `POST /v1/cases` 가 부르는 접수 함수(`open_case`)와 컨트롤러(`run_case`)를 같은 순서로 직접 부른다.
- 이 스크립트 전용 테넌트 · 고객을 만들고, 끝나면 그 테넌트의 행을 지운다(`--keep` 이면 남긴다).
- 문장 하나 = 분류 모델 1번 + 팀 실행(숙소 · 항공 팀이면 해석 모델 1번 + 마이리얼트립 몇 번).
- 숙소 · 항공 팀은 프롬프트를 DB 에서 읽는다 — 먼저 `python -m scripts.register_prompts` 를 돌려 둔다.

실행 위치: final_project_cs
  python -m scripts.try_case "11월 6일부터 9일까지 성인 2명 용산 근처 호텔 찾아줘"
  python -m scripts.try_case --keep "김포에서 제주 11월 6일 갔다가 9일에 오는 비행기 성인 1명"
"""
from argparse import ArgumentParser
import asyncio
from datetime import datetime
import platform
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

CLEANUP = (
    "DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)",
    "DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)",
    "DELETE FROM agent_runs WHERE tenant_id=%s",
    "DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)",
    "DELETE FROM action_requests WHERE tenant_id=%s",
    "DELETE FROM case_events WHERE tenant_id=%s",
    "DELETE FROM outbox WHERE tenant_id=%s",
    "DELETE FROM customer_cases WHERE tenant_id=%s",
    "DELETE FROM customers WHERE tenant_id=%s",
    "DELETE FROM tenants WHERE tenant_id=%s",
)


def main():
    from app import composition
    from app.application.case_intake import open_case
    from app.infrastructure.db import repository
    from app.infrastructure.db.session import get_connection

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("sentences", nargs="+")
    parser.add_argument("--keep", action="store_true", help="끝나고 행을 지우지 않는다")
    args = parser.parse_args()
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")

    tenant, customer = "try_case_" + uuid4().hex[:12], uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "try_case script"))
        cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)",
                    (customer, tenant, "try-case-customer"))
    print(f"테넌트 {tenant}")
    classifier, controller = composition.build_classifier(), composition.build_controller()
    try:
        for text in args.sentences:
            print(f"\n[문장] {text}")
            started = time.perf_counter()
            with get_connection() as conn:
                opened = open_case(conn, repository=repository, tenant_id=tenant, customer_id=customer,
                                   request_id=uuid4().hex, message=text, channel="try", actor_type="api",
                                   actor_id="try_case", classifier=classifier)
                case = repository.get_case(conn, tenant_id=tenant, case_id=opened.case_id)
            print(f"[접수] {time.perf_counter() - started:.1f}초 · 상태 {case['status']} · intent {case.get('intent')} · "
                  f"issue_code {case.get('issue_code')}")
            if str(case["status"]) == "routing":
                ran = time.perf_counter()
                outcome = asyncio.run(controller.run_case(tenant_id=tenant, case_id=opened.case_id, actor_id="try_case"))
                print(f"[실행] {time.perf_counter() - ran:.1f}초 · {outcome}")
            with get_connection() as conn, conn.cursor() as cur:
                case = repository.get_case(conn, tenant_id=tenant, case_id=opened.case_id)
                cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY created_at", (opened.case_id,))
                events = [row[0] for row in cur.fetchall()]
            state = case.get("state_json") or {}
            print(f"[결과] 전체 {time.perf_counter() - started:.1f}초 · 상태 {case['status']} · 담당 팀 {case.get('owner_team_id')}")
            print(f"[이벤트] {' → '.join(events)}")
            for key in ("failure_code", "escalation_reason", "routing_failure", "warnings"):
                if state.get(key):
                    print(f"[{key}] {state[key]}")
            print("[답]")
            print(state.get("answer") or "(없음)")
    finally:
        if args.keep:
            print(f"\n행을 남겼다 — 테넌트 {tenant}")
        else:
            with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
                for statement in CLEANUP:
                    cur.execute(statement, (tenant,))
            print(f"\n테넌트 {tenant} 의 행을 지웠다")


if __name__ == "__main__":
    main()
