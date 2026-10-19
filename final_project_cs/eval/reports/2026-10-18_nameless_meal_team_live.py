# -*- coding: utf-8 -*-
"""가게 이름 없는 식사 — 고친 판(worktree)으로 실제 원장 · 카카오 · 모델을 붙여 접수 → 후보 → 자동 추천 미리보기. 등록하지 않는다."""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
MAIN = r"C:\Users\JSH\Desktop\SKN\SKN32-FINAL-6TEAM\final_project_cs"
for name in (".env", ".env.apikeys"):                      # 값은 찍지 않는다 — 이 프로세스 환경에만 싣는다
    for line in open(os.path.join(MAIN, name), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
os.environ["ACOP_DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/dining_nm_live"
os.environ["ACOP_GUARDRAILS_PATH"] = os.environ.get("NAMELESS_GUARDRAILS", "config/guardrails.yaml")   # 읽기 모델 없이 점검하려면 intake_reader.mode 를 off 로 둔 사본
os.environ["ACOP_MOBILITY_DATA_DIR"] = r"C:\Users\JSH\Desktop\SKN\SKN32-FINAL-6TEAM\datasets\mobility\processed"

import subprocess  # noqa: E402

for module in ("app.infrastructure.db.migrate", "scripts.register_prompts"):   # 고친 판의 마이그레이션 · 프롬프트를 복사본 DB 에 올린다
    done = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise SystemExit(f"{module} 실패: {done.stdout[-500:]} {done.stderr[-1500:]}")

from starlette.testclient import TestClient  # noqa: E402

from app.presentation.api.app import create_app  # noqa: E402

HEAD = "10월 24일 토요일 서울 여행, 2명.\n"
PLANS = {
    "N1_lunch": HEAD + "10:00 경복궁\n12:00 점심\n15:00 북촌한옥마을",
    "N2_market": HEAD + "10:00 창덕궁\n12:30 광장시장 근처 점심\n15:00 청계천",
    "N3_area": HEAD + "11:00 서울숲\n18:00 성수 근처 저녁\n20:00 뚝섬한강공원",
    "N4_myeongdong": HEAD + "10:00 남산서울타워\n12:00 명동 근처 점심\n16:00 남대문시장",
    "N5_boramae": HEAD + "10:00 서울대공원\n12:30 보라매공원 근처 점심\n16:00 여의도 한강공원",
}


def main():
    client = TestClient(create_app())
    headers = {"X-User-Key": client.post("/v1/web/session").json()["user_key"]}
    out = {}
    for name, text in PLANS.items():
        resp = client.post("/v1/web/trip-intakes", headers=headers, data={"text": text})
        if resp.status_code != 202:
            out[name] = {"submit": resp.status_code, "error": resp.text[:300]}
            continue
        intake = resp.json()["intake_id"]
        view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        for _ in range(30):
            if view.get("status") != "reading":
                break
            time.sleep(2)
            view = client.get(f"/v1/web/trip-intakes/{intake}", headers=headers).json()
        items = (view.get("review") or {}).get("items") or []
        meals = []
        for it in items:
            if it.get("kind") != "dining":
                continue
            cand = client.get(f"/v1/web/trip-intakes/{intake}/candidates", headers=headers,
                              params={"source_id": it["source_id"], "index": it["index"], "revision": view["revision"]}).json()
            meals.append({"title": it.get("title"), "status": it.get("status"), "place_state": it.get("place_state"),
                          "place": (it.get("place") or {}).get("name"),
                          "place_row": next(([r["result"], r["text"]] for r in it.get("rows") or [] if r["row"] == "place"), None),
                          "notes": cand.get("notes"),
                          "candidates": [[c["place"]["name"], c["place"].get("source"), c["place"].get("category"), c.get("status")]
                                         for c in cand.get("candidates") or []]})
        dry = client.post(f"/v1/web/trip-intakes/{intake}/autofix", headers=headers, json={"revision": view["revision"], "dry_run": True})
        preview = dry.json() if dry.status_code == 200 else {"error": dry.status_code, "body": dry.text[:200]}
        changes = [[c.get("title"), (c.get("to") or {}).get("place", {}).get("name") if isinstance((c.get("to") or {}).get("place"), dict) else None,
                    c.get("reason")] for c in (preview.get("changed") or [])]
        kept = [[k.get("title"), k.get("reason")] for k in (preview.get("kept") or [])]
        out[name] = {"status": view.get("status"), "items": [[i.get("kind"), i.get("title"), i.get("starts_at")] for i in items],
                     "meals": meals, "autofix_preview": {"changes": changes, "kept": kept}}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
