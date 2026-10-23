# -*- coding: utf-8 -*-
"""실제 모델 · 실제 외부 API 로 접수 → 확인 화면 → 요식 판정 → 등록 한 바퀴 (DB 는 복사본 dining_llmcheck)."""
import json
import sys
import time

from starlette.testclient import TestClient

sys.stdout.reconfigure(encoding="utf-8")

from app.core import settings as settings_module  # noqa: E402
from app.core.settings import get_guardrails  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402
from app.presentation.api.app import create_app  # noqa: E402

PLANS = {
    "A_halal_required": "10월 24일 토요일 서울 하루 여행이에요. 일행 2명, 무슬림이라 할랄 음식만 먹을 수 있어요(꼭 지켜야 해요).\n"
                        "10:00 남산서울타워\n12:00 할랄부산집 점심\n18:00 명동교자 본점 저녁",
    "B_plain": "10월 24일 토요일 서울 하루 여행이에요. 2명.\n10:00 경복궁\n12:30 명동교자 본점 점심\n15:00 남대문시장 구경",
}


def dining_rows(view):
    out = []
    for item in (view.get("review") or {}).get("items") or []:
        if item.get("kind") != "dining":
            continue
        rows = [{k: r.get(k) for k in ("row", "result", "text", "by", "requirement", "blocks_registration") if r.get(k) is not None}
                for r in item.get("rows") or []]
        out.append({"title": item.get("title"), "status": item.get("status"), "rows": rows})
    return out


def main():
    print("LLM provider:", settings_module.get_settings().llm_provider,
          "| judge:", get_guardrails().get("travel.dining.agent_judge.model"))
    client = TestClient(create_app())
    headers = {"X-User-Key": client.post("/v1/web/session").json()["user_key"]}
    result = {}
    for name, text in PLANS.items():
        t0 = time.perf_counter()
        resp = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
        step = {"submit": resp.status_code}
        if resp.status_code != 202:
            step["error"] = resp.text[:800]
            result[name] = step
            continue
        intake = resp.json()["intake_id"]
        view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        for _ in range(60):                                   # 판정이 끝날 때까지(뒤 작업) 다시 읽는다
            meta = (view.get("review") or {}).get("dining_judge") or {}
            if view.get("status") != "reading" and meta.get("status") not in ("queued", "running", "pending"):
                break
            time.sleep(2)
            view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        step.update({"seconds_to_review": round(time.perf_counter() - t0, 1), "status": view.get("status"),
                     "revision": view.get("revision"),
                     "dining_judge": (view.get("review") or {}).get("dining_judge"),
                     "agent_judged": (view.get("review") or {}).get("agent_judged"),
                     "ready": (view.get("review") or {}).get("ready"),
                     "items": [(i.get("kind"), i.get("title"), i.get("status")) for i in (view.get("review") or {}).get("items") or []],
                     "dining": dining_rows(view)})
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT item_id, check_code, agent_verdict, rule_verdict, agree, failure, model FROM dining.dn_agent_judge "
                        "WHERE intake_id=%s ORDER BY judge_id", (intake,))
            step["judge_records"] = [list(map(str, r)) for r in cur.fetchall()]
        confirm = client.post(f"/v1/web/trip-intakes/{intake}/confirm", headers=headers,
                              json={"revision": view.get("revision")})
        step["confirm"] = confirm.status_code
        body = confirm.json()
        step["confirm_body"] = {k: body.get(k) for k in ("status", "error", "code", "message", "detail") if k in body} \
            if confirm.status_code != 200 else {"status": body.get("status"), "trip_id": (body.get("trip") or {}).get("trip_id")}
        step["total_seconds"] = round(time.perf_counter() - t0, 1)
        result[name] = step
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
