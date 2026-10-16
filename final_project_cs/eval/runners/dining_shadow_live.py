# -*- coding: utf-8 -*-
"""판정 에이전트 그림자 — 실제 접수 하나에 실제 모델 · 바깥 조회(카카오 · 구글)를 붙여 돌린다. 스위치는 **이 프로세스에서만** 켠다. `[2026-10-16]`

    python -m eval.runners.dining_shadow_live <intake_id> [tenant]     # DB = .env 의 ACOP_DATABASE_URL(로컬 dining_rebuild)

★접수가 확인 화면으로 넘긴 뒤 부르는 것과 같은 입구(`pipeline._dining_shadow` 와 같은 load → runner)를 쓴다. 고객 결과는 바꾸지 않고
  `dining.dn_agent_shadow` 에 한 판이 더 쌓인다. 결과 · 부른 도구는 eval/reports/2026-10-16_dining_shadow_live.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from uuid import UUID

OUT = Path(__file__).resolve().parents[1] / "reports" / "2026-10-16_dining_shadow_live.json"


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    intake_id, tenant = UUID(argv[0]), (argv[1] if len(argv) > 1 else "demo")
    import hashlib

    from app import composition
    from app.core import settings as settings_module
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.intake import review as review_module
    from app.infrastructure.db.session import get_connection

    config = Path(__file__).resolve().parents[2] / "config" / "guardrails.yaml"
    before = hashlib.sha256(config.read_bytes()).hexdigest()
    model = str(get_guardrails().get("travel.dining.agent_shadow.model") or "openai:gpt-6-luna")
    settings_module.dining_agent_shadow = lambda: {"model": model, "deadline_s": 120.0}        # ★이 프로세스에서만 켠다
    runner = composition._dining_agent_shadow()
    assert runner is not None, "그림자 실행기를 만들지 못했다(키 · 설정)"
    made = []
    factory = runner.keywords["tools_factory"]

    def capture(connect):
        tools = factory(connect)
        made.append(tools)
        return tools
    runner.keywords["tools_factory"] = capture

    with get_connection() as conn:
        payload = review_module.load(conn, tenant, intake_id, 1)
        with conn.cursor() as cur:
            cur.execute("SELECT transcript FROM intake_sources WHERE tenant_id=%s AND intake_id=%s ORDER BY position",
                        (tenant, intake_id))
            notes = "\n".join(r[0] or "" for r in cur.fetchall())
    assert payload, "그 접수의 확인 결과가 없다"
    started = time.perf_counter()
    counts = runner(get_connection, tenant_id=tenant, intake_id=intake_id, revision=1, review=payload, notes=notes)
    seconds = round(time.perf_counter() - started, 1)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT run_id FROM dining.dn_agent_shadow WHERE intake_id=%s ORDER BY created_at DESC LIMIT 1", (intake_id,))
        run_id = cur.fetchone()[0]
        cur.execute("SELECT item_id, check_code, agent_verdict, rule_verdict, agree, failure, detail FROM dining.dn_agent_shadow "
                    "WHERE run_id=%s ORDER BY item_id, check_code", (run_id,))
        rows = [dict(zip(("item_id", "check", "agent", "rule", "agree", "failure", "detail"), r)) for r in cur.fetchall()]
    titles = {i["id"]: i.get("title") for i in payload.get("items") or []}
    for r in rows:
        r["title"] = titles.get(r["item_id"])
    calls = [c for t in made for c in t.calls]
    used = {}
    for c in calls:
        used[c.get("name")] = used.get(c.get("name"), 0) + 1
    out = {"intake_id": str(intake_id), "model": model, "seconds": seconds, "counts": counts, "tools_used": used,
           "adapters": {"kakao": made[0].kakao is not None if made else None, "google": made[0].google is not None if made else None},
           "rows": rows, "calls": calls,
           "config_unchanged": hashlib.sha256(config.read_bytes()).hexdigest() == before}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("model", "seconds", "counts", "tools_used", "adapters", "config_unchanged")},
                     ensure_ascii=False, indent=1, default=str))
    for r in rows:
        print(f"  {str(r['title'])[:14]:14} {r['check']:14} agent={r['agent']} rule={r['rule']} agree={r['agree']} {r['failure'] or ''}")
    print("report:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
