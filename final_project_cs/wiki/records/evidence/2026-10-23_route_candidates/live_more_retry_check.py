# -*- coding: utf-8 -*-
"""배포 직후 첫 「더 보기」 — 화면이 하는 것(빈 쪽 + 「오래 걸려」면 3초 뒤 한 번 다시)을 그대로 따라 해 실서버에서 잰다. 표준 라이브러리만.

    python3 live_more_retry_check.py --base http://127.0.0.1:<api 포트> [--key <웹 사용자 키>] [--out result.json]

배포로 cs 프로젝트 서버가 막 다시 뜬 뒤(계산기가 차가울 때) 돌려야 뜻이 있다. 시험 접수 1건만 만든다(여행 등록 없음).
"""
import argparse
import json
import time
import urllib.parse

from live_route_check import PLAN, call

RETRY_S = 3.0          # 화면 `ROUTES_RETRY_MS` 와 같다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--key")
    ap.add_argument("--out", default="live_more_retry_check.json")
    a = ap.parse_args()
    steps = []

    def step(name, **kw):
        steps.append({"step": name, **kw})
        print(name, json.dumps(kw, ensure_ascii=False)[:500], flush=True)

    key = a.key
    if not key:
        s, body, dt, _ = call(a.base, "POST", "/v1/web/session", body={})
        step("session", status=s)
        key = body["user_key"]
    H = {"X-User-Key": key}
    s, body, dt, _ = call(a.base, "POST", "/v1/web/trip-intakes", H, form={"text": PLAN})
    iid = body["intake_id"]
    t0, view = time.perf_counter(), None
    while time.perf_counter() - t0 < 420:
        s, view, _, _ = call(a.base, "GET", f"/v1/web/trip-intakes/{iid}", H)
        if s == 200 and view.get("review"):
            break
        time.sleep(3)
    rv = view["review"]
    step("review_ready", wait_sec=round(time.perf_counter() - t0, 1), revision=rv["revision"], moves=len(rv["moves"]))
    for m in rv["moves"]:
        if m.get("basis") != "timetable" or not m.get("routes_more"):
            continue
        pair = urllib.parse.quote(f"{m['from']}~{m['to']}")
        offset = len(m.get("routes") or [])
        start = time.perf_counter()
        tries = []
        for n in (1, 2):
            s, body, dt, _ = call(a.base, "GET", f"/v1/web/trip-intakes/{iid}/moves/{pair}/routes?revision={rv['revision']}&offset={offset}&limit=5", H)
            got = body.get("routes") or [] if isinstance(body, dict) else []
            tries.append({"try": n, "status": s, "sec": round(dt, 2), "n": len(got), "why": body.get("why") if isinstance(body, dict) else body,
                          "has_more": body.get("has_more") if isinstance(body, dict) else None})
            if n == 1 and s == 200 and not got and body.get("why") and body.get("has_more"):
                time.sleep(RETRY_S)
                continue
            break
        step("more", pair=f"{m['from']}~{m['to']}", tries=tries, customer_wait_sec=round(time.perf_counter() - start, 2),
             shown=tries[-1]["n"], retried=len(tries) == 2)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"intake_id": iid, "steps": steps}, f, ensure_ascii=False, indent=1)
    print("saved", a.out)


if __name__ == "__main__":
    main()
