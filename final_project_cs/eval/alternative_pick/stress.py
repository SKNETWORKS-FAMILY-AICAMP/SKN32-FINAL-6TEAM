# -*- coding: utf-8 -*-
"""dev 스트레스 — 고객 요청 경로에서 holdout-2 가 찾은 실패 꼴을 dev 카드에 일부러 넣은 사례. `[2026-10-20]`

    PYTHONPATH=. python -m eval.alternative_pick.stress      # → cases_dev_stress.jsonl (DB 없음)

★왜: holdout-2(v3)에서 고객 요청 경로가 막힌 이유 — ①「박물관 아니면 전시」를 「박물관 말고」로 거꾸로 읽음(심각)
  ②후보 정보에 없는 성격을 이유에 붙임(「조용한 전시관에 맞다」 · 이름의 「갤러리」로 전시). dev 38 은 템플릿 문장
  (「오늘은 실내 쪽으로 바꿔 주세요」)이라 이런 표현이 없다. holdout-2 는 결과를 봤으니 고치는 데 쓰지 않는다.
★재료: dev 38 의 결합 카드(`cases_dev.partial.json` — 후보 · 분류 · 설문). 카드마다 이길 속성 A 와, 후보 중 A 가 아닌 곳이
  가진 다른 속성 B 를 골라 세 꼴의 문장을 만든다(문장은 기계 생성 — dev 라 사람 문장이 아니어도 된다).
  - `or`     「A 아니면 B 같은 데로」 — A · B 둘 다 허용. 거꾸로 읽으면 A 를 피한다
  - `refuse` 「B 말고 A 쪽으로」 — A 허용, B(이면서 A 아님)는 위험(고객이 거부한 유형)
  - `or_anim` 「A 아님 B 같은 데로」 — 구어 「아님」(= 아니면). `[2026-10-21]` holdout-4 M-63 「박물관 아님 전시로」를 거꾸로 읽은 뒤 더했다
    (`--only or_anim --out cases_dev_stress_anim.jsonl` — 앞 54건 파일은 그대로 둔다)
  - `trap`   「조용한 A 곳으로」 — A 허용. 「조용」은 후보 정보에 없다 → 이유에서 조용하다고 하면 지어냄(금지 주장)
★라벨: 엄격 조건 속성(`apply_review_fixes.strict_attrs`)으로 — 규칙 라벨이라 판 사이 비교용이다(전환 판정에 안 씀).
  허용이 후보 셋 전부가 되는 꼴은 고를 게 없어 뺀다.
"""
from __future__ import annotations

import json

from .build import HERE, write
from .dev import card_tools

OUT = HERE / "cases_dev_stress.jsonl"
WORD = {"indoor": "실내", "outdoor": "야외", "history": "역사 유적", "nature": "자연", "experience": "체험",
        "culture": "전시", "shopping": "쇼핑", "leisure": "레저", "night_view": "야경", "low_walking": "덜 걷는 곳",
        "stroller": "유모차 다니기 쉬운 곳"}
QUIET = ["조용", "한적", "사람이 적", "붐비지"]


def variants(card: dict, attrs) -> list[dict]:
    a = card["preference_target"]["attribute"]
    if a not in WORD:
        return []
    cands = card["candidates"]
    tags = [attrs(c) for c in cands]
    ids = [c["id"] for c in cands]
    hit = [i for i, t in zip(ids, tags) if a in t]
    if not hit:
        return []
    others = [o for t in (t for t in tags if a not in t) for o in sorted(t) if o in WORD and o != a]
    b = others[0] if others else None
    out = []
    if b:
        either = [i for i, t in zip(ids, tags) if a in t or b in t]
        if len(either) < len(ids):
            out.append(("or", f"{WORD[a]} 아니면 {WORD[b]} 같은 데로 바꿔 주세요.", either, [], []))
            out.append(("or_anim", f"{WORD[a]} 아님 {WORD[b]} 같은 데로 바꿔 주세요.", either, [], []))
        refused = [i for i, t in zip(ids, tags) if b in t and a not in t]
        out.append(("refuse", f"{WORD[b]} 말고 {WORD[a]} 쪽으로 해 주세요.", hit, refused, []))
    if len(hit) < len(ids):
        out.append(("trap", f"조용한 {WORD[a]} 곳으로 부탁해요.", hit, [], QUIET))
    return [{"kind": k, "text": text, "acceptable": acc, "forbidden": forb, "claims": claims, "b": b}
            for k, text, acc, forb, claims in out]


