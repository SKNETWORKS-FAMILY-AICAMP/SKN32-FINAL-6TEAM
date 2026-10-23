# -*- coding: utf-8 -*-
"""경로 후보(먼저 3개 · 더 보기 · 고르기) 실서버 확인 — 표준 라이브러리만 쓴다.

    python3 live_route_check.py --base http://127.0.0.1:<api 포트> [--key <웹 사용자 키>] [--out result.json]

하는 일(읽기 + 시험 접수 1건): 웹 세션 키를 받거나(--key 가 없으면 POST /v1/web/session) → 시험 계획서로 접수 1건 →
확인 결과가 나올 때까지 기다림 → 구간마다 routes(앞 3개) 크기 · 수 → routes_more 인 구간마다 GET …/routes 2쪽(시간 잼) →
다른 경로 하나 고르기(POST …/route) → 반영 확인 → 추천으로 되돌리기. 여행 등록은 하지 않는다(접수만 남는다 — 게스트 자료 7일 자동 정리).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PLAN = ("2026-11-05\n"
        "10시 경복궁 관람 1시간 반\n"
        "13시 홍대입구역 걷기 1시간\n"
        "15시 30분 롯데월드타워 전망대 1시간\n"
        "18시 종각 저녁")


def call(base, method, path, headers=None, body=None, form=None, timeout=120):
    data, h = None, dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=h, method=method)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, json.loads(raw or b"null"), time.perf_counter() - t, len(raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"null"), time.perf_counter() - t, len(raw)
        except ValueError:
            return e.code, raw.decode("utf-8", "replace")[:500], time.perf_counter() - t, len(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--key")
    ap.add_argument("--out", default="live_route_check.json")
    ap.add_argument("--wait", type=int, default=420)
    a = ap.parse_args()
    out = {"base_is_local": a.base.startswith("http://127.0.0.1") or a.base.startswith("http://localhost"), "steps": []}

    def step(name, **kw):
        out["steps"].append({"step": name, **kw})
        print(name, json.dumps(kw, ensure_ascii=False)[:600], flush=True)

    key = a.key
    if not key:
        s, body, dt, _ = call(a.base, "POST", "/v1/web/session", body={})
        step("session", status=s, sec=round(dt, 2))
        if s != 201:
            step("stop", why="세션 키를 못 받음 — --key 로 시험 키를 주세요", body=body)
            return finish(out, a.out)
        key = body["user_key"]
    H = {"X-User-Key": key}
    s, body, dt, _ = call(a.base, "POST", "/v1/web/trip-intakes", H, form={"text": PLAN})
    step("intake_submit", status=s, sec=round(dt, 2))
    if s != 202:
        step("stop", body=body)
        return finish(out, a.out)
    iid = body["intake_id"]
    out["intake_id"] = iid
    t0, view = time.perf_counter(), None
    while time.perf_counter() - t0 < a.wait:
        s, view, _, _ = call(a.base, "GET", f"/v1/web/trip-intakes/{iid}", H)
        if s == 200 and view.get("status") in ("review", "confirmed") and view.get("review"):
            break
        time.sleep(3)
    rv = (view or {}).get("review") or {}
    step("review_ready", status=view.get("status") if view else None, wait_sec=round(time.perf_counter() - t0, 1),
         revision=rv.get("revision"), moves=len(rv.get("moves") or []), engine=rv.get("engine"))
    if not rv:
        return finish(out, a.out)
    revision = rv["revision"]
    moves = rv.get("moves") or []
    for m in moves:
        routes = m.get("routes")
        step("move", pair=f"{m['from']}~{m['to']}", mode=m.get("mode"), basis=m.get("basis"), depart=m.get("depart"),
             arrive=m.get("arrive"), has_routes_field=routes is not None, n_first=len(routes or []),
             routes_total=m.get("routes_total"), routes_more=m.get("routes_more"), route_key=m.get("route_key"),
             first_bytes=len(json.dumps(routes or [], ensure_ascii=False).encode()),
             first=[(r.get("lines"), r.get("minutes"), r.get("depart"), r.get("arrive"), r.get("early"), r.get("planned")) for r in routes or []])
    pick = None
    for m in moves:
        if m.get("basis") != "timetable":
            continue
        pair = f"{m['from']}~{m['to']}"
        shown = list(m.get("routes") or [])
        offset = len(shown)
        for page in (1, 2):
            if not m.get("routes_more") and page == 1:
                break
            s, body, dt, size = call(a.base, "GET", f"/v1/web/trip-intakes/{iid}/moves/{urllib.parse.quote(pair)}/routes?revision={revision}&offset={offset}&limit=5", H)
            got = (body or {}).get("routes") or [] if isinstance(body, dict) else []
            step("more", pair=pair, page=page, status=s, sec=round(dt, 2), bytes=size, n=len(got), offset=offset,
                 has_more=(body or {}).get("has_more") if isinstance(body, dict) else None, total=(body or {}).get("total") if isinstance(body, dict) else None,
                 why=(body or {}).get("why") if isinstance(body, dict) else body,
                 routes=[(r.get("lines"), r.get("minutes"), r.get("depart"), r.get("arrive"), r.get("early"), r.get("slack_min")) for r in got])
            shown += got
            offset += len(got)
            if s != 200 or not (body or {}).get("has_more"):
                break
        if pick is None:
            alt = next((r for r in shown if r.get("key") != m.get("route_key") and (r.get("slack_min") or 0) >= 0), None)
            if alt is not None:
                pick = (pair, alt, m.get("route_key"))
    if pick:
        pair, alt, before = pick
        s, body, dt, _ = call(a.base, "POST", f"/v1/web/trip-intakes/{iid}/moves/{urllib.parse.quote(pair)}/route", H,
                              body={"revision": revision, "key": alt["key"]})
        after = next((m for m in ((body or {}).get("review") or {}).get("moves") or [] if f"{m['from']}~{m['to']}" == pair), {}) if isinstance(body, dict) else {}
        step("choose", pair=pair, status=s, sec=round(dt, 2), key=alt["key"], early=alt.get("early"),
             new_revision=(body or {}).get("revision") if isinstance(body, dict) else None,
             route_key_after=after.get("route_key"), route_choice=after.get("route_choice"), depart=after.get("depart"),
             arrive=after.get("arrive"), minutes=after.get("minutes"), mode_label=after.get("mode_label"),
             first_after=[r.get("key") for r in after.get("routes") or []], error=None if s == 200 else body)
        if s == 200:
            s2, body2, dt2, _ = call(a.base, "POST", f"/v1/web/trip-intakes/{iid}/moves/{urllib.parse.quote(pair)}/route", H,
                                     body={"revision": body["revision"], "key": "recommended"})
            back = next((m for m in ((body2 or {}).get("review") or {}).get("moves") or [] if f"{m['from']}~{m['to']}" == pair), {}) if isinstance(body2, dict) else {}
            step("undo", status=s2, sec=round(dt2, 2), route_key_after=back.get("route_key"), same_as_before=back.get("route_key") == before,
                 route_choice=back.get("route_choice"))
        s3, body3, dt3, _ = call(a.base, "POST", f"/v1/web/trip-intakes/{iid}/moves/{urllib.parse.quote(pair)}/route", H,
                                 body={"revision": 1, "key": alt["key"]})
        step("stale_revision_refused", status=s3, code=(body3 or {}).get("code") if isinstance(body3, dict) else None)
    else:
        step("choose", skipped="다른 경로가 있는 구간이 없음")
    return finish(out, a.out)


def finish(out, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", path)


if __name__ == "__main__":
    sys.exit(main())
