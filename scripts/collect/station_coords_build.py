# scripts/collect/station_coords_build.py — 역 좌표표 (국가철도공단 표준데이터 → 우리 station_key)
# 실행: 저장소 루트에서  python scripts/collect/station_coords_build.py [--src <파일경로>]
# 선행(수동 1회): 공공데이터포털 "전국도시철도역사정보표준데이터"(15013205) XLSX 를 raw/mobility/ 에 저장.
#   오픈API 없음·연 1회 갱신·저장 자유. 카카오 좌표는 저장 금지라 링크 조립용 좌표는 이 소스여야 한다.
#
# ★매핑은 노선명이 아니라 **역명**으로 한다.
#   표준데이터는 코레일 구간을 운영 노선이 아니라 철도 노선명으로 부른다 —
#   '1호선'은 서울교통공사 구간 10개역뿐이고 나머지는 경부선·경인선·경원선·안산과천선·일산선으로 흩어진다.
#   '수인선'+'분당선'이 수인분당선, '인천국제공항선'이 공항철도다. 노선명으로 이으면 절반이 깨진다(9/9 확인: 322/799).
#   환승역은 물리적으로 같은 위치이므로 역명이 같으면 노선이 달라도 같은 좌표를 쓴다 —
#   링크 조립과 도보 거리 개략에는 충분하다(출구별 차이는 [추정] 범위 안).
#   대신 동명 역(부산 서면·대구 중앙로 …)을 막기 위해 **수도권 운영기관·노선만** 남긴다.
#
# ★출처가 둘이다 (2026-09-13 명시). 좌표만 표준데이터에서 오고, **역명(한글·영문)은 열린데이터광장
#   OA-15442(stations_all.json)** 에서 온다. 필드 이름이 양쪽 다 STATION_NM_ENG 라 한 소스처럼 보였고,
#   레코드의 source 가 kric_station_standard 하나여서 영문명 결함을 표준데이터 탓으로 오인했다.
#   이제 레코드에 coord_source / name_source 를 따로 적는다.
#
# ★영문명 보정 (2026-09-13). 원본 영문명에 결함이 18역 있었다 — 대소문자 9·붙어쓰기 6·이중공백 3·
#   부역명 1(중복 포함), 그리고 규칙으로 못 잡는 4건(Lrt·Sutgogae·Inchon·Station 접미).
#   config/mobility/station_nm_en_fix.json 으로 보정하고 원본은 station_nm_en_src 에 남긴다.
#   2026-09-13 추가: 약어 정책(Int'l 통일)과 역 단위 일관성(같은 한글 역명은 같은 영문명).
#   보정한 역은 station_nm_en_grade='추정'. 검사는 scripts/check_station_names.py.
import json, re, argparse, collections, unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from _paths import RAW_MOBILITY, PROCESSED

KST = timezone(timedelta(hours=9))
OUT_DIR = PROCESSED / "mobility"
OUT = OUT_DIR / "station_coords.json"
REPORT = OUT_DIR / "station_coords_report.md"
STATIONS = RAW_MOBILITY / "stations_all.json"
SOURCE = "kric_station_standard"          # 좌표 출처
NAME_SOURCE = "seoul_opendata_OA-15442"   # 역명(한글·영문) 출처 — 좌표와 다르다
FIXES = Path(__file__).resolve().parents[2] / "config" / "mobility" / "station_nm_en_fix.json"

_fx = json.loads(FIXES.read_text(encoding="utf-8")) if FIXES.exists() else {"치환": {"규칙": []}, "역별": {}}
# 규칙마다 등급이 다르다 — 오탈자 교정은 확정 유지, 약어 통일은 우리가 고른 것이라 추정으로 내린다
_SUBS = [(r["from"], r["to"], r.get("grade", "확정")) for r in _fx.get("치환", {}).get("규칙", [])]
_BY_ST = {k: v["to"] for k, v in _fx.get("역별", {}).items() if isinstance(v, dict) and "to" in v}


def fix_en(key, en):
    """영문명 보정 → (값, 등급, 사유). 원본은 호출한 쪽에서 station_nm_en_src 로 남긴다.

    역별 표가 우선이다. 없으면 기계적 문자 치환(백틱·굽은따옴표·이중공백)만 건다 —
    치환은 의미가 안 바뀌므로 확정을 유지하고, 역별 보정은 판단이 들어가므로 추정으로 내린다.
    """
    if not en:
        return None, "근거없음", "원본 없음"
    if key in _BY_ST:
        return _BY_ST[key], "추정", "역별 보정표"
    out, grade, kinds = en, "확정", []
    for a, b, g in _SUBS:
        if a not in out:
            continue
        while a in out:
            out = out.replace(a, b)
        kinds.append("약어 통일" if g == "추정" else "문자 치환")
        if g == "추정":
            grade = "추정"
    if out != en:
        return out, grade, " + ".join(dict.fromkeys(kinds))
    return en, "확정", None

