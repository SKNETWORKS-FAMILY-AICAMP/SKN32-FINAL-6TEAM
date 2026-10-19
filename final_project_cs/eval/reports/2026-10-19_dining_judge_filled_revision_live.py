# -*- coding: utf-8 -*-
"""채운 판(먼저 채우기가 만든 2판)에 요식 판정이 붙나 — 실제 원장 복사본 · 카카오 · OpenAI 읽기 · luna 판정. 등록하지 않는다. `[2026-10-19]`

읽기 모델은 이 PC 에 없어(Ollama) **모델 경로 `api`**(관리 콘솔 「모델 경로」와 같은 길, `ollama_chat._build` → `wrap_from_settings(api_first=True)`)로
OpenAI 가 읽는다. 키는 이 프로세스 환경에만 싣고 찍지 않는다. 서버의 읽기(학습 모델)와 읽은 결과는 다를 수 있다.

    python eval/reports/2026-10-19_dining_judge_filled_revision_live.py > eval/reports/2026-10-19_dining_judge_filled_revision_live.txt
"""
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # final_project_cs
MAIN = r"C:\Users\JSH\Desktop\SKN\SKN32-FINAL-6TEAM\final_project_cs"
for name in (".env", ".env.apikeys"):
    for line in open(os.path.join(MAIN, name), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["ACOP_DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/dining_judge_live"
os.environ["ACOP_MOBILITY_DATA_DIR"] = r"C:\Users\JSH\Desktop\SKN\SKN32-FINAL-6TEAM\datasets\mobility\processed"
os.environ["ACOP_MODEL_ROUTE_CHAT"] = "api"                                  # 읽기 · 채팅 모델을 OpenAI 먼저로
os.environ.setdefault("ACOP_OPENAI_API_KEY_SERVER", os.environ.get("ACOP_OPENAI_API_KEY", ""))   # 이 경로는 서버용 키만 읽는다 — 이 프로세스에만
if not os.environ.get("ACOP_OLLAMA_BASE_URL"):
    os.environ["ACOP_OLLAMA_BASE_URL"] = "http://127.0.0.1:9"                 # 비면 클라이언트를 안 만든다 — API 가 먼저라 부르지 않는다

for module in ("app.infrastructure.db.migrate", "scripts.register_prompts"):
    done = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise SystemExit(f"{module} 실패: {done.stdout[-500:]} {done.stderr[-1500:]}")

from starlette.testclient import TestClient  # noqa: E402

from app.infrastructure import llm_failover  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402
from app.presentation.api.app import create_app  # noqa: E402

CALLS = {"openai_structured": 0}
_structured = llm_failover.OpenAIChat.structured


def counted(self, *a, **k):
    CALLS["openai_structured"] += 1
    return _structured(self, *a, **k)


llm_failover.OpenAIChat.structured = counted

HEAD = "10월 24일 토요일 서울 여행, 2명.\n"
PLANS = {
    "N1_lunch": HEAD + "10:00 경복궁\n12:00 점심\n15:00 북촌한옥마을",
    "N2_market": HEAD + "10:00 창덕궁\n12:30 광장시장 근처 점심\n15:00 청계천",
    "N3_area": HEAD + "11:00 서울숲\n18:00 성수 근처 저녁\n20:00 뚝섬한강공원",
    "N4_myeongdong": HEAD + "10:00 남산서울타워\n12:00 명동 근처 점심\n16:00 남대문시장",
    "N5_named": HEAD + "10:00 광화문\n12:00 하동관 명동본점\n15:00 덕수궁",
}


def judged(intake_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT revision, check_code, item_id, agent_verdict, failure FROM dining.dn_agent_judge "
                    "WHERE intake_id = %s ORDER BY judge_id", (intake_id,))
        return [list(r) for r in cur.fetchall()]


def main():
    from app.domains.travel_ops.components.intake import pipeline

    client = TestClient(create_app())
    headers = {"X-User-Key": client.post("/v1/web/session").json()["user_key"]}
    out = {"reader_config": pipeline.agent_reader_config(os.environ.get("ACOP_TENANT_ID", "demo"))}
    for name, text in PLANS.items():
        started, before = time.monotonic(), CALLS["openai_structured"]
        resp = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
        if resp.status_code != 202:
            out[name] = {"submit": resp.status_code, "error": resp.text[:300]}
            continue
        intake = resp.json()["intake_id"]
        view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        for _ in range(90):                                     # 읽기 · 채우기 · 판정이 뒤에서 끝날 때까지
            rows = judged(intake)
            if view.get("status") not in ("reading",) and (rows or view.get("status") == "fatal"):
                break
            time.sleep(2)
            view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        items = (view.get("review") or {}).get("items") or []
        out[name] = {
            "status": view.get("status"), "revision": view.get("revision"), "fatal": view.get("fatal"),
            "seconds": round(time.monotonic() - started, 1), "openai_reads": CALLS["openai_structured"] - before,
            "prefill_filled": [[f.get("item"), f.get("owner")] for f in (view.get("prefill") or {}).get("filled") or []],
            "items": [[i.get("id"), i.get("kind"), i.get("title"), (i.get("place") or {}).get("name"), i.get("status")] for i in items],
            "dining_rows": [[i.get("id"), [[r.get("row"), r.get("result"), r.get("by"), r.get("text")] for r in i.get("rows") or []]]
                            for i in items if i.get("kind") == "dining"],
            "agent_judged": (view.get("review") or {}).get("agent_judged"),
            "judge_records": [[rev, code, item, verdict, failure] for rev, code, item, verdict, failure in judged(intake)],
        }
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
