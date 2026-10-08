# -*- coding: utf-8 -*-
"""지하철 요금 독립 대조(#21) — 우리 계산(공표 거리 → 없으면 선로 길이 추정) vs ODsay 대중교통 길찾기의 요금(payment) (2026-10-04).

실행(final_project_cs 에서 · 키는 .env.apikeys 의 ACOP_ODSAY_API_KEY — 값은 출력하지 않는다 · 쌍당 호출 1회):
  python scripts/mobility/validate_fare_vs_odsay.py [쌍 수]
★ODsay 키는 「URI」 플랫폼이면 등록한 웹 주소를 Referer 로 보내야 통과한다 — 환경변수 ODSAY_REFERER 로 준다(문서·커밋에 적지 않는다).
ODsay 응답은 요금·노선 숫자만 쓰고 파일로 저장하지 않는다. ODsay 값도 독립 **참고값**이다(정답 아님).
"""
import json, os, random, re, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, ".")
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine import options as O

ENV = {}
for f in (Path(".env.apikeys"), Path(".env")):
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$", l)
            if m and m.group(2): ENV.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
KEY = ENV["ACOP_ODSAY_API_KEY"]
REF = os.environ.get("ODSAY_REFERER") or ENV.get("ODSAY_REFERER", "")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
EST_LINES = ["09호선", "경의선", "수인분당선", "경춘선", "서해선"]
CONTROL_LINES = ["01호선", "02호선", "03호선", "04호선", "05호선", "06호선", "07호선", "08호선"]
LINE_DIGIT = {"09호선": "9", "경의선": "경의", "수인분당선": "수인", "경춘선": "경춘", "서해선": "서해"}


def odsay(a, b):
    q = urllib.parse.urlencode({"SX": a[1], "SY": a[0], "EX": b[1], "EY": b[0], "apiKey": KEY, "OPT": "0"})
    req = urllib.request.Request("https://api.odsay.com/v1/api/searchPubTransPathT?" + q, headers={"Referer": REF, "Origin": REF} if REF else {})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as ex:                                     # noqa: BLE001
        return {"error": [{"message": type(ex).__name__}]}


def lane_matches(lane_name, line):
    d = LINE_DIGIT.get(line) or str(int(line[:2]))
    return d in (lane_name or "")


def our_fare(v, line, a_nm, b_nm):
    legs = [{"line": line, "from": a_nm, "to": b_nm}]
    F = O._fare(v)
    for net, est in ((O.fare_net(v), False), (O.fare_net_est(v), True)):
        if net is None:
            continue
        ub = net.upper_m(legs)
        if ub is None:
            continue
        lb = min(net.lower_m(legs) or 0, ub)
        f1, f2 = O.subway_fare_at(F, lb, 720), O.subway_fare_at(F, ub, 720)
        if f1 == f2:
            return f2, est
    return None, False


def main():
    rt = build_verifier(quiet=True)
    v = rt._v
    rng = random.Random(21)
    jobs = []
    for line, n in [(l, max(2, N // (len(EST_LINES) * 2))) for l in EST_LINES] + [(l, max(1, N // (len(CONTROL_LINES) * 2))) for l in CONTROL_LINES]:
        names = v.lo.stations(line)
        for _ in range(n):
            a, b = rng.sample(names, 2)
            jobs.append((line, a, b))
    rows = []
    for line, a, b in jobs:
        pa, pb = v.sc.get(line, a), v.sc.get(line, b)
        if not pa or not pb or pa.get("lat") is None or pb.get("lat") is None:
            continue
        mine, est = our_fare(v, line, a, b)
        res = odsay((pa["lat"], pa["lng"]), (pb["lat"], pb["lng"]))
        paths = (res.get("result") or {}).get("path") or []
        pay = None
        for p in paths:
            subs = [s for s in p.get("subPath", []) if s.get("trafficType") in (1, 2)]
            if len(subs) == 1 and subs[0]["trafficType"] == 1 and lane_matches(((subs[0].get("lane") or [{}])[0]).get("name"), line):
                pay = (p.get("info") or {}).get("payment")
                break
        rows.append({"line": line, "a": a, "b": b, "mine": mine, "est": est, "odsay": pay, "err": (res.get("error") or [{}])[0].get("message") if not paths else None})
        time.sleep(0.12)
    err = [r for r in rows if r["err"]]
    print(f"쌍 {len(rows)} · ODsay 오류 {len(err)}" + (f" ({err[0]['err'][:60]})" if err else ""))
    for label, sel in (("추정 노선(공표 없음)", lambda r: r["line"] in EST_LINES), ("대조군 1~8호선(공표 있음)", lambda r: r["line"] in CONTROL_LINES)):
        grp = [r for r in rows if sel(r) and not r["err"]]
        both = [r for r in grp if r["mine"] is not None and r["odsay"] is not None]
        same = [r for r in both if r["mine"] == r["odsay"]]
        near = [r for r in both if abs(r["mine"] - r["odsay"]) <= 100]
        print(f"[{label}] 쌍 {len(grp)} · 우리 값 있음 {sum(1 for r in grp if r['mine'] is not None)} · ODsay 단일 노선 경로 있음 {sum(1 for r in grp if r['odsay'] is not None)} · 둘 다 {len(both)} → 같음 {len(same)} · ±100원 안 {len(near)}")
        for r in both:
            if r["mine"] != r["odsay"]:
                print(f"   다름: {r['line']} {r['a']}→{r['b']} 우리 {r['mine']}{'(추정)' if r['est'] else ''} · ODsay {r['odsay']}")


if __name__ == "__main__":
    main()
