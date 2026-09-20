# scripts/collect/build_airport_bus_v1.py — 인천공항 버스 원본 → 판정기용 시간표
# 실행: 저장소 루트에서  python scripts/collect/build_airport_bus_v1.py   (API 호출 없음)
# 출력: processed/mobility/airport_bus_v1.jsonl        출발 1건 = 1행 (지하철 timetable_v1 과 같은 축)
#       processed/mobility/airport_bus_stops.jsonl     노선별 경유 정류장
#       processed/mobility/airport_bus_v1_report.md    노선 수·시간표 제공 여부·권역
#
# ★핵심: t1wdayt / t1wt 는 배차간격이 아니라 **출발 시각 전체 목록**이다("0540, 0610, 0630, …").
#   지하철과 같은 정밀도라 이 노선들은 대기 시간이 추정이 아니라 시각 자체가 확정 근거가 된다.
#   다만 일부 노선은 시각 목록 대신 첫차·막차만 들어 있다 — 그건 timetable_available=false 로 구분한다.
import json, re, collections
from datetime import datetime, timezone, timedelta
from _paths import RAW_MOBILITY, PROCESSED

KST = timezone(timedelta(hours=9))
SRC = RAW_MOBILITY / "incheon_airport_bus.json"
OUT_DIR = PROCESSED / "mobility"
OUT = OUT_DIR / "airport_bus_v1.jsonl"
STOPS = OUT_DIR / "airport_bus_stops.jsonl"
REPORT = OUT_DIR / "airport_bus_v1_report.md"
SOURCE = "incheon_airport_bus"

# 원본 필드 → (터미널, 요일). t1wt/t2wt 는 주말이며 지하철의 holiday 와 같은 축으로 둔다.
SLOTS = [("T1", "weekday", "t1wdayt", "t1endfirst", "t1endlast", "t1ridelo"),
         ("T1", "holiday", "t1wt", "t1endfirst", "t1endlast", "t1ridelo"),
         ("T2", "weekday", "t2wdayt", "t2endfirst", "t2endlast", "t2ridelo"),
         ("T2", "holiday", "t2wt", "t2endfirst", "t2endlast", "t2ridelo")]


def clean(v):
    """원본에 빈 문자열과 문자열 'None' 이 섞여 온다."""
    s = str(v).strip() if v is not None else ""
    return "" if s.lower() in ("", "none", "null", "-") else s


def hhmm(s):
    s = clean(s)
    return f"{s[:2]}:{s[2:4]}:00" if re.fullmatch(r"\d{4}", s) else None


def fare(raw):
    """요금은 등급별로 여러 값이 올 수 있다("13000, 13000"). 최저·최고만 남긴다."""
    vals = sorted({int(x) for x in re.findall(r"\d+", clean(raw))})
    if not vals:
        return None
    return {"min": vals[0], "max": vals[-1]} if len(vals) > 1 else vals[0]


def times_of(raw):
    return [t for t in (hhmm(x) for x in clean(raw).split(",")) if t]


doc = json.loads(SRC.read_text(encoding="utf-8"))
fetched = doc.get("fetched_at", "")[:10]
items = doc["items"]

OUT_DIR.mkdir(parents=True, exist_ok=True)
rows = 0
stat = collections.Counter()
per_route = {}
with OUT.open("w", encoding="utf-8") as g, STOPS.open("w", encoding="utf-8") as gs:
    for it in items:
        no = clean(it.get("busnumber"))
        base = {
            "route_no": no, "route_key": f"airport_bus|{no}",
            "area": clean(it.get("area")), "bus_class": clean(it.get("busclass")),
            "fare_adult": fare(it.get("adultfare")),          # "13000, 13000" 처럼 등급별로 여러 값이 온다
            "operator": clean(it.get("cpname")),
            "to_airport_first": hhmm(it.get("toawfirst")), "to_airport_last": hhmm(it.get("toawlast")),
            "source": SOURCE, "fetched_at": fetched, "fetched_at_precision": "day",
        }
        # 경유 정류장 — 중복이 섞여 오므로 순서를 지키며 중복 제거
        seen, stops = set(), []
        for nm in (clean(it.get("routeinfo")).split(",")):
            nm = nm.strip()
            if nm and nm not in seen:
                seen.add(nm); stops.append(nm)
        if stops:
            gs.write(json.dumps({"route_no": no, "stop_count": len(stops), "stops": stops,
                                 "source": SOURCE, "fetched_at": fetched}, ensure_ascii=False) + "\n")

        got_any = False
        for term, day, tf, ff, lf, rl in SLOTS:
            times = times_of(it.get(tf))
            first, last = hhmm(it.get(ff)), hhmm(it.get(lf))
            if not times and not (first or last):
                continue
            # 시각이 2개 이하이고 첫차·막차와 같으면 시간표가 아니라 첫차·막차만 실린 것이다
            has_tt = len(times) > 2 or (times and set(times) - {first, last})
            stat[f"{term}/{day}/{'시간표' if has_tt else '첫차막차만'}"] += 1
            got_any = True
            for t in (times or [x for x in (first, last) if x]):
                g.write(json.dumps({**base, "terminal": term, "day_type": day, "dep_time": t,
                                    "dir": "from_airport", "ride_location": clean(it.get(rl)) or None,
                                    "first": first, "last": last,
                                    "timetable_available": bool(has_tt),
                                    "grade": "확정" if has_tt else "첫차막차만",
                                    }, ensure_ascii=False) + "\n")
                rows += 1
        per_route[no] = got_any

lines = ["# 인천공항 버스 시간표 v1", "",
         f"생성 {datetime.now(KST).isoformat(timespec='seconds')} · 소스 {SOURCE} · 수집일 {fetched}",
         f"노선 {len(items)}개 · 출발 행 {rows:,}개 · 정류장 목록 {sum(1 for _ in STOPS.open(encoding='utf-8'))}개 노선", "",
         "## 터미널·요일별 제공 상태", "", "| 구분 | 노선 수 |", "|---|---|"]
lines += [f"| {k} | {v} |" for k, v in sorted(stat.items())]
lines += ["", "## 읽는 법", "",
          "- `t1wdayt`·`t1wt` 는 **출발 시각 전체 목록**이다. 지하철과 같은 정밀도이므로 이 노선의 출발 시각은 `확정` 근거가 된다 — 버스라고 해서 대기 시간을 추정으로 두지 않는다.",
          "- 시각이 2개뿐이고 첫차·막차와 같으면 시간표가 아니라 첫차·막차만 실린 것이다. `timetable_available=false`, `grade=첫차막차만` 으로 구분하고, 그 노선의 중간 시각은 `근거 없음`으로 다룬다.",
          "- `dir=from_airport` — 이 데이터는 공항 출발편의 시각이다. 공항행은 `to_airport_first`·`to_airport_last`(첫차·막차)만 있고 중간 시각이 없다.",
          "- 요일 축은 지하철과 맞췄다: `weekday` / `holiday`(원본의 주말 필드).",
          "- 승차 위치(`ride_location`)는 판정에 쓰지 않고 안내 문구 소재로만 쓴다.",
          "- T2 값이 비어 있는 노선은 T1 만 운행한다. 인바운드 고객이 T2 도착이면 그 노선은 후보에서 뺀다."]
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"출발 행 {rows:,}개 → {OUT}")
print(f"정류장 → {STOPS}")
print(f"리포트 → {REPORT}")
for k, v in sorted(stat.items()):
    print(f"   {k}: {v}")
