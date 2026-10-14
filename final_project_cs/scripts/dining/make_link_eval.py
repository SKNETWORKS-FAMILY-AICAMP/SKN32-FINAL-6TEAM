# -*- coding: utf-8 -*-
"""원장 ↔ 장소 연결 정답셋을 만든다 — 여행에 들어온 장소가 **맞는 원장 가게**와 이어지는지 잰다. `[2026-10-14]`

    python -m scripts.dining.make_link_eval --dsn postgresql://postgres:postgres@127.0.0.1:5433/dining_rebuild

★왜 새로 만드나 — 원장 DB 의 연결 1,883건은 전부 `linked_by = rebuild` 다. 원장 가게로 코어 장소를 **만들면서** 이었으니
  100% 가 당연하고, 「맞게 이었나」를 재지 않는다. 실제로 틀릴 수 있는 곳은 여행 등록 때 들어온 장소(관광공사 · 카카오 · 원장 찾기)를
  원장 가게와 잇는 두 길이다 — 등록 뒤 `dining.link_core_place`(224) · 등록 전 확인 화면 `ledger._catalog_uid`.
★정답은 **만드는 방법으로 정해진다** — 원장 가게 하나에서 장소를 만들고(이름 변형 · 좌표 흔들기) 그 가게를 정답으로 둔다.
  원장에 없는 가게 · 다른 지점은 「잇지 않음」이 정답이다. 사람이 하나씩 고른 정답이 아니다 — 실제 여행 장소 표본의 사람 검수는 따로 남는다.
★원장 DB 는 읽기만 한다. 같은 seed · 같은 원장이면 같은 자료가 나온다. holdout 은 dev 와 **가게가 겹치지 않는다** — 규칙을 고칠 때 보지 않는다.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "datasets"
SEED = 20261014
#: (모둠, dev 수, holdout 수, 설명) — 순서대로 가게를 뽑는다(한 가게는 한 사례에만)
GROUPS = (
    ("content_id", 8, 3, "관광공사 번호가 같은 가게 — 이름 · 좌표가 조금 달라도 잇는다"),
    ("exact_near", 8, 3, "이름이 같고 40m 안 — 카카오로 찾은 장소(번호 없음)"),
    ("name_variant", 8, 3, "지점 표시 · 띄어쓰기만 다른 이름, 40m 안"),
    ("far_offset", 6, 2, "같은 가게인데 좌표가 90~200m 어긋남(관광공사 · 카카오 좌표 차이) — 놓치면 missed"),
    ("neighbor", 8, 3, "80m 안에 다른 원장 가게가 있다 — 그쪽으로 이으면 오연결"),
    ("similar_pair", 4, 1, "80m 안에 이름이 비슷한 원장 가게가 하나 더 있다 — 같은 이름 쪽을 골라야 한다"),
    ("not_in_ledger", 8, 3, "원장에 없는 가게(체인 · 편의점)가 원장 가게 바로 옆 — 잇지 않는 것이 정답"),
    ("other_branch", 6, 2, "같은 이름의 가게가 1.5~3km 떨어진 곳 — 원장 가게가 아니다(다른 지점 · 동명 가게)"),
)
#: 원장에 없는지 만들 때 확인하는 이름(카카오에서 흔히 나오는 체인 · 편의점)
OUTSIDERS = ("GS25", "CU", "세븐일레븐", "다이소", "올리브영", "이디야커피", "메가MGC커피", "컴포즈커피",
             "빽다방", "투썸플레이스", "파리바게뜨", "뚜레쥬르", "맘스터치", "롯데리아", "버거킹", "배스킨라빈스")


def moved(lat: float, lng: float, metres: float, bearing_deg: float) -> tuple[float, float]:
    """(위도, 경도)를 방위각 쪽으로 metres 만큼 옮긴다. 서울 범위에서 1m 이내 오차."""
    rad = math.radians(bearing_deg)
    dlat = metres * math.cos(rad) / 111_320
    dlng = metres * math.sin(rad) / (111_320 * math.cos(math.radians(lat)))
    return round(lat + dlat, 7), round(lng + dlng, 7)


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = b[0] - a[0]
    dx = (b[1] - a[1]) * math.cos(math.radians(a[0]))
    return math.degrees(math.atan2(dx, dy)) % 360


def load(cur) -> tuple[list[dict], dict[str, str], dict[str, list[str]], list[tuple[str, str, float, float]]]:
    cur.execute("SELECT place_uid::text, name_ko, dining.norm_name(name_ko), lat, lng, road_address "
                "FROM dining.dn_place WHERE record_status <> 'closed' AND NOT is_synthetic "
                "AND lat IS NOT NULL AND lng IS NOT NULL ORDER BY place_uid")
    shops = [dict(uid=u, name=n, norm=k, lat=la, lng=lo, road=r or "") for u, n, k, la, lo, r in cur.fetchall()]
    # 관광공사 번호 → 가게(번호 하나가 가게 하나로만 이어지는 것)
    cur.execute("SELECT external_id, min(place_uid::text) FROM dining.dn_source_record "
                "WHERE source_code = 'tourapi_kor_food' AND match_status <> 'rejected' "
                "GROUP BY external_id HAVING count(DISTINCT place_uid) = 1")
    tour = {uid: cid for cid, uid in cur.fetchall()}
    by_norm: dict[str, list[str]] = {}
    for s in shops:
        by_norm.setdefault(s["norm"], []).append(s["uid"])
    # 80m 안 가게 짝(폐업 포함 — 연결 후보 뷰가 폐업을 거르지 않는다)
    cur.execute("SELECT a.place_uid::text, b.place_uid::text, dining.distance_m(a.lat, a.lng, b.lat, b.lng), "
                "dining.name_sim(dining.norm_name(a.name_ko), dining.norm_name(b.name_ko)) "
                "FROM dining.dn_place a JOIN dining.dn_place b ON a.place_uid <> b.place_uid "
                "AND b.lat BETWEEN a.lat - 0.001 AND a.lat + 0.001 AND b.lng BETWEEN a.lng - 0.0013 AND a.lng + 0.0013 "
                "WHERE a.record_status <> 'closed' AND NOT a.is_synthetic "
                "AND dining.distance_m(a.lat, a.lng, b.lat, b.lng) <= 80")
    pairs = cur.fetchall()
    return shops, tour, by_norm, pairs


def variant(shop: dict, rng: random.Random) -> str:
    name = shop["name"].strip()
    gu = next((w for w in shop["road"].split() if w.endswith("구")), "")
    choices = [name + " 본점", name.replace(" ", "") if " " in name else name[:2] + " " + name[2:]]
    if gu:
        choices.append(f"{name} {gu[:-1]}점")
    return rng.choice(choices)


def outsider_ok(cur, name: str, lat: float, lng: float) -> bool:
    """원장에 없는 이름인가 — 같은 정규화 이름이 없고, 150m 안에 유사도 0.6 이상인 가게도 없다."""
    cur.execute("SELECT count(*) FROM dining.dn_place WHERE dining.norm_name(name_ko) = dining.norm_name(%s) "
                "OR dining.norm_name(name_ko) LIKE dining.norm_name(%s) || '%%'", (name, name))
    if cur.fetchone()[0]:
        return False
    cur.execute("SELECT count(*) FROM dining.dn_place WHERE dining.distance_m(lat, lng, %s, %s) <= 150 "
                "AND dining.name_sim(dining.norm_name(name_ko), dining.norm_name(%s)) >= 0.6", (lat, lng, name))
    return cur.fetchone()[0] == 0


def build(dsn: str) -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(SEED)
    with psycopg.connect(dsn) as conn:
        conn.read_only = True
        cur = conn.cursor()
        shops, tour, by_norm, pairs = load(cur)
        index = {s["uid"]: s for s in shops}
        unique = [s for s in shops if len(by_norm[s["norm"]]) == 1 and len(s["norm"]) >= 2]
        rng.shuffle(unique)
        used: set[str] = set()
        near_other = {}       # 가게 → (이웃, 거리, 유사도) — 이름이 다른 이웃
        near_similar = {}     # 이름이 비슷한 이웃
        for a, b, dist, sim in pairs:
            if b in index:
                if sim >= 0.75 and index[a]["norm"] != index[b]["norm"]:
                    near_similar.setdefault(a, (b, dist, sim))
                elif sim < 0.5:
                    near_other.setdefault(a, (b, dist, sim))
        crowded = {a for a, *_ in pairs}       # 80m 안에 다른 가게가 있는 가게

        def take(test) -> dict | None:
            for shop in unique:
                if shop["uid"] not in used and test(shop):
                    used.add(shop["uid"])
                    return shop
            return None

        cases: dict[str, list[dict]] = {"dev": [], "holdout": []}
        counts = {}
        for group, n_dev, n_hold, why in GROUPS:
            made = 0
            for split, n in (("dev", n_dev), ("holdout", n_hold)):
                for _ in range(n):
                    case = make(group, take, rng, cur, tour, near_other, near_similar, crowded, index, why)
                    if case is None:
                        break
                    case["id"] = f"{'LK' if split == 'dev' else 'LH'}-{len(cases[split]) + 1:03d}"
                    cases[split].append(case)
                    made += 1
            counts[group] = made
        meta = {"made": date.today().isoformat(), "seed": SEED, "db": dsn.rsplit("/", 1)[-1],
                "shops_open": len(shops), "groups": counts}
    return cases["dev"], cases["holdout"], meta


def _place(name, lat, lng, *, source="kakao_local", content_id=None) -> dict:
    return {"name": name, "kind": "dining", "latitude": lat, "longitude": lng,
            "source_name": source, "source_content_id": content_id}


def make(group, take, rng, cur, tour, near_other, near_similar, crowded, index, why) -> dict | None:
    if group == "content_id":
        shop = take(lambda s: s["uid"] in tour)
        if shop is None:
            return None
        off = rng.uniform(15, 60)
        lat, lng = moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360))
        place = _place(shop["name"], lat, lng, source="tour_api", content_id=tour[shop["uid"]])
    elif group == "exact_near":
        shop = take(lambda s: s["uid"] not in crowded)
        if shop is None:
            return None
        off = rng.uniform(5, 40)
        place = _place(shop["name"], *moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360)))
    elif group == "name_variant":
        shop = take(lambda s: s["uid"] not in crowded and len(s["name"]) >= 3)
        if shop is None:
            return None
        off = rng.uniform(10, 40)
        place = _place(variant(shop, rng), *moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360)))
    elif group == "far_offset":
        shop = take(lambda s: s["uid"] not in crowded)
        if shop is None:
            return None
        off = rng.uniform(90, 200)
        place = _place(shop["name"], *moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360)))
    elif group == "neighbor":
        shop = take(lambda s: s["uid"] in near_other)
        if shop is None:
            return None
        other = index[near_other[shop["uid"]][0]]
        off = min(30.0, near_other[shop["uid"]][1] / 2)          # 이웃 쪽으로 — 이웃까지 반보다 가깝게
        place = _place(shop["name"], *moved(shop["lat"], shop["lng"], off,
                                            bearing((shop["lat"], shop["lng"]), (other["lat"], other["lng"]))))
        why = f"{why} — 이웃 「{other['name']}」({near_other[shop['uid']][1]:.0f}m)"
    elif group == "similar_pair":
        shop = take(lambda s: s["uid"] in near_similar)
        if shop is None:
            return None
        other = index[near_similar[shop["uid"]][0]]
        off = 10.0
        place = _place(shop["name"], *moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360)))
        why = f"{why} — 「{other['name']}」(유사도 {near_similar[shop['uid']][2]:.2f})"
    elif group == "not_in_ledger":
        shop = take(lambda s: True)
        if shop is None:
            return None
        off = rng.uniform(0, 20)
        lat, lng = moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360))
        for _ in range(20):
            gu = next((w for w in shop["road"].split() if w.endswith("구")), "")
            name = f"{rng.choice(OUTSIDERS)} {(gu[:-1] or '서울')}{rng.choice(('역', '중앙', '시청', ''))}점"
            if outsider_ok(cur, name, lat, lng):
                break
        else:
            return None
        return {"group": group, "why": f"{why} — 옆 원장 가게 「{shop['name']}」", "place": _place(name, lat, lng),
                "expect": {"place_uid": None, "name": None},
                "made_from": {"place_uid": shop["uid"], "name": shop["name"], "offset_m": round(off, 1)}}
    elif group == "other_branch":
        shop = take(lambda s: True)
        if shop is None:
            return None
        off = rng.uniform(1500, 3000)
        place = _place(shop["name"], *moved(shop["lat"], shop["lng"], off, rng.uniform(0, 360)))
        return {"group": group, "why": why, "place": place, "expect": {"place_uid": None, "name": None},
                "made_from": {"place_uid": shop["uid"], "name": shop["name"], "offset_m": round(off, 1)}}
    else:
        raise ValueError(group)
    return {"group": group, "why": why, "place": place,
            "expect": {"place_uid": shop["uid"], "name": shop["name"]},
            "made_from": {"place_uid": shop["uid"], "name": shop["name"], "offset_m": round(off, 1)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://postgres:postgres@127.0.0.1:5433/dining_rebuild")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    dev, holdout, meta = build(a.dsn)
    out = Path(a.out)
    for name, rows in (("dining_link_v1.jsonl", dev), ("dining_link_holdout_v1.jsonl", holdout)):
        with (out / name).open("w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps({"id": row.pop("id"), **row, "meta": meta}, ensure_ascii=False) + "\n")
        print(name, len(rows))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
