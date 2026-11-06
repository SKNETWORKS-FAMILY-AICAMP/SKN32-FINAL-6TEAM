"""날짜 읽기 실측 — 합성 표본을 실제 로컬 E4B 로 `pipeline.read_source(agent_mode="on")` 에 넣고 최종 items[i].date 를 채점한다.

    python -B measure_dates.py --source-root <final_project_cs> --live-launch <launch-serving.py> --label before|after --out <dir>

- 모델 주소 · 이름 · num_ctx 는 하드코딩하지 않는다: 지금 로컬 서빙(`--live-launch`)이 넣는 ACOP_OLLAMA_* 값을 읽어 Settings 로 넘기고,
  제품과 같은 `ollama_chat._build(settings, "local")` 로 클라이언트를 만든다(넘김 장치 꺼짐 = 유료 경로 없음).
- 네트워크: 그 Ollama host:port 연결만 허용, 나머지 socket · psycopg 는 차단.
- 유휴 확인: 행마다 서빙의 policy-counters(chat_admitted == chat_completed)를 본다. 사용 중이면 최대 20분 기다리고 그래도면 not_run_paused.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import socket
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ap = argparse.ArgumentParser()
ap.add_argument("--source-root", required=True)
ap.add_argument("--live-launch", required=True)
ap.add_argument("--samples", default=str(Path(__file__).with_name("samples.json")))
ap.add_argument("--label", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--only", default="")
args = ap.parse_args()
args.out = str(Path(args.out).resolve())
args.samples = str(Path(args.samples).resolve())

launch = Path(args.live_launch)
env_from_launch: dict[str, str] = {}
for node in ast.walk(ast.parse(launch.read_text(encoding="utf-8"))):
    if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "update" and node.args and isinstance(node.args[0], ast.Dict):
        try:
            value = ast.literal_eval(node.args[0])
        except ValueError:
            continue
        env_from_launch.update({k: v for k, v in value.items() if k.startswith("ACOP_OLLAMA_") or k == "ACOP_LLM_FAILOVER_ENABLED"})
need = ("ACOP_OLLAMA_BASE_URL", "ACOP_OLLAMA_MODEL", "ACOP_OLLAMA_NUM_CTX")
missing = [k for k in need if not env_from_launch.get(k)]
if missing:
    raise SystemExit(f"live launch has no {missing} — refusing to guess")
counters = launch.with_name("policy-counters.json")

os.environ.update({
    "ACOP_DATABASE_URL": "postgresql://unit:***@127.0.0.1:1/unit", "ACOP_OPENAI_API_KEY": "unit-placeholder", "ACOP_LLM_MODEL": "unit-placeholder",
    "ACOP_EMBEDDING_MODEL": "unit-placeholder", "ACOP_TENANT_ID": "demo", "ACOP_SECRET_KEY": "unit-placeholder-secret-0123456789abcdef",
    "ACOP_COMPOSER_JWT_SECRET": "unit-placeholder-composer-0123456789abcdef", "ACOP_COMPOSER_ISSUER_SECRET": "unit-placeholder-issuer-0123456789abcdef",
    "PYTHONDONTWRITEBYTECODE": "1"})
os.environ.update({k: env_from_launch[k] for k in env_from_launch if k in need or k == "ACOP_LLM_FAILOVER_ENABLED"})
os.environ["ACOP_LLM_FAILOVER_ENABLED"] = "false"
base = urlparse(env_from_launch["ACOP_OLLAMA_BASE_URL"])
allowed = {(base.hostname, base.port)}

_orig_connect = socket.socket.connect


def _guard_connect(self, address, *a, **kw):
    import inspect
    if inspect.currentframe().f_back.f_code is socket._fallback_socketpair.__code__:
        return _orig_connect(self, address, *a, **kw)
    if isinstance(address, tuple) and (address[0], address[1]) in allowed:
        return _orig_connect(self, address, *a, **kw)
    raise RuntimeError(f"measure runner: connect denied {address!r}")


socket.socket.connect = _guard_connect
_orig_cc = socket.create_connection


def _guard_cc(address, *a, **kw):
    if (address[0], address[1]) in allowed:
        return _orig_cc(address, *a, **kw)
    raise RuntimeError(f"measure runner: create_connection denied {address!r}")


socket.create_connection = _guard_cc
root = Path(args.source_root)
os.chdir(root)
sys.path.insert(0, str(root))
import psycopg  # noqa: E402

psycopg.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("measure runner: database denied"))

from app.core.settings import Settings  # noqa: E402
from app.infrastructure import ollama_chat  # noqa: E402
from app.domains.travel_ops.components.intake import agent_read, pipeline  # noqa: E402

settings = Settings()
chat = ollama_chat._build(settings, "local")
print(json.dumps({"root": str(root), "model": chat.model, "base_url": chat.base_url, "num_ctx": chat.num_ctx,
                  "schema_has_date_form": "date_form" in json.dumps(agent_read.SCHEMA)}, ensure_ascii=False), flush=True)


class Recording:
    def __init__(self, inner):
        self.inner, self.raw = inner, []

    @property
    def model(self):
        return self.inner.model

    def structured(self, system, user, schema, *, num_predict=160):
        value = self.inner.structured(system, user, schema, num_predict=num_predict)
        self.raw.append(value)
        return value

    def structured_stream(self, system, user, schema, **kw):
        value = self.inner.structured_stream(system, user, schema, **kw)
        self.raw.append(value)
        return value


def idle() -> bool:
    if not counters.exists():
        return True
    c = json.loads(counters.read_text(encoding="utf-8"))
    return c.get("chat_admitted", 0) == c.get("chat_completed", 0)


data = json.loads(Path(args.samples).read_text(encoding="utf-8"))
today = date.fromisoformat(data["today"])
only = set(filter(None, args.only.split(",")))
out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)
result_path = out_dir / f"{args.label}.jsonl"
results = []
with result_path.open("w", encoding="utf-8") as fh:
    for s in data["samples"]:
        if only and s["id"] not in only:
            continue
        waited = 0
        while not idle() and waited < 1200:
            time.sleep(30)
            waited += 30
        if not idle():
            row = {"id": s["id"], "status": "not_run_paused"}
        else:
            rec = Recording(chat)
            started = time.perf_counter()
            try:
                rows = pipeline.read_source(s["text"], today=today, agent=rec, agent_mode="on", position=0)
                dates = {}
                for r in rows:
                    f = r["field"]
                    if f.startswith("items[") and f.endswith(".date"):
                        dates[int(f[6:f.index("]")])] = {"value": r["value"], "how": (r.get("evidence") or {}).get("how"),
                                                         "method": r.get("method"), "needs_review": r.get("needs_review")}
                got = [dates[k]["value"] for k in sorted(dates)]
                raw_items = [{k: it.get(k) for k in ("place_quote", "date", "date_quote", "date_form", "year_quote")}
                             for raw in rec.raw for it in (raw.get("items") or []) if isinstance(it, dict)]
                row = {"id": s["id"], "group": s["group"], "text": s["text"], "expect": s["expect"], "got": got,
                       "ok": got == s["expect"], "dates": [dates[k] for k in sorted(dates)], "raw_items": raw_items,
                       "seconds": round(time.perf_counter() - started, 2), "status": "ran"}
            except Exception as exc:  # noqa: BLE001 — 실패도 행으로 남긴다(분모에서 빼지 않는다)
                row = {"id": s["id"], "group": s["group"], "text": s["text"], "expect": s["expect"], "got": None, "ok": False,
                       "status": "error", "error": f"{type(exc).__name__}: {exc}", "raw_items": None}
        results.append(row)
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        print(row["id"], row.get("status"), row.get("ok"), row.get("got"), flush=True)
ran = [r for r in results if r.get("status") != "not_run_paused"]
ok = sum(1 for r in ran if r.get("ok"))
summary = {"label": args.label, "ok": ok, "ran": len(ran), "total": len(results),
           "pct": round(100 * ok / len(ran), 1) if ran else None,
           "errors": sum(1 for r in ran if r.get("status") == "error")}
(out_dir / f"{args.label}.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
