# -*- coding: utf-8 -*-
"""holdout-2 — v3 를 최종 판정할 새 자료. 상황 카드 틀 40장(dev 가 쓰지 않은 나머지)을 새 장소에 결합하고 작성자 시트를 낸다. `[2026-10-20]`

    PYTHONPATH=. python -m eval.alternative_pick.holdout2           # DB 필요(활동 원장 읽기만)
    PYTHONPATH=. python -m eval.alternative_pick.holdout2 --allow-partial

★왜: holdout 80 · 감시 21 은 결과를 보고 v3 를 만들었고, dev 38 로 v3 를 다듬었다. v3 가 정말 나아졌는지는
  **아무도 본 적 없는 자료**로 한 번만 잰다(`대체 후보 판정 — 허용 기준과 성능 향상 테스트 계획.md` 2-3).
★장소: holdout 80 · dev 38 의 원래 장소 · 후보 contentid 를 모두 뺀다. 결합 조건은 dev 와 같다(`dev.bind_fresh`).
★문장: 사람(작성자 2명)이 쓴다 — 결합 뒤 상황 문장의 원래 장소 · 사유를 새 장소에 맞추고, 묶음마다 번갈아 나눈다.
  작성자는 후보 · 정답을 보지 않는다(카드 검토를 하지 않았으니 이번에는 누구도 후보를 본 적이 없다).
★감시 경로 판은 같은 카드에서 고객 문장을 뺀 것으로 나중에 만든다(`watch.variants`) — 사람 라벨은 그때 따로 단다.
★출력(`eval/situation_cards/`): `cards_llm_bound_h2.jsonl`(정답 키 포함 — 작성자에게 주지 않는다) ·
  `sheet_llm_bound_h2.csv` · `write_by_작성자1_h2.csv` · `write_by_작성자2_h2.csv`.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
import re
import time
from datetime import timedelta
from pathlib import Path

from .build import HERE
from .dev import CARDS_DIR, bind_fresh, load_holdout, pick

BOUND_H2 = CARDS_DIR / "cards_llm_bound_h2.jsonl"
SHEET_H2 = CARDS_DIR / "sheet_llm_bound_h2.csv"
SHEET_COLUMNS = ["카드", "작성자", "상황", "참고", "고객이 보낼 말(1~2문장)", "메모"]
WRITERS = ("작성자1", "작성자2")


def remaining(cards: list[dict]) -> list[dict]:
    """dev 가 고르지 않은 카드 틀 — 두 자료가 같은 틀을 쓰지 않게."""
    taken = {c["card_id"] for c in pick(cards)}
    return [c for c in cards if c["card_id"] not in taken]


def remaining_cards(cards: list[dict], ids: list[str]) -> dict[str, dict]:
    by = {c["card_id"]: c for c in cards}
    return {cid: by[cid] for cid in ids}


def dev_places() -> set[str]:
    """dev 38 의 원래 장소 · 후보 contentid(결합 중간 파일에 원래 장소 id 가 있다)."""
    partial = HERE / "cases_dev.partial.json"
    bound = json.loads(partial.read_text(encoding="utf-8"))["bound"]
    return {card["origin"]["id"] for card in bound.values()} | {c["id"] for card in bound.values() for c in card["candidates"]}


TOP10_NOTE = "운영 순위 상위 10곳(화면 3곳 + 더보기)에서 카드 조건에 맞는 3곳을 순위 순서대로 고름 — 화면에 보이는 3곳은 아님"


def bind_top10(todo: dict[str, dict], used: set[str], *, sample: int, seed: int, partial: Path) -> tuple[dict, list[str]]:
    """`[2026-10-20 사용자 결정 ①]` 화면 3곳으로 못 묶은 카드 — 운영 순위 상위 10곳 안에서 3곳을 고른다.

    ★운영 화면 3곳만으로는 충돌(C) · 동점(D) 조합이 드물어 원래 장소 1,087곳을 다 보고도 C 0/6 · D 1/6 였다(81분).
    ★후보 이유 · 운영 여부 · 순서는 운영 계산(`rank_alternatives`) 그대로다. 고른 3곳은 순위 순서를 지키므로 1순위가 코드 순서다.
    ★조건은 같다 — 엄격 조건(`strict_ok`) · 생활 시설 · 브랜드 매장 없음 · 같은 부지 없음 · holdout · dev · 앞서 묶은 장소 제외.
    """
    from .dev import card_tools

    fixes, bc = card_tools()
    used = set(used)
    fixes.CLEAN_SET.update(todo)
    state = json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {"bound": {}, "checked": []}
    bound, checked = state["bound"], set(state["checked"])
    for cid, card in bound.items():
        todo.pop(cid, None)
        used |= {card["origin"]["id"], *(c["id"] for c in card["candidates"])}
    origins = [o for o in bc.sample_origins("demo", sample, seed=seed) if o["id"] not in used]
    random.Random(seed + 1).shuffle(origins)
    total, started = len(origins), time.monotonic()
    print(f"상위 10곳에서 고르기 — 남은 카드 {len(todo)}장 · 원래 장소 {total}곳", flush=True)
    for n, origin in enumerate(origins, start=1):
        if not todo:
            break
        if n % 25 == 0:
            print(f"  … 원래 장소 {n}/{total} · 남은 카드 {len(todo)} · {time.monotonic() - started:.0f}초", flush=True)
        if origin["id"] in checked or origin["id"] in used:
            continue
        checked.add(origin["id"])
        pool = fixes.find_place_candidates(fixes.get_connection, "demo", origin["id"])
        if not pool:
            continue
        by_id = {str(c.get("contentid")): c for c in pool["candidates"]}
        ranked_by: dict[tuple[int, str | None], list[dict]] = {}
        for cid, card in list(todo.items()):
            hour = 19 if card["preference_target"]["attribute"] == "night_view" else 14
            at = bc.WEEK["토"] + timedelta(hours=hour)
            for pref in bc.PREFERENCES:
                if (hour, pref) not in ranked_by:
                    ranked = bc.rank_alternatives(pool["origin"], pool["candidates"], at, preference=pref)
                    ranked_by[(hour, pref)] = [
                        {"id": str(a["contentid"]), "title": a["title"], "code_reason": a["reason"],
                         "distance_km": a["distance_km"], "availability": a["availability"],
                         "class": by_id[str(a["contentid"])].get("lclsSystm3"),
                         "auto_tags": sorted(bc.tags(by_id[str(a["contentid"])]))}
                        for a in [*ranked["alternatives"], *ranked["more_alternatives"]][:10]
                        if a.get("revalidated", True) is not False]
                top = [c for c in ranked_by[(hour, pref)] if c["id"] not in used]
                combo = next((list(x) for x in itertools.combinations(top, 3)
                              if fixes.strict_ok(card, list(x), origin["title"])), None)
                if combo is None:
                    continue
                survey = {k: v for k, v in card["survey"].items() if k != "priority"}
                if pref is not None:
                    survey["priority"] = [pref]
                o1, o2 = pool["origin"].get("lclsSystm1"), pool["origin"].get("lclsSystm2")
                bound[cid] = {**card, "origin": {"id": origin["id"], "title": origin["title"],
                                                 "class": pool["origin"].get("lclsSystm3"),
                                                 "outdoor": fixes.weather_from_class(o1, o2)},
                              "at": at.isoformat(), "candidates": combo, "survey": survey, "candidates_by": TOP10_NOTE}
                used |= {origin["id"], *(c["id"] for c in combo)}
                del todo[cid]
                print(f"[+{len(bound)}] {cid}({card['stratum']} · {card['preference_target']['label']}) ← {origin['title']} "
                      f"· 원래 장소 {n}/{total} · 남은 {len(todo)}", flush=True)
                break
            if cid in bound:
                break
        partial.write_text(json.dumps({"bound": bound, "checked": sorted(checked)}, ensure_ascii=False), encoding="utf-8")
    return bound, sorted(todo, key=lambda x: int(x[2:]))


def situation(card: dict, old_title: str, fixes) -> str:
    """상황 문장을 새 원래 장소에 맞춘다 — 「X에 가려 했는데 …」 꼴은 사유까지 바꾸고(`situation_for`), 그 밖은 이름만."""
    from datetime import datetime

    at = datetime.fromisoformat(card["at"])
    # ★결합본 원래 장소(다시 고른 이름)가 문장에 없으면 카드 틀 이름(`origin_hint`)으로 적혀 있다(E · F 「X 일정이 바뀌어」)
    for name in dict.fromkeys((old_title, card.get("origin_hint") or old_title)):
        if f"{name}에 가려 했는데" in card["situation"]:
            return fixes.situation_for(card, name, card["origin"]["title"], card["origin"].get("outdoor"), at)
        if name in card["situation"]:
            return re.sub(re.escape(name), card["origin"]["title"], card["situation"])
    raise SystemExit(f"{card['card_id']}: 상황 문장에서 원래 장소({old_title} · {card.get('origin_hint')})를 못 찾았다")


def assign(cards: list[dict], seed: int) -> dict[str, str]:
    """묶음(`stratum` · 단서 출처)마다 번갈아 — 사람마다 · 묶음마다 차이가 1장 이하(`build_cards.assign_writers` 와 같은 방식)."""
    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in cards:
        groups.setdefault((c["stratum"], c["preference_target"]["cue_source"]), []).append(c)
    out, turn = {}, 0
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda c: c["card_id"])
        rng.shuffle(members)
        for c in members:
            out[c["card_id"]] = WRITERS[turn % len(WRITERS)]
            turn += 1
    return out


def write_sheet(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise SystemExit(f"{path.name} 이(가) 이미 있다 — 덮어쓰지 않는다")
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=2021)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    if BOUND_H2.exists():
        raise SystemExit(f"{BOUND_H2.name} 가 이미 있다 — 덮어쓰지 않는다")

    holdout = load_holdout()
    used = ({c["origin"]["id"] for c in holdout} | {x["id"] for c in holdout for x in c["candidates"]} | dev_places())
    todo = {c["card_id"]: c for c in remaining(holdout)}
    partial = BOUND_H2.with_name(BOUND_H2.stem + ".partial.json")
    bound, missing, fixes = bind_fresh(todo, used, sample=args.sample, seed=args.seed, partial=partial)
    if missing:
        # ★`[2026-10-20 사용자 결정 ①]` 화면 3곳으로 못 묶은 카드는 운영 순위 상위 10곳에서 고른다
        taken = used | {card["origin"]["id"] for card in bound.values()} | {c["id"] for card in bound.values()
                                                                             for c in card["candidates"]}
        extra, missing = bind_top10({cid: todo_card for cid, todo_card in remaining_cards(holdout, missing).items()},
                                    taken, sample=args.sample, seed=args.seed,
                                    partial=BOUND_H2.with_name(BOUND_H2.stem + ".top10.partial.json"))
        bound = {**bound, **extra}
    if missing and not args.allow_partial:
        raise SystemExit(f"결합 실패 {len(missing)}장 {missing} — 묶은 {len(bound)}장은 중간 파일에 남겼다(--allow-partial)")

    old_titles = {c["card_id"]: c["origin"]["title"] for c in holdout}
    cards = []
    for cid in sorted(bound, key=lambda x: int(x[2:])):
        card = bound[cid]
        new_id = cid.replace("L-", "H-")
        cards.append({**card, "card_id": new_id, "from_card": cid, "situation": situation(card, old_titles[cid], fixes),
                      "acceptable_draft": [c["id"] for c in card["candidates"]
                                           if card["preference_target"]["attribute"] in fixes.strict_attrs(c)],
                      "label_by": "rule-draft(strict_attrs) — 사람 라벨 전", "needs_review": "",
                      "writer_saw_candidates": False})
    writer = assign(cards, args.seed)
    with BOUND_H2.open("w", encoding="utf-8", newline="\n") as fh:
        for c in cards:
            fh.write(json.dumps({**c, "writer": writer[c["card_id"]]}, ensure_ascii=False) + "\n")
    rows = [{"카드": c["card_id"], "작성자": writer[c["card_id"]], "상황": c["situation"],
             "참고": c.get("writer_hint", ""), "고객이 보낼 말(1~2문장)": "", "메모": ""} for c in cards]
    write_sheet(SHEET_H2, rows)
    for w in WRITERS:
        write_sheet(CARDS_DIR / f"write_by_{w}_h2.csv", [r for r in rows if r["작성자"] == w])
    by = {w: {} for w in WRITERS}
    for c in cards:
        by[writer[c["card_id"]]][c["stratum"]] = by[writer[c["card_id"]]].get(c["stratum"], 0) + 1
    print(json.dumps({"cards": len(cards), "missing": missing, "by_writer": by}, ensure_ascii=False))


if __name__ == "__main__":
    main()