def build_cases(only: set[str] | None = None) -> tuple[list[dict], dict]:
    fixes, _ = card_tools()
    bound = json.loads((HERE / "cases_dev.partial.json").read_text(encoding="utf-8"))["bound"]
    cases, counts = [], {}
    for cid in sorted(bound, key=lambda x: int(x[2:])):
        card = bound[cid]
        for v in variants(card, fixes.strict_attrs):
            if (only or {"or", "refuse", "trap"}) and v["kind"] not in (only or {"or", "refuse", "trap"}):
                continue
            counts[v["kind"]] = counts.get(v["kind"], 0) + 1
            cases.append({
                "case_id": f"{cid.replace('L-', 'S-')}-{v['kind']}", "kind": "alternative_pick", "split": "dev",
                "stratum": card["stratum"], "stress": v["kind"],
                "inputs": {"origin": card["origin"]["title"], "at": card["at"],
                           "candidates": [{"id": c["id"], "title": c["title"], "code_reason": c["code_reason"],
                                           "distance_km": c["distance_km"], "class": c["class"]} for c in card["candidates"]],
                           "preference": {"survey": card["survey"], "customer_text": v["text"]}},
                "acceptable": v["acceptable"], "forbidden": v["forbidden"], "no_fit": False, "expects_code_order": False,
                "forbidden_claims": v["claims"],
                "rationale": f"{card['preference_target']['attribute']} · {v['kind']} · B={v['b']}",
                "label_by": "rule:strict_attrs(stress) — 사람 검토 전", "text_by": "stress-template", "from_card": cid,
            })
    return cases, counts


#: ★`[2026-10-21]` 「전시 ≠ 공연」 — holdout-4 M-21 「미술 전시 같은 걸로」에 공연장을 「전시에 맞는」 곳이라 했다(경미 5건).
#:  dev 카드 중 전시시설(VE07) 후보가 있는 9장에 공연장(VE06) 하나를 **코드 1순위 자리**에 넣고(섞음 — 거리 · 이유는 그 공연장의 것),
#:  공연장 · 도서관 · 공원만 있는 4장은 그대로 둔다(맞는 후보 없음). 모두 같은 문장 「미술 전시 같은 걸로 바꿔 주세요.」
EXHIBIT_TEXT = "미술 전시 같은 걸로 바꿔 주세요."


def build_exhibit_cases() -> tuple[list[dict], dict]:
    bound = json.loads((HERE / "cases_dev.partial.json").read_text(encoding="utf-8"))["bound"]
    order = sorted(bound, key=lambda x: int(x[2:]))
    venues = [c for cid in order for c in bound[cid]["candidates"] if (c["class"] or "").startswith("VE06")]
    cases, counts, v = [], {"exhibit_mixed": 0, "exhibit_none": 0}, 0
    for cid in order:
        card = bound[cid]
        cands = card["candidates"]
        if any((c["class"] or "").startswith("VE07") for c in cands):
            swap = next(i for i, c in enumerate(cands) if not (c["class"] or "").startswith("VE07"))                 if any(not (c["class"] or "").startswith("VE07") for c in cands) else 0
            rest = [c for i, c in enumerate(cands) if i != swap]
            cands, kind = [venues[v % len(venues)], *rest], "exhibit_mixed"
            v += 1
        elif any((c["class"] or "").startswith("VE06") for c in cands):
            kind = "exhibit_none"
        else:
            continue
        counts[kind] += 1
        acceptable = [c["id"] for c in cands if (c["class"] or "").startswith("VE07")]
        cases.append({
            "case_id": f"{cid.replace('L-', 'S-')}-{kind}", "kind": "alternative_pick", "split": "dev",
            "stratum": card["stratum"], "stress": kind,
            "inputs": {"origin": card["origin"]["title"], "at": card["at"],
                       "candidates": [{"id": c["id"], "title": c["title"], "code_reason": c["code_reason"],
                                       "distance_km": c["distance_km"], "class": c["class"]} for c in cands],
                       "preference": {"survey": card["survey"], "customer_text": EXHIBIT_TEXT}},
            "acceptable": acceptable, "forbidden": [], "no_fit": not acceptable, "expects_code_order": False,
            "forbidden_claims": [], "rationale": f"전시(VE07)만 허용 · 공연장(VE06)은 전시가 아니다 · {kind}",
            "label_by": "rule:VE07(stress) — 사람 검토 전", "text_by": "stress-template", "from_card": cid,
        })
    return cases, counts


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", help="이 꼴만(예: or_anim). 기본은 앞 54건과 같은 or · refuse · trap")
    parser.add_argument("--out", help="출력 파일 이름(기본 cases_dev_stress.jsonl)")
    args = parser.parse_args(argv)
    out = HERE / args.out if args.out else OUT
    if out.exists():
        raise SystemExit(f"{out.name} 가 이미 있다 — 덮어쓰지 않는다")
    if args.only == ["exhibit"]:
        cases, counts = build_exhibit_cases()
    else:
        cases, counts = build_cases(set(args.only) if args.only else None)
    manifest = write(cases, out, {"labeler": "rule:strict_attrs(stress)", "texts": "stress-template", "smoke": False,
                                  "stress": counts, "from": "cases_dev.partial.json(dev 38 결합 카드)"})
    print(json.dumps({k: manifest[k] for k in ("cases", "by_stratum", "sha256")} | {"stress": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
