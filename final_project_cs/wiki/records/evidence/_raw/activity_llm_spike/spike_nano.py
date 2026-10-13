"""1단계 스파이크 — gpt-5.4-nano + web_search 실측 (액티비티 LLM 연동 계획서 §3)."""
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path("/Users/imac/Documents/SKN32-FINAL-6TEAM/final_project_cs")


def load_key() -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("ACOP_OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("key missing")


from openai import OpenAI  # noqa: E402

print("openai sdk", __import__("openai").__version__)
client = OpenAI(api_key=load_key(), timeout=60)
MODEL = "gpt-5.4-nano"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["open", "closed", "unknown"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"url": {"type": "string"}, "quote": {"type": "string"},
                               "published_at": {"type": ["string", "null"]}},
                "required": ["url", "quote", "published_at"],
            },
        },
    },
    "required": ["verdict", "confidence", "reason", "citations"],
}
FMT = {"format": {"type": "json_schema", "name": "live_status", "schema": SCHEMA, "strict": True}}
PROMPT = ("오늘은 2026-10-06이다. 장소 '경복궁'(서울 종로구)이 2026-10-07(수) 14:00에 관람 가능한지 "
          "임시휴무·행사·공사 공지를 웹에서 확인해 판정하라. 근거가 없으면 verdict=unknown. "
          "citations 에는 실제로 본 페이지 URL만 넣는다.")


def summarize(resp, started):
    items = [getattr(o, "type", "?") for o in resp.output]
    cites = []
    for o in resp.output:
        if getattr(o, "type", "") == "message":
            for c in o.content:
                for a in getattr(c, "annotations", None) or []:
                    if getattr(a, "type", "") == "url_citation":
                        cites.append(a.url)
    u = resp.usage
    return {
        "latency_s": round(time.monotonic() - started, 2),
        "output_items": items,
        "web_search_calls": items.count("web_search_call"),
        "url_citation_annotations": len(cites),
        "input_tokens": getattr(u, "input_tokens", None),
        "output_tokens": getattr(u, "output_tokens", None),
        "reasoning_tokens": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", None),
        "text_head": (resp.output_text or "")[:300],
    }


def attempt(label, **kwargs):
    started = time.monotonic()
    try:
        resp = client.responses.create(model=MODEL, **kwargs)
        out = {"ok": True, **summarize(resp, started)}
    except Exception as exc:  # 실측이므로 오류 원문을 그대로 남긴다
        out = {"ok": False, "latency_s": round(time.monotonic() - started, 2),
               "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
    print(f"\n### {label}\n" + json.dumps(out, ensure_ascii=False, indent=2))
    sys.stdout.flush()
    return out


# Q1 temperature / seed
attempt("Q1a temperature=0 (effort none)", input="1+1은? 숫자만.", temperature=0,
        reasoning={"effort": "none"})
attempt("Q1b temperature=0 (effort low)", input="1+1은? 숫자만.", temperature=0,
        reasoning={"effort": "low"})
attempt("Q1c seed=7 (extra_body)", input="1+1은? 숫자만.", extra_body={"seed": 7},
        reasoning={"effort": "none"})

# Q2 web_search 와 effort
attempt("Q2a web_search + effort none + json_schema", input=PROMPT, tools=[{"type": "web_search"}],
        reasoning={"effort": "none"}, text=FMT)
attempt("Q2b web_search + effort low + json_schema", input=PROMPT, tools=[{"type": "web_search"}],
        reasoning={"effort": "low"}, text=FMT)
attempt("Q2c web_search + effort none, no schema", input=PROMPT, tools=[{"type": "web_search"}],
        reasoning={"effort": "none"})

# Q4 지연 — 같은 요청 5회 (effort low + web_search + schema)
lat = []
for i in range(5):
    r = attempt(f"Q4 run {i + 1}", input=PROMPT, tools=[{"type": "web_search"}],
                reasoning={"effort": "low"}, text=FMT)
    if r["ok"]:
        lat.append(r["latency_s"])
if lat:
    lat.sort()
    print("\n### Q4 latency summary", json.dumps({
        "n": len(lat), "values": lat, "p50": statistics.median(lat), "max(≈p95 at n=5)": lat[-1]}))
