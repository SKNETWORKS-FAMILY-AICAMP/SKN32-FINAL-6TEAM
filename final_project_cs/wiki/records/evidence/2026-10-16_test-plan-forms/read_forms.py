# 새 준비 계획(test17~)을 지금 구조 read_source 로 읽어 본다(2026-10-16 보고서 근거). final_project_cs 에서: python <이 파일> <out.jsonl> [--ollama <x600 과 같은 구성의 Ollama 주소>]
import json, os, sys, time
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.getcwd())
from eval.intake_diverse.run_current import _DUMMY_ENV, adapt, TimedChat
for k, v in _DUMMY_ENV.items():
    os.environ.setdefault(k, v)

from app.domains.travel_ops.components.intake import test_plans as plans
from app.domains.travel_ops.components.intake.pipeline import read_source

out = sys.argv[1]
ollama = sys.argv[sys.argv.index("--ollama") + 1] if "--ollama" in sys.argv else ""
chat = None
if ollama:
    from app.infrastructure.ollama_chat import OllamaChat
    chat = TimedChat(OllamaChat(base_url=ollama, model="tripilot-pointer:e4b-ft", timeout=120.0, keep_alive="30m", num_ctx=8192))
today = date(2026, 10, 16)
now = datetime(2026, 10, 16, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
with open(out, "w", encoding="utf-8") as f:
    for n in range(len(plans.PLANS) + 1, plans.TOTAL + 1):
        p = plans.prepared(n, today)
        calls = chat.calls if chat else 0
        t = time.perf_counter()
        err, rows = None, []
        try:
            rows = read_source(p["text"], chat=chat, tour=None, kakao=None, our_places=[], today=today, now=now)
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"[:300]
        a = adapt(rows)
        rec = {"code": p["code"], "category": p["category"], "name": p["name"], "seconds": round(time.perf_counter() - t, 2),
               "model_calls": (chat.calls - calls) if chat else 0, "error": err,
               "items": [{k: i.get(k) for k in ("title", "date", "start", "end", "kind")} for i in a["items"]],
               "trip": a["trip"], "requests": a["requests"], "missing": a["missing"],
               "fields": sorted({r.get("field") for r in rows if not str(r.get("field", "")).startswith("items[")})}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(p["code"], p["category"], len(rec["items"]), "항목", rec["seconds"], "s", "모델", rec["model_calls"], err or "")