# 수도권만 남긴다 ── 한국철도공사는 전국이라 노선명으로 한 번 더 거른다
KEEP_OPERATOR = re.compile(r"서울교통공사|한국철도공사|코레일|공항철도|인천교통공사|신분당|의정부|용인|김포|"
                           r"우이신설|메트로9호선|경기철도|새서울|남서울|서부광역|국가철도공단|에스알|SR|"
                           r"남양주도시공사|구리도시공사|하남도시공사|성남도시개발")   # 별내선·진접선 등 지자체 운영
DROP_OPERATOR = re.compile(r"부산|대구|대전|광주|김해")
KORAIL_SEOUL = {"경부선", "경인선", "경원선", "경의중앙선", "경춘선", "경강선", "분당선", "수인선",
                "안산과천선", "일산선", "장항선", "진접선", "서해선", "중앙선"}
KORAIL_DROP = {"동해선", "대경선"}          # 부산·대구권


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s·.\-()（）]", "", s)


def base_name(s):                            # "이촌(국립중앙박물관)" → "이촌"
    return re.sub(r"\(.*?\)", "", str(s or "")).strip()


def keys_of(nm):
    """매칭 후보 키들.

    ★코레일은 역명 끝에 '역'을 붙이고("용산역", "수원역(분당)") 서울교통공사는 붙이지 않는다("제기동").
      '서울역'처럼 '역'이 이름의 일부인 경우도 있어 무조건 떼면 안 된다 — 양쪽을 다 후보로 둔다.
      지하철 시간표 매칭에서 겪은 것과 같은 함정이다(소싱 문서 3-1 표).
    """
    base = base_name(nm)
    out = {norm(nm), norm(base), norm(re.sub(r"역$", "", base)), norm(base + "역")}
    return {k for k in out if k}


def find_src():
    for p in sorted(RAW_MOBILITY.glob("*")):
        if p.suffix.lower() in (".xlsx", ".xls", ".csv") and any(
                k in p.name for k in ("역사", "station", "KRIC", "kric", "도시철도")):
            return p
    return None


def load_rows(path):
    if path.suffix.lower() == ".csv":
        import csv
        for enc in ("utf-8-sig", "cp949"):
            try:
                with path.open(encoding=enc, newline="") as f:
                    return list(csv.DictReader(f))
            except UnicodeDecodeError:
                continue
        raise SystemExit("CSV 인코딩을 읽지 못했다 (utf-8/cp949 시도)")
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise SystemExit("pip install openpyxl 또는 CSV 로 저장해서 다시 실행")
    ws = load_workbook(path, read_only=True, data_only=True).active
    it = ws.iter_rows(values_only=True)
    header = [str(c or "").strip() for c in next(it)]
    return [dict(zip(header, r)) for r in it]


def pick(row, *keys):
    for k in row:
        kk = norm(k)
        for want in keys:
            if norm(want) in kk:
                return row[k]
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--src", help="표준데이터 파일 경로 (미지정 시 raw/mobility 에서 자동 탐색)")
args = ap.parse_args()
src = Path(args.src) if args.src else find_src()
if not src or not src.exists():
    raise SystemExit(f"표준데이터 파일이 없다. data.go.kr 15013205 에서 받아 {RAW_MOBILITY} 에 두고 다시 실행.")
raw = load_rows(src)
print(f"표준데이터 {len(raw)}행 ← {src.name}")

# ── 표준데이터 → 역명별 좌표 ─────────────────────────────────────
coords_by_name, basis, dropped = {}, set(), collections.Counter()
for row in raw:
    nm, line = pick(row, "역사명", "역명"), str(pick(row, "노선명") or "")
    lat, lng = pick(row, "역위도", "위도"), pick(row, "역경도", "경도")
    op = str(pick(row, "운영기관명", "운영기관") or "")
    d = pick(row, "데이터기준일자", "기준일자")
    if d:
        basis.add(str(d)[:10])
    if not (nm and lat and lng):
        dropped["좌표없음"] += 1; continue
    if line in KORAIL_DROP or DROP_OPERATOR.search(op) or not KEEP_OPERATOR.search(op):
        dropped["수도권밖"] += 1; continue
    if "철도공사" in op and line not in KORAIL_SEOUL:
        dropped[f"코레일 수도권밖:{line}"] += 1; continue
    rec = {"lat": float(lat), "lng": float(lng), "src_name": str(nm), "operator": op, "src_line": line}
    for k in keys_of(nm):
        coords_by_name.setdefault(k, rec)
