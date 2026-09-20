# scripts/collect/build_bus_all_v1.py
# 서울 시내버스 21노선 → **717노선 전수**. API 호출 0회.
#
# 왜 호출이 0인가: seoul_bus_find_routes.py 의 --enumerate / --fetch-stops 가 이미
#   raw/mobility/seoul_bus_all_routes.json  (717 노선 · 첫차·막차·배차·기종점)
#   raw/mobility/seoul_bus_all_stops.json   (717 노선 전부의 정류장)
# 를 받아 뒀다. seoul_bus_collect.py --routes 로 717개를 돌리면 호출이 1,400여 회라
# 하루 쿼터 1,000 을 넘는다. **이미 받은 것을 쓰는 게 맞다.**
#
# 실행:
#   python scripts/collect/build_bus_all_v1.py                 # 만들어 보고 *_v2 로 쓴다(기본)
#   python scripts/collect/build_bus_all_v1.py --dry-run       # 쓰지 않고 숫자만 본다
#   python scripts/collect/build_bus_all_v1.py --replace-v1    # v1 을 덮어쓴다(되돌릴 수 없다)
#
# ★ 정규화 규칙은 seoul_bus_collect.py 를 **그대로** 옮겼다. 한 줄도 바꾸지 않는다 —
#   바꾸면 기존 21노선의 값이 달라지고, 그러면 회귀가 왜 움직였는지 구분이 안 된다.
#   [4] 검사가 그것을 확인한다.
#
# ★ fetched_at 은 **오늘이 아니라 캐시를 받은 날**이다. 값을 오늘 것으로 적으면
#   확인 시각을 위조하는 것이다. 캐시 안의 firstBusTm/lastBusTm 날짜에서 뽑는다.
import argparse, collections, json, re, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import RAW_MOBILITY, PROCESSED                      # noqa: E402

ROUTE_TYPE = {"1": "공항", "2": "마을", "3": "간선", "4": "지선", "5": "순환",
              "6": "광역", "7": "인천", "8": "경기", "9": "폐지", "10": "투어", "15": "심야"}
CONFIRMED_TYPES = {"1", "2", "3", "4", "5", "6", "7", "8", "10", "15"}
NON_SEOUL_TYPES = {"7", "8"}
SEOUL_ID_RANGE = range(100, 125)


def bus_time(s, base=None):
    """'YYYYMMDDHHMMSS' → 'HH:MM'. base 보다 날짜가 크면 24 를 더한다(익일 막차)."""
    s = (s or "").strip()
    if not re.fullmatch(r"\d{14}", s):
        return None, None
    d, hh, mm = s[:8], int(s[8:10]), int(s[10:12])
    if base and d > base:
        hh += 24 * (datetime.strptime(d, "%Y%m%d").date() - datetime.strptime(base, "%Y%m%d").date()).days
    return f"{hh:02d}:{mm:02d}", d


def is_seoul(item):
    rid = item.get("busRouteId", "")
    if item.get("routeType") in NON_SEOUL_TYPES:
        return False
    return rid[:3].isdigit() and int(rid[:3]) in SEOUL_ID_RANGE


