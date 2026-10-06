"""스파이크 보강 — json_schema 응답의 citations[].url 을 web_search_call.action.sources 와 대조할 수 있나."""
import json, sys, time
sys.path.insert(0, "/private/tmp/claude-501/-Users-imac-Documents-SKN32-FINAL-6TEAM/cd867cd7-1d24-4c89-9768-3cf40884bead/scratchpad")
import importlib.util
spec = importlib.util.spec_from_file_location("s", sys.path[0] + "/spike_nano.py")
src = open(sys.path[0] + "/spike_nano.py", encoding="utf-8").read().split("# Q1 temperature")[0]
ns = {}; exec(src, ns)
client, PROMPT, FMT = ns["client"], ns["PROMPT"], ns["FMT"]
from urllib.parse import urlsplit
def norm(u): p = urlsplit(u); return (p.netloc.replace("www.", ""), p.path.rstrip("/"))
for i in range(3):
    t = time.monotonic()
    r = client.responses.create(model="gpt-5.4-nano", input=PROMPT, tools=[{"type": "web_search"}],
                                reasoning={"effort": "low"}, text=FMT,
                                include=["web_search_call.action.sources"])
    sources = []
    actions = []
    for o in r.output:
        if o.type == "web_search_call":
            a = o.action
            actions.append(getattr(a, "type", None))
            for s in getattr(a, "sources", None) or []:
                sources.append(getattr(s, "url", None))
    body = json.loads(r.output_text)
    cited = [c["url"] for c in body["citations"]]
    src_norm = {norm(u) for u in sources if u}
    print(json.dumps({
        "run": i + 1, "latency_s": round(time.monotonic() - t, 2), "verdict": body["verdict"],
        "action_types": actions, "n_sources": len(sources), "sources_head": sources[:5],
        "cited": cited,
        "cited_in_sources_exact": [u in sources for u in cited],
        "cited_in_sources_host_path": [norm(u) in src_norm for u in cited],
        "published_at": [c["published_at"] for c in body["citations"]],
    }, ensure_ascii=False, indent=2)); sys.stdout.flush()
