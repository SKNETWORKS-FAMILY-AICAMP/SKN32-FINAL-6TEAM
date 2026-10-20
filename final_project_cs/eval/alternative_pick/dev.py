# -*- coding: utf-8 -*-
"""dev 40 — 프롬프트 · 입력을 고치며 견주는 자료(계획서 3절 dev). holdout 80 과 원래 장소 · 후보가 겹치지 않는다. `[2026-10-20]`

    PYTHONPATH=. python -m eval.alternative_pick.dev          # DB 필요(활동 원장 읽기만) → cases_dev.jsonl

★왜: holdout 80 · 감시 21 은 결과를 이미 봤다 — 그것으로 프롬프트를 고치면 과적합이다(계획서 3절 · [8]).
★카드 틀: 상황 카드 결합본(`cards_llm_bound_v0.jsonl`)의 묶음 · 이길 속성 · 결합 조건만 가져온다(장소 · 후보는 버린다).
  묶음마다 카드 번호 순으로 하나 걸러 고른다 → A 7 · B 14 · C 7 · D 4 · E 6 · F 2 = 40(holdout 80 비율의 절반, 아래 `pick`).
★결합: 10-17 카드 재결합과 같은 엄격 조건(`apply_review_fixes.strict_ok` · 화면 3곳에 생활 시설 · 브랜드 매장 없음) +
  holdout 의 원래 장소 · 후보 contentid 를 모두 뺀다.
★문장: 템플릿(`build.template_text` — 계획서 「dev 는 템플릿 문장」). 사람 문장의 말투는 holdout 에서만 잰다.
★라벨: 규칙(`strict_attrs`) — 단서 없음 · 함정 · 범위 이탈은 셋 다 허용, 나머지는 이길 속성이 있는 후보.
  사람 검토 전이라 `label_by` 에 규칙임을 적는다. dev 는 판 사이 **비교용**이라 같은 라벨로 견주면 된다(전환 판정에 쓰지 않는다).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import timedelta
from pathlib import Path

from .build import BOUND, HERE, template_text, write

CARDS_DIR = BOUND.parent
DEV = HERE / "cases_dev.jsonl"
TARGET = {"A": 7, "B": 14, "C": 7, "D": 4, "E": 6, "F": 2}          # holdout 80 의 절반 비율
RULE_LABEL = "rule:strict_attrs(dev) — 사람 검토 전"


def pick(cards: list[dict]) -> list[dict]:
    """묶음마다 카드 번호 순 짝수째(1 · 3 · 5 …번째)부터 목표 수만큼."""
    out = []
    for stratum, n in TARGET.items():
        members = sorted((c for c in cards if c["stratum"] == stratum), key=lambda c: int(c["card_id"][2:]))
        out += (members[::2] + members[1::2])[:n]
    return out


def label(card: dict, shown: list[dict], strict_attrs) -> tuple[list[str], bool]:
    """(허용 id, 코드 순서 유지 기대)."""
    ids = [c["id"] for c in shown]
    attr = card["preference_target"]["attribute"]
    if attr == "none" or card["expected_behavior"] in ("keep_code_order", "no_fabrication", "valid_ids_only"):
        return ids, card["expected_behavior"] == "keep_code_order"
    return [c["id"] for c in shown if attr in strict_attrs(c)], False


def card_tools():
    """상황 카드 폴더 스크립트(DB import 포함) — 늦게 불러온다."""
    sys.path.insert(0, str(CARDS_DIR))
    import apply_review_fixes as fixes  # noqa: E402
    import bind_candidates as bc  # noqa: E402
    return fixes, bc


def load_holdout() -> list[dict]:
    return [json.loads(line) for line in BOUND.read_text(encoding="utf-8").splitlines() if line.strip()]


def bind_fresh(todo: dict[str, dict], used: set[str], *, sample: int, seed: int,
               partial: Path) -> tuple[dict[str, dict], list[str], object]:
    """카드 틀마다 `used` 와 겹치지 않는 새 원래 장소 · 후보를 엄격 조건으로 묶는다. `[2026-10-20]` dev · holdout-2 가 같이 쓴다.

    ★중간 저장(`partial`) — 묶을 때마다 쓰고, 다시 돌리면 거기서 잇는다. 반환: (묶은 카드, 못 묶은 카드 id, fixes 모듈).
    """
    fixes, bc = card_tools()
    PREFERENCES, WEEK, sample_origins, shown_for = bc.PREFERENCES, bc.WEEK, bc.sample_origins, bc.shown_for
    used = set(used)
    fixes.CLEAN_SET.update(todo)

    # ★`[2026-10-20]` 중간 저장 — 묶을 때마다 `<out>.partial.json` 에 쓰고, 다시 돌리면 거기서 잇는다
    state = json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else {"bound": {}, "checked": []}
    bound: dict[str, dict] = state["bound"]
    checked = set(state["checked"])
    for cid, card in bound.items():
        todo.pop(cid, None)
        used |= {card["origin"]["id"], *(c["id"] for c in card["candidates"])}
    origins = [o for o in sample_origins("demo", sample, seed=seed) if o["id"] not in used]
    random.Random(seed).shuffle(origins)
    total, started = len(origins), time.monotonic()
    print(f"시작 — 묶음 {len(bound)}/{len(bound) + len(todo)} · 원래 장소 표본 {total}곳(이미 본 곳 {len(checked)})", flush=True)

    def save() -> None:
        partial.write_text(json.dumps({"bound": bound, "checked": sorted(checked)}, ensure_ascii=False), encoding="utf-8")

    for n, origin in enumerate(origins, start=1):
        if not todo:
            break
        if n % 50 == 0:
            print(f"  … 원래 장소 {n}/{total} 확인 · 묶음 {len(bound)}/{len(bound) + len(todo)} · "
                  f"{time.monotonic() - started:.0f}초", flush=True)
        if origin["id"] in checked or origin["id"] in used:
            continue
        checked.add(origin["id"])
        pool = fixes.find_place_candidates(fixes.get_connection, "demo", origin["id"])
        if not pool:
            continue
        # ★화면 3곳은 카드와 상관없이 (시각, 선호도) 로만 정해진다 — 카드마다 다시 계산하지 않는다(전에는 이것 때문에 느렸다)
        shown_by: dict[tuple[int, str | None], list[dict]] = {}
        for cid, card in list(todo.items()):
            hour = 19 if card["preference_target"]["attribute"] == "night_view" else 14
            at = WEEK["토"] + timedelta(hours=hour)
            for pref in PREFERENCES:
                shown = shown_by.setdefault((hour, pref), shown_for(pool, at, pref))
                if any(c["id"] in used for c in shown) or not fixes.strict_ok(card, shown, origin["title"]):
                    continue
                survey = {k: v for k, v in card["survey"].items() if k != "priority"}
                if pref is not None:
                    survey["priority"] = [pref]
                o1, o2 = pool["origin"].get("lclsSystm1"), pool["origin"].get("lclsSystm2")
                bound[cid] = {**card, "origin": {"id": origin["id"], "title": origin["title"],
                                                 "class": pool["origin"].get("lclsSystm3"),
                                                 "outdoor": fixes.weather_from_class(o1, o2)},
                              "at": at.isoformat(), "candidates": shown, "survey": survey}
                used |= {origin["id"], *(c["id"] for c in shown)}
                del todo[cid]
                print(f"[{len(bound)}/{len(bound) + len(todo)}] {cid}({card['stratum']} · "
                      f"{card['preference_target']['label']}) ← {origin['title']} · 원래 장소 {n}/{total}", flush=True)
                break
            if cid in bound:
                break                                  # 원래 장소 하나에 카드 하나
        save()
    return bound, sorted(todo, key=lambda x: int(x[2:])), fixes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=2020)
    parser.add_argument("--out", type=Path, default=DEV)
    parser.add_argument("--allow-partial", action="store_true",
                        help="표본을 다 돌고도 못 묶은 카드가 있으면 그 카드만 빼고 쓴다(빠진 카드는 매니페스트에)")
    args = parser.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"{args.out} 가 이미 있다 — 덮어쓰지 않는다")
    partial = args.out.with_name(args.out.stem + ".partial.json")

    holdout = load_holdout()
    used = {c["origin"]["id"] for c in holdout} | {x["id"] for c in holdout for x in c["candidates"]}
    bound, missing, fixes = bind_fresh({c["card_id"]: c for c in pick(holdout)}, used, sample=args.sample,
                                       seed=args.seed, partial=partial)
    if missing and not args.allow_partial:
        raise SystemExit(f"결합 실패 {len(missing)}장 {missing} — 묶은 {len(bound)}장은 {partial.name} 에 남겼다. "
                         "--sample 을 늘려 다시 돌리면 잇는다(또는 --allow-partial)")
    cases = []
    for cid in sorted(bound, key=lambda x: int(x[2:])):
        card = bound[cid]
        acceptable, quiet = label(card, card["candidates"], fixes.strict_attrs)
        cases.append({
            "case_id": cid.replace("L-", "D-"), "kind": "alternative_pick", "split": "dev", "stratum": card["stratum"],
            "inputs": {"origin": card["origin"]["title"], "at": card["at"],
                       "candidates": [{"id": c["id"], "title": c["title"], "code_reason": c["code_reason"],
                                       "distance_km": c["distance_km"], "class": c["class"]} for c in card["candidates"]],
                       "preference": {"survey": card["survey"], "customer_text": template_text(card)}},
            "acceptable": acceptable, "forbidden": [], "no_fit": not acceptable, "expects_code_order": quiet,
            "forbidden_claims": card.get("forbidden_claims") or [],
            "rationale": f"{card['preference_target']['label']} ({card['preference_target']['cue_source']})",
            "label_by": RULE_LABEL, "text_by": "template", "from_card": cid,
        })
    manifest = write(cases, args.out, {"labeler": RULE_LABEL, "texts": "template", "smoke": False,
                                       "dev": {"seed": args.seed, "sample": args.sample, "missing_cards": missing,
                                               "disjoint_from": "holdout 80 의 원래 장소 · 후보 contentid"}})
    print(json.dumps({k: manifest[k] for k in ("cases", "by_stratum", "sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