print(f"수도권 역명 키 {len(coords_by_name)}개 (제외 {sum(dropped.values())}행)")

# ── 우리 역 목록에 붙이기 ───────────────────────────────────────
stations = json.loads(STATIONS.read_text(encoding="utf-8"))
fetched = sorted(basis)[-1] if basis else None
coords, missing = {}, []
fixed = collections.Counter()
for s in stations:
    key = f"{s['LINE_NUM']}|{s['STATION_NM']}"
    hit = next((coords_by_name[k] for k in keys_of(s["STATION_NM"]) if k in coords_by_name), None)
    if not hit:
        missing.append(key); continue
    en_src = s.get("STATION_NM_ENG")
    en, en_grade, en_why = fix_en(key, en_src)
    if en_why:
        fixed[en_why] += 1
    coords[key] = {"station_key": key, "line": s["LINE_NUM"], "station_nm": s["STATION_NM"],
                   "station_nm_en": en, "station_nm_en_src": en_src,
                   "station_nm_en_grade": en_grade, "station_nm_en_fix": en_why,
                   "station_cd": s["STATION_CD"],
                   "lat": hit["lat"], "lng": hit["lng"], "operator": hit["operator"],
                   "src_name": hit["src_name"], "src_line": hit["src_line"],
                   "source": SOURCE, "coord_source": SOURCE, "name_source": NAME_SOURCE,
                   "fetched_at": fetched, "fetched_at_precision": "day"}

OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"source": SOURCE, "src_file": src.name, "data_basis_date": fetched,
                           "built_at": datetime.now(KST).isoformat(timespec="seconds"),
                           "count": len(coords), "stations": coords}, ensure_ascii=False, indent=1), encoding="utf-8")

by_line = collections.Counter(k.split("|")[0] for k in missing)
lines = ["# 역 좌표표 커버리지", "",
         f"소스 {SOURCE} ({src.name}, 기준일자 {fetched}) · 생성 {datetime.now(KST).isoformat(timespec='seconds')}",
         f"좌표 확보 **{len(coords)} / {len(stations)}** · 미확보 {len(missing)}", "",
         "| 노선 | 좌표 없는 역 |", "|---|---|"]
lines += [f"| {l} | {c}개 — {', '.join(n.split('|')[1] for n in missing if n.startswith(l))[:120]} |"
          for l, c in sorted(by_line.items())]
lines += ["", "## 읽는 법", "",
          "- 매핑 키는 **역명**이다. 표준데이터가 코레일 구간을 운영 노선이 아니라 철도 노선명(경부선·경인선·안산과천선 …)으로 불러 노선명으로는 이을 수 없다.",
          "- 환승역은 물리적으로 같은 위치이므로 노선이 달라도 같은 좌표를 쓴다. 출구별 차이는 링크 조립·도보 개략 용도에서 [추정] 범위 안이다.",
          "- 동명 역(부산 서면·대구 중앙로 …)은 운영기관과 코레일 노선 화이트리스트로 걸렀다.",
          "- **코레일은 역명 끝에 '역'을 붙이고**('용산역', '수원역(분당)') 서울교통공사는 붙이지 않는다('제기동'). '서울역'처럼 '역'이 이름의 일부인 경우도 있어 양쪽을 다 후보 키로 둔다.",
          f"- 제외 내역: {dict(dropped)}",
          "- 좌표가 없는 역은 카카오맵 링크를 장소명만으로 조립하고, 그 구간의 도보 거리 판정은 '근거 없음'으로 둔다.",
          "", "## 출처가 둘이다", "",
          f"- 좌표 `coord_source` = {SOURCE} (표준데이터 XLSX)",
          f"- 역명(한글·영문) `name_source` = {NAME_SOURCE} (stations_all.json)",
          "- 필드 이름이 양쪽 다 `STATION_NM_ENG` 라 한 소스로 오인했다. 레코드의 `source` 는 좌표 출처다.",
          "", "## 영문명 보정", "",
          f"- 보정 {sum(v for k, v in fixed.items() if k)}역 — " + (", ".join(f"{k} {v}역" for k, v in fixed.most_common() if k) or "없음"),
          "- 원본은 `station_nm_en_src` 에 남는다. 등급: 역별 보정·약어 통일 = `추정`, 문자 치환(오탈자) = 확정 유지.",
          "- 표: `config/mobility/station_nm_en_fix.json` · 검사: `python scripts/check_station_names.py`"]
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"좌표 {len(coords)}/{len(stations)}역 → {OUT}")
print(f"미확보 {len(missing)}역 · 리포트 → {REPORT}")