def cache_date(routes):
    """캐시를 받은 날 = 노선 시각 문자열의 날짜 최빈값. 오늘 날짜를 쓰지 않는다."""
    c = collections.Counter()
    for it in routes.values():
        for k in ("firstBusTm", "lastBusTm"):
            v = (it.get(k) or "").strip()
            if re.fullmatch(r"\d{14}", v):
                c[v[:8]] += 1
    if not c:
        raise SystemExit("캐시에서 날짜를 못 뽑았다 — fetched_at 을 오늘로 적지 않는다. 중단한다.")
    d = c.most_common(1)[0][0]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 숫자만 낸다")
    ap.add_argument("--replace-v1", action="store_true", help="*_v1 을 덮어쓴다(되돌릴 수 없다)")
    a = ap.parse_args()
    suffix = "v1" if a.replace_v1 else "v2"

    src_routes = RAW_MOBILITY / "seoul_bus_all_routes.json"
    src_stops = RAW_MOBILITY / "seoul_bus_all_stops.json"
    for p in (src_routes, src_stops):
        if not p.exists():
            raise SystemExit(f"없다: {p}\n  먼저 seoul_bus_find_routes.py --enumerate / --fetch-stops 를 돌린다.")
    all_routes = json.loads(src_routes.read_text(encoding="utf-8"))
    all_stops = json.loads(src_stops.read_text(encoding="utf-8"))

    fetched = cache_date(all_routes)
    source_id = f"seoul_bus_route@{fetched}"
    print(f"[0] 캐시 {len(all_routes)}노선 · 정류장 캐시 {len(all_stops)}노선 · 확인 시각 {fetched}")

    routes_out, stops_out, coords = [], [], {}
    excluded, no_stops, unknown_type = [], [], collections.Counter()

    for rid, it in all_routes.items():
        if not is_seoul(it):
            excluded.append((it.get("busRouteNm"), rid, it.get("routeType")))
            continue
        rt = it.get("routeType", "")
        if rt not in CONFIRMED_TYPES:
            unknown_type[rt] += 1
        first, base = bus_time(it.get("firstBusTm"))
        last, _ = bus_time(it.get("lastBusTm"), base)
        term_raw = (it.get("term") or "").strip()
        term = int(term_raw) if term_raw.isdigit() else None
        if term == 0:
            term = None          # 배차 0분이 아니라 배차 개념이 없다는 뜻이다
        routes_out.append({
            "route_id": rid, "route_nm": it.get("busRouteNm"),
            "route_type": rt,
            "route_type_nm": ROUTE_TYPE.get(rt),
            "route_type_grade": "확정" if rt in CONFIRMED_TYPES else "추정",
            "corp_nm": re.sub(r"\s+", " ", it.get("corpNm", "")),
            "st_station_nm": it.get("stStationNm"), "ed_station_nm": it.get("edStationNm"),
            "length_km": float(it["length"]) if it.get("length") else None,
            "term_min": term,
            "first_time": first, "last_time": last,
            "crosses_midnight": bool(last and int(last[:2]) >= 24),
            "grade_service_window": "확정" if first and last else "근거없음",
            "grade_wait": "추정" if term else "근거없음",
            "source": "seoul_bus_route", "source_id": source_id,
            "fetched_at": fetched, "fetched_at_precision": "day",
        })

        stops = all_stops.get(rid) or []
        if not stops:
            no_stops.append((it.get("busRouteNm"), rid))
        for s in stops:
            lat = float(s["gpsY"]) if s.get("gpsY") else None
            lng = float(s["gpsX"]) if s.get("gpsX") else None
            ars = s.get("arsId")
            stops_out.append({
                "route_id": rid, "route_nm": it.get("busRouteNm"),
                "seq": int(s["seq"]) if (s.get("seq") or "").isdigit() else None,
                "station_id": s.get("station"), "ars_id": ars,
                "station_nm": s.get("stationNm"),
                "lat": lat, "lng": lng,
                "direction": s.get("direction"),
                "sect_dist_m": int(s["fullSectDist"]) if (s.get("fullSectDist") or "").isdigit() else None,
                "transfer_yn": s.get("transYn"),
                "source": "seoul_bus_route", "source_id": source_id,
                "fetched_at": fetched, "fetched_at_precision": "day",
            })
            if ars and lat and lng:
                key = f"버스|{ars}"
                coords.setdefault(key, {
                    "station_key": key, "line": "버스", "station_nm": s.get("stationNm"),
                    "station_nm_en": None, "station_cd": ars, "lat": lat, "lng": lng,
                    "operator": None, "src_name": s.get("stationNm"), "src_line": "서울시내버스",
                    "station_id": s.get("station"), "routes": [],
                })
                coords[key]["routes"].append(it.get("busRouteNm"))

    by_type = collections.Counter(r["route_type_nm"] for r in routes_out)
    print(f"[1] 서울 노선 {len(routes_out)} · 제외(인천·경기 면허) {len(excluded)}")
    print(f"    유형: {dict(by_type)}")
    print(f"[2] 정류장 {len(stops_out)}행 · 고유 정류장(ars) {len(coords)}")
    if no_stops:
        print(f"    ! 정류장 캐시가 없는 노선 {len(no_stops)}개: {[n for n, _ in no_stops[:8]]}")
    print(f"[3] 배차 없음(term_min=NULL) {sum(1 for r in routes_out if r['term_min'] is None)} · "
          f"자정 넘김 {sum(1 for r in routes_out if r['crosses_midnight'])} · "
          f"막차 미상 {sum(1 for r in routes_out if not r['last_time'])}")
    if unknown_type:
        print(f"    ! 처음 보는 routeType {dict(unknown_type)} → route_type_grade=추정")

    # [4] ★ 기존 21노선이 한 글자도 안 바뀌었는가
    old = PROCESSED / "mobility" / "bus_route_v1.jsonl"
    if old.exists():
        prev = {json.loads(l)["route_id"]: json.loads(l) for l in old.open(encoding="utf-8")}
        now = {r["route_id"]: r for r in routes_out}
        missing = sorted(set(prev) - set(now))
        diff = []
        for rid, o in prev.items():
            n = now.get(rid)
            if not n:
                continue
            # fetched_at·source_id 는 캐시 날짜라 달라질 수 있다. 그 둘만 빼고 비교한다.
            ks = set(o) | set(n)
            d = {k: (o.get(k), n.get(k)) for k in ks - {"fetched_at", "source_id"} if o.get(k) != n.get(k)}
            if d:
                diff.append((rid, o.get("route_nm"), d))
        print(f"[4] 기존 21노선 대조 — 사라진 노선 {len(missing)} · 값이 달라진 노선 {len(diff)}")
        for rid, nm, d in diff[:5]:
            print(f"    ! {nm}({rid}) {d}")
        if missing:
            print(f"    ! 사라짐: {missing}")
        if missing or diff:
            print("    ★ 확장이 기존 값을 바꿨다. 쓰지 않는다.")
            if not a.dry_run:
                raise SystemExit(2)

    if a.dry_run:
        print("[5] --dry-run — 아무것도 쓰지 않았다")
        return

    outs = {
        PROCESSED / "mobility" / f"bus_route_{suffix}.jsonl":
            "\n".join(json.dumps(r, ensure_ascii=False) for r in routes_out) + "\n",
        PROCESSED / "mobility" / f"bus_stops_{suffix}.jsonl":
            "\n".join(json.dumps(s, ensure_ascii=False) for s in stops_out) + "\n",
        PROCESSED / "mobility" / (f"bus_stop_coords.json" if a.replace_v1 else "bus_stop_coords_v2.json"):
            json.dumps(coords, ensure_ascii=False, indent=1),
    }
    for p, text in outs.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"[5] {p.name}  {len(text):,} bytes")
    print(f"\n  다음: 회귀를 새 파일로 한 번 돌려 본다(v1 은 그대로 둔 채)\n"
          f"  python scripts/verify_time.py --cases tests/mobility/bus_legs_v1.json --check-expect \\\n"
          f"      --bus-route data/travel/processed/mobility/bus_route_{suffix}.jsonl \\\n"
          f"      --bus-stops data/travel/processed/mobility/bus_stops_{suffix}.jsonl")


if __name__ == "__main__":
    main()
