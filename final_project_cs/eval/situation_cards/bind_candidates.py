# -*- coding: utf-8 -*-
"""LLM 상황 카드에 실제 후보 3곳을 붙인다 — 운영 코드 그대로(`find_place_candidates` → `rank_alternatives`).

★**계산만 한다.** LLM 을 부르지 않는다. DB(활동 원장 `activity.ac_place`)는 읽기만 한다.
★후보의 속성 태그(실내 · 역사 …)는 **결합 조건을 보는 초안**이다 — 관광공사 분류에서 기계로 읽은 값이라
  정답이 아니다. 허용 답(`acceptable`)은 2인 라벨로 정한다(`label_by: auto-tag-draft`).
★결합 조건(`binding`)을 못 맞추면 선호도(설문 `priority` → 분류를 푸는 폭)를 None → activity → mobility 로 넓혀
  다시 뽑는다. 쓴 선호도는 카드 설문의 `priority` 에 적는다 — 운영에서 같은 후보가 나오려면 그 설문이어야 한다.
  끝까지 못 맞추면 `binding_status: failed` 로 남긴다(지어 붙이지 않는다).

실행: `python eval/situation_cards/bind_candidates.py [--tenant demo]` (final_project_cs 에서, DB 필요)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class
from app.domains.travel_ops.instances.activity.alternatives import rank_alternatives
from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates
from app.infrastructure.db.session import get_connection

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")
#: 2026-11-16(월) ~ 22(일) 한 주 — 카드의 요일을 날짜로 바꾼다
WEEK = {name: datetime(2026, 11, 16 + i, tzinfo=KST) for i, name in enumerate("월화수목금토일")}
DEFAULT_AT = ("토", "14:00")
#: 카드의 장소 이름 → 관광공사 contentid(원장 `activity.ac_place` 와 같은 번호). 2026-10-16 로컬 DB 에서 찾음.
ORIGIN_IDS = {
    "경복궁": "126508", "경복궁 야간관람": "126508", "광장시장": "132183", "국립중앙박물관": "129703",
    "국립현대미술관": "1934593", "낙산공원": "129501", "낙산성곽길": "4065859", "남산공원": "126485",
    "남산서울타워": "126535", "덕수궁": "126509", "동대문디자인플라자": "2470006", "롯데월드타워 전망대": "2492348",
    "명동": "264311", "북촌한옥마을": "126537", "북한산 둘레길": "1196871", "서울숲": "128611",
    "서울식물원": "2589349", "어린이대공원": "126490", "인사동 쌈지길": "128553", "리버시티수상스키장": "767780",
    "창덕궁": "1604941", "코엑스 아쿠아리움": "130284", "코엑스몰": "1984944", "하늘공원": "2654607",
    "북촌전통공예체험관": "2993183",
}
PREFERENCES = (None, "activity", "mobility")
NIGHT = re.compile(r"전망|타워|스카이|야경|루프탑")


def tags(c: dict) -> set[str]:
    """관광공사 분류 → 속성 초안. 모르는 것은 붙이지 않는다(아이 동반 · 덜 걷기는 사람 몫)."""
    l1, l2 = c.get("lclsSystm1") or "", c.get("lclsSystm2") or ""
    out: set[str] = set()
    weather = weather_from_class(l1, l2)
    if weather is True:
        out.add("outdoor")
    elif weather is False:
        out.add("indoor")
    out |= {"history"} if l1 == "HS" else set()
    out |= {"nature"} if l1 == "NA" or l2 in ("VE03", "VE04") else set()
    out |= {"experience"} if l1 == "EX" else set()
    out |= {"culture"} if l2 in ("VE06", "VE07") else set()
    out |= {"shopping"} if l1 == "SH" else set()
    out |= {"leisure"} if l1 == "LS" else set()
    out |= {"night_view"} if NIGHT.search(c.get("title") or "") else set()
    return out


def when(card: dict) -> datetime:
    m = re.search(r"([월화수목금토일])요일 (\d{1,2}):(\d{2})", card["situation"])
    day, clock = (m.group(1), f"{m.group(2)}:{m.group(3)}") if m else DEFAULT_AT
    if not m and "휴관" in card["situation"] or not m and "휴궁" in card["situation"]:
        day = "월"
    hour, minute = map(int, clock.split(":"))
    return WEEK[day] + timedelta(hours=hour, minutes=minute)


def check(card: dict, shown: list[dict]) -> tuple[bool, str]:
    target = card["preference_target"]
    attr, rule = target["attribute"], card["binding"]
    if len(shown) < 3:
        return False, f"후보 {len(shown)}곳"
    if not target["inferable"]:
        return True, "자동 확인 불가 속성 — 사람 확인"
    if attr == "none":
        return True, "단서 없음 — 조건 없음"
    hit = [attr in s["auto_tags"] for s in shown]
    if sum(hit) < rule["need_match"]:
        return False, f"맞는 후보 {sum(hit)}곳 < {rule['need_match']}"
    if len(hit) - sum(hit) < rule["need_nonmatch"]:
        return False, "안 맞는 후보가 없다(순서를 바꿀 이유가 없음)"
    if rule.get("code_first_matches") is False and hit[0]:
        return False, "코드 1순위가 이미 맞는다(기준선과 같은 답)"
    lose = target.get("loses_to")
    if rule.get("need_survey_match") and lose and lose in {"kid", "low_walking"}:
        return True, "설문 쪽 속성 자동 확인 불가 — 사람 확인"
    if rule.get("need_survey_match") and lose and not any(lose in s["auto_tags"] for s in shown):
        return False, f"설문 쪽 속성({lose}) 후보가 없다 — 충돌이 성립 안 함"
    return True, "충족"


def draft_acceptable(card: dict, shown: list[dict]) -> list[str]:
    target, behavior = card["preference_target"], card["expected_behavior"]
    if behavior == "keep_code_order" or behavior == "valid_ids_only":
        return [shown[0]["id"]]
    if behavior == "no_fabrication":
        return [s["id"] for s in shown]
    if not target["inferable"]:
        return []
    return [s["id"] for s in shown if target["attribute"] in s["auto_tags"]]


def bind(card: dict, tenant: str) -> dict:
    content_id = ORIGIN_IDS.get(card["origin_hint"])
    if content_id is None:
        return {**card, "binding_status": "failed", "binding_note": "카탈로그 장소를 못 찾음"}
    pool = find_place_candidates(get_connection, tenant, content_id)
    if pool is None:
        return {**card, "binding_status": "failed", "binding_note": f"origin {content_id} 없음"}
    at = when(card)
    attempts = []
    for pref in PREFERENCES:
        ranked = rank_alternatives(pool["origin"], pool["candidates"], at, preference=pref)
        shown = [{"id": str(a["contentid"]), "title": a["title"], "code_reason": a["reason"],
                  "distance_km": a["distance_km"], "availability": a["availability"],
                  "class": next((c.get("lclsSystm3") for c in pool["candidates"]
                                 if str(c.get("contentid")) == str(a["contentid"])), None),
                  "auto_tags": sorted(tags(next(c for c in pool["candidates"]
                                                if str(c.get("contentid")) == str(a["contentid"]))))}
                 for a in ranked["alternatives"][:3]]
        ok, note = check(card, shown)
        attempts.append({"preference": pref, "ok": ok, "note": note, "titles": [s["title"] for s in shown]})
        if ok:
            survey = dict(card["survey"])
            if pref is not None:
                survey["priority"] = [pref]
            return {**card, "survey": survey, "origin": {"id": content_id, "title": pool["origin"]["title"],
                                                          "class": pool["origin"].get("lclsSystm3")},
                    "at": at.isoformat(), "candidates": shown, "acceptable_draft": draft_acceptable(card, shown),
                    "binding_status": "ok", "binding_note": note, "attempts": attempts, "label_by": "auto-tag-draft"}
    return {**card, "origin": {"id": content_id, "title": pool["origin"]["title"]}, "at": at.isoformat(),
            "binding_status": "failed", "binding_note": attempts[-1]["note"], "attempts": attempts}


def sample_origins(tenant: str, n: int, seed: int) -> list[dict]:
    """다시 고를 원래 장소 표본 — 활동 분류(쇼핑 · 음식 · 숙박 제외) · 좌표 있음 · seed 고정."""
    with get_connection() as conn, conn.cursor() as cur:
        # ★`[2026-10-16]` 활동 원장만 읽는다(운영 후보 경로와 같은 표). 원장은 공용이라 `tenant` 는 쓰지 않는다
        cur.execute("SELECT content_id, name_ko FROM activity.ac_place WHERE content_id ~ '^[0-9]+$' AND delisted_at IS NULL "
                    "AND lat IS NOT NULL AND coalesce(lcls1,'') NOT IN ('SH','EV','FD','AC','') ORDER BY content_id")
        rows = [{"id": r[0], "title": r[1]} for r in cur.fetchall()]
    random.Random(seed).shuffle(rows)
    return rows[:n]


def shown_for(pool: dict, at: datetime, pref: str | None) -> list[dict]:
    by_id = {str(c.get("contentid")): c for c in pool["candidates"]}
    ranked = rank_alternatives(pool["origin"], pool["candidates"], at, preference=pref)
    return [{"id": str(a["contentid"]), "title": a["title"], "code_reason": a["reason"],
             "distance_km": a["distance_km"], "availability": a["availability"],
             "class": by_id[str(a["contentid"])].get("lclsSystm3"),
             "auto_tags": sorted(tags(by_id[str(a["contentid"])]))}
            for a in ranked["alternatives"][:3]]


def survey_coverage(table: dict) -> dict:
    """★설문 무응답(선호도 None)일 때 화면 3곳의 속성 초안이 **서로 다른** 원래 장소의 비율.
    같으면 취향으로 순서를 바꿀 근거가 분류에 없다 — LLM 순서가 쓸모 있는 상황이 얼마나 되는지의 대략치."""
    total = mixed = 0
    for (_, pref), shown in table.items():
        if pref is not None or len(shown) < 3:
            continue
        total += 1
        mixed += len({tuple(s["auto_tags"]) for s in shown}) > 1
    return {"origins": total, "mixed": mixed}


def rebind(card: dict, table: dict, origins: list[dict], used: set[str], at: datetime) -> dict | None:
    """실패한 카드의 원래 장소를 표본에서 다시 고른다. 상황 문장의 장소 이름 · 사유를 함께 바꾼다."""
    for origin in origins:
        if origin["id"] in used:
            continue
        for pref in PREFERENCES:
            shown = table.get((origin["id"], pref))
            if not shown:
                continue
            ok, note = check(card, shown)
            if not ok:
                continue
            used.add(origin["id"])
            outdoor = weather_from_class(*(table[("_class", origin["id"])]))
            # ★비 사유는 실내 쪽을 바라는 카드에만 — 「비가 오는데 숲길을 걷고 싶다」 같은 모순을 만들지 않는다
            rainy = outdoor is not False and card["preference_target"]["attribute"] in ("indoor", "culture", "shopping")
            why = "비 예보로 야외 일정이 어렵다는 안내를 받았습니다" if rainy else "운영이 임시로 중단됐다는 공지를 봤습니다"
            situation = re.sub(rf"{re.escape(card['origin_hint'])}에 가려 했는데 [^.]*\.",
                               f"{origin['title']}에 가려 했는데 {why}.", card["situation"], count=1)
            survey = dict(card["survey"])
            if pref is not None:
                survey["priority"] = [pref]
            return {**card, "situation": situation, "survey": survey, "origin_rebound_from": card["origin_hint"],
                    "origin": {"id": origin["id"], "title": origin["title"]}, "at": at.isoformat(),
                    "candidates": shown, "acceptable_draft": draft_acceptable(card, shown), "binding_status": "ok",
                    "binding_note": f"원래 장소를 다시 골랐다 — {note}", "label_by": "auto-tag-draft",
                    "needs_review": "; ".join(x for x in (card["needs_review"],
                                                          "원래 장소를 다시 골랐다 — 상황 문장 · 후보가 자연스러운지 확인") if x)}
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="demo")
    # ★`[2026-10-16]` 300 → 800 — 카드 80장으로 늘린 뒤 300곳으로는 충돌 · 동점 카드 3장의 조건을 맞추는 원래 장소를 못 찾았다
    parser.add_argument("--sample", type=int, default=800, help="다시 고를 원래 장소 표본 수")
    args = parser.parse_args()
    cards = [json.loads(line) for line in (HERE / "cards_llm_v0.jsonl").open(encoding="utf-8")]
    bound = [bind(card, args.tenant) for card in cards]
    first = sum(card["binding_status"] == "ok" for card in bound)
    print(f"1차 결합(카드에 적힌 장소) {first}/{len(bound)} = {first / len(bound):.0%}")
    # ★2차 — 실패한 카드만, 표본 원래 장소에서 조건을 맞는 곳을 찾는다. 시각은 카드 시각 그대로.
    origins = sample_origins(args.tenant, args.sample, seed=1016)
    table: dict = {}
    at_default = WEEK[DEFAULT_AT[0]] + timedelta(hours=14)
    for origin in origins:
        pool = find_place_candidates(get_connection, args.tenant, origin["id"])
        if not pool:
            continue
        table[("_class", origin["id"])] = (pool["origin"].get("lclsSystm1"), pool["origin"].get("lclsSystm2"))
        for pref in PREFERENCES:
            table[(origin["id"], pref)] = shown_for(pool, at_default, pref)
    used = {card["origin"]["id"] for card in bound if card["binding_status"] == "ok"}
    for i, card in enumerate(bound):
        if card["binding_status"] == "ok":
            continue
        again = rebind(cards[i], table, origins, used, at_default)
        if again is not None:
            bound[i] = {**again, "attempts": card.get("attempts", [])}
    coverage = survey_coverage(table)
    print(f"설문 무응답일 때 화면 3곳의 속성이 섞인 원래 장소 {coverage['mixed']}/{coverage['origins']} = "
          f"{coverage['mixed'] / max(coverage['origins'], 1):.0%}")
    with (HERE / "cards_llm_bound_v0.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for card in bound:
            fh.write(json.dumps(card, ensure_ascii=False) + "\n")
    # ★작성자 시트도 결합 뒤 문장으로 다시 쓴다(블라인드 — 정답 키 · 후보 · 묶음 없음). 결합 실패 카드는 빼고 낸다.
    order = [card for card in bound if card["binding_status"] == "ok"]
    random.Random(1016).shuffle(order)
    with (HERE / "sheet_llm_bound_v0.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["카드", "작성자", "상황", "참고", "고객이 보낼 말(1~2문장)", "메모"])
        for i, card in enumerate(order):
            out.writerow([card["card_id"], f"작성자{i % 4 + 1}", card["situation"], card.get("writer_hint", ""), "", ""])
    by: dict[str, list[int]] = {}
    for card in bound:
        row = by.setdefault(card["stratum"], [0, 0])
        row[0] += card["binding_status"] == "ok"
        row[1] += 1
    ok = sum(r[0] for r in by.values())
    print(f"결합 {ok}/{len(bound)} = {ok / len(bound):.0%} · 묶음별 " + " · ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(by.items())))
    for card in bound:
        if card["binding_status"] != "ok":
            print(f"  실패 {card['card_id']} {card['stratum']} {card['origin_hint']} [{card['preference_target']['attribute']}] — "
                  + " | ".join(f"{a['preference']}: {a['note']} {a['titles']}" for a in card.get("attempts", [])) or card["binding_note"])


if __name__ == "__main__":
    main()
