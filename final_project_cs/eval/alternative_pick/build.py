# -*- coding: utf-8 -*-
"""대체 후보 1순위 판정 평가 사례 — 상황 카드(결합본)를 채점용 사례로 바꾸고 해시를 매니페스트에 적는다.

    python -m eval.alternative_pick.build                      # holdout 80: 작성자 문장 + 합의 라벨
    python -m eval.alternative_pick.build --labels 라벨.json    # 라벨 파일(human_review 형식)을 지정
    python -m eval.alternative_pick.build --smoke               # 도구 점검용: 템플릿 문장 + 분류 태그 초안 라벨
    python -m eval.alternative_pick.build --watch --watch-labels 라벨.json   # 감시 경로 판(고객 문장 없음) — `watch.py`
    python -m eval.alternative_pick.build --watch --draft        # 감시 판 도구 점검용(사람 라벨 자리를 셋 다 허용으로)

계획: `docs/activity/대체 후보 3곳 중 최적 장소 판정 — LLM 테스트 계획.md` §3.
★사례 하나 = 카드 하나. `inputs` 는 운영 코드가 LLM 에 넘기는 재료(원래 장소 · 후보 3곳 코드 순서 · 설문 · 고객 문장)뿐이다.
  `acceptable` · `forbidden` 은 후보 id. 라벨 시트는 번호(1 · 2 · 3, 코드 순서)로 받으므로 여기서 id 로 바꾼다.
★`--smoke` 는 **수치로 쓰지 않는다.** holdout 카드의 후보에 템플릿 문장을 붙인 것이라, 이것으로 프롬프트를 고치면
  holdout 후보를 본 셈이 된다(계획서 §3 과적합 방지). 실행 · 채점 경로가 도는지만 본다.
★매니페스트는 해시를 둘 적는다 — `inputs_sha256`(LLM 이 받는 것)과 `sha256`(라벨 포함 전체). 실행 뒤 라벨만 고쳐
  다시 채점할 수 있게, 채점은 입력 해시만 실행 기록과 맞춘다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = HERE.parent / "situation_cards"
BOUND = CARDS / "cards_llm_bound_v0.jsonl"
RESPONSES = CARDS / "responses_llm_bound_v0.csv"
TEXT_COL = "고객이 보낼 말(1~2문장)"
DATASET = HERE / "cases.jsonl"
SMOKE = HERE / "cases_smoke.jsonl"
WATCH = HERE / "cases_watch.jsonl"
WATCH_DRAFT = HERE / "cases_watch_draft.jsonl"
#: ★`[2026-10-20]` 자료 묶음 — v0 = holdout 80, h2 = holdout-2(`holdout2.py`). (결합본, 작성자 문장, 고객 요청 판, 감시 판, 라벨 묶음 접미사)
SETS = {
    "v0": (BOUND, RESPONSES, DATASET, WATCH, ""),
    "h2": (CARDS / "cards_llm_bound_h2.jsonl", CARDS / "responses_llm_bound_h2.csv", HERE / "cases_h2.jsonl",
           HERE / "cases_watch_h2.jsonl", "_h2"),
    "h3": (CARDS / "cards_llm_bound_h3.jsonl", CARDS / "responses_llm_bound_h3.csv", HERE / "cases_h3.jsonl",
           HERE / "cases_watch_h3.jsonl", "_h3"),
    #: ★`[2026-10-21]` holdout-4 — 고객 요청 경로만(감시 경로는 h2 · h3 에서 통과)
    "h4": (CARDS / "cards_llm_bound_h4.jsonl", CARDS / "responses_llm_bound_h4.csv", HERE / "cases_h4.jsonl",
           HERE / "cases_watch_h4.jsonl", "_h4"),
}


def manifest_path(dataset: Path) -> Path:
    return dataset.with_name(dataset.stem + ".manifest.json")


def template_text(card: dict) -> str:
    """`--smoke` 문장 — 묶음 · 이길 속성 · 금지 주장에서 기계로 만든다(사람 문장의 대역)."""
    target = card["preference_target"]
    claims = card.get("forbidden_claims") or []
    stratum = card["stratum"]
    if stratum == "A":
        return "다른 곳으로 바꿔 주세요."
    if stratum == "E":
        return f"{claims[0] if claims else '후기'} 좋은 곳으로 골라 주세요."
    if stratum == "F":
        return f"목록 말고 {claims[0] if claims else '롯데월드'}로 해 주세요."
    if target.get("cue_source") == "survey":
        return "다른 곳으로 바꿔 주세요."            # 단서는 설문에만 있다
    return f"오늘은 {target['label']} 쪽으로 바꿔 주세요."


def numbers_to_ids(numbers: list[str], ids: list[str]) -> list[str]:
    return [ids[int(n) - 1] for n in numbers]


def to_case(card: dict, text: str, acceptable: list[str], forbidden: list[str], *, split: str,
            label_by: str, text_by: str, no_fit: bool = False) -> dict:
    return {
        "case_id": card["card_id"], "kind": "alternative_pick", "split": split, "stratum": card["stratum"],
        "inputs": {
            "origin": card["origin"]["title"], "at": card["at"],
            "candidates": [{"id": c["id"], "title": c["title"], "code_reason": c["code_reason"],
                            "distance_km": c["distance_km"], "class": c["class"]} for c in card["candidates"]],
            "preference": {"survey": card.get("survey") or {}, "customer_text": text},
        },
        "acceptable": acceptable, "forbidden": forbidden,
        # ★`[2026-10-19 A안]` 고객이 바란 곳이 후보에 없다(라벨 「없음」) — M1 참고값의 분모에서 뺀다. M2 · M5 에는 그대로 든다
        "no_fit": no_fit,
        # ★단서 없음(A) — M4 「코드 순서를 지켰나」 의 분모
        "expects_code_order": card["expected_behavior"] == "keep_code_order",
        "forbidden_claims": card.get("forbidden_claims") or [],
        "rationale": f"{card['preference_target']['label']} ({card['preference_target']['cue_source']})",
        "label_by": label_by, "text_by": text_by,
        # ★`[2026-10-17]` 작성자를 바꾼 카드(L-01 · L-55) — 새 작성자가 문장을 쓰기 전에 후보를 봤다. 분석에서 가려 볼 수 있게
        "writer_saw_candidates": bool(card.get("writer_saw_candidates")),
        # ★`[2026-10-20]` holdout-2 의 일부 카드는 운영 화면 3곳이 아니라 운영 순위 상위 10곳에서 골랐다(`holdout2.bind_top10`)
        **({"candidates_by": card["candidates_by"]} if card.get("candidates_by") else {}),
    }


def load_cards(path: Path = BOUND) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cards_as_chat_cases(path: Path) -> list[dict]:
    """결합본 카드 → 고객 문장 없는 사례(라벨 비움). 감시 판(`watch.variants`)의 재료 — 고객 요청 판 라벨을 기다리지 않는다."""
    return [to_case(card, None, [], [], split="holdout", label_by=None, text_by="none") for card in load_cards(path)]


def load_texts(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {r["카드"]: r[TEXT_COL].strip() for r in csv.DictReader(fh)}


def load_labels(path: Path, bundle: str = "situation_cards") -> tuple[dict[str, dict], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("bundle") != bundle:
        raise SystemExit(f"{path}: {bundle} 라벨 파일이 아니다(bundle={data.get('bundle')!r})")
    return data["labels"], data["reviewer"]


def build(cards: list[dict], *, smoke: bool, texts: dict[str, str] | None = None,
          labels: dict[str, dict] | None = None, labeler: str = "") -> list[dict]:
    cases = []
    missing: list[str] = []
    for card in cards:
        ids = [c["id"] for c in card["candidates"]]
        if smoke:
            cases.append(to_case(card, template_text(card), list(card.get("acceptable_draft") or []), [],
                                 split="smoke", label_by="auto-tag-draft", text_by="template"))
            continue
        cid = card["card_id"]
        if cid not in (texts or {}) or cid not in (labels or {}):
            missing.append(cid)
            continue
        entry = labels[cid]
        cases.append(to_case(card, texts[cid], numbers_to_ids(entry.get("acceptable", []), ids),
                             numbers_to_ids(entry.get("forbidden", []), ids),
                             split="holdout", label_by=labeler, text_by="writer", no_fit=bool(entry.get("no_fit"))))
    if missing:
        raise SystemExit(f"문장 또는 라벨이 없는 카드 {len(missing)}장: {', '.join(missing[:10])}…")
    return cases


def inputs_digest(cases: list[dict]) -> str:
    """LLM 이 받는 것만 — 라벨이 바뀌어도 같은 값이다."""
    body = "".join(json.dumps({"case_id": c["case_id"], "inputs": c["inputs"]}, ensure_ascii=False, sort_keys=True)
                   + "\n" for c in cases)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write(cases: list[dict], dataset: Path, extra: dict) -> dict:
    text = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases)
    dataset.write_text(text, encoding="utf-8")
    by_stratum: dict[str, int] = {}
    for c in cases:
        by_stratum[c["stratum"]] = by_stratum.get(c["stratum"], 0) + 1
    manifest = {
        "built_on": date.today().isoformat(), "cases": len(cases), "by_stratum": dict(sorted(by_stratum.items())),
        "split": sorted({c["split"] for c in cases}), "source": BOUND.name,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "inputs_sha256": inputs_digest(cases), **extra,
    }
    manifest_path(dataset).write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


def load_cases(dataset: Path) -> tuple[list[dict], dict]:
    """사례와 매니페스트 — 해시가 다르면 멈춘다(다른 데이터로 낸 수치를 같은 이름으로 싣지 않는다)."""
    text = dataset.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path(dataset).read_text(encoding="utf-8"))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != manifest["sha256"]:
        raise SystemExit(f"{dataset.name} 해시가 매니페스트와 다르다({digest[:12]} ≠ {manifest['sha256'][:12]}) — build 를 다시 돌린다")
    return [json.loads(line) for line in text.splitlines() if line.strip()], manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="템플릿 문장 + 분류 태그 초안 라벨(도구 점검용 — 수치로 쓰지 않음)")
    parser.add_argument("--responses", type=Path, default=RESPONSES, help="작성자 문장(review_sheets.py merge 결과)")
    parser.add_argument("--labels", type=Path, help="합의 라벨 파일(human_review apply 형식, bundle=situation_cards)")
    parser.add_argument("--watch", action="store_true", help="감시 경로 판 — 동결 holdout 에서 고객 문장을 뺀다")
    parser.add_argument("--watch-labels", type=Path, help="감시 판 사람 라벨(human_review apply 형식, bundle=situation_cards_watch)")
    parser.add_argument("--draft", action="store_true", help="--watch 와 함께 — 사람 라벨 없이 도구만 점검(수치로 쓰지 않음)")
    parser.add_argument("--set", choices=tuple(SETS), default="v0", help="h2 = holdout-2(`holdout2.py` 결합본)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    bound, responses, dataset, _, suffix = SETS[args.set]
    if args.set != "v0" and args.responses == RESPONSES:
        args.responses = responses

    if args.watch:
        build_watch(args)
        return
    cards = load_cards(bound)
    if args.smoke:
        cases = build(cards, smoke=True)
        out = args.out or SMOKE
        extra = {"labeler": "auto-tag-draft — 사람 검토 전", "texts": "template", "smoke": True}
    else:
        if not args.responses.exists():
            raise SystemExit(f"{args.responses} 가 없다 — 작성자 문장을 먼저 합친다(review_sheets.py merge)")
        if args.labels is None:
            raise SystemExit("--labels 합의 라벨 파일을 지정한다(2인 라벨 → agree → 합의본)")
        labels, reviewer = load_labels(args.labels, f"situation_cards{suffix}")
        cases = build(cards, smoke=False, texts=load_texts(args.responses), labels=labels, labeler=reviewer)
        out = args.out or dataset
        extra = {"labeler": reviewer, "labels_file": args.labels.name, "texts": args.responses.name, "smoke": False,
                 "set": args.set, "source": bound.name}
    manifest = write(cases, out, extra)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


def build_watch(args) -> None:
    """감시 경로 판 — 동결 holdout 의 입력을 그대로 쓰고 고객 문장만 뺀다(`watch.py`)."""
    from . import watch

    bound, _, dataset, watch_out, suffix = SETS[args.set]
    if args.set == "v0":
        chat, chat_manifest = load_cases(dataset)
        source = {"dataset": dataset.name, "sha256": chat_manifest["sha256"]}
    else:
        chat = cards_as_chat_cases(bound)
        source = {"bound": bound.name, "sha256": hashlib.sha256(bound.read_bytes()).hexdigest()}
    cases, counts = watch.variants(chat)
    if args.draft:
        cases = [{**c, "split": "smoke", "acceptable": [x["id"] for x in c["inputs"]["candidates"]],
                  "label_by": "auto-tag-draft"} for c in cases]
        out, labeler = args.out or WATCH_DRAFT, "draft — 사람 라벨 전(셋 다 허용으로 채움)"
    else:
        if args.watch_labels is None:
            raise SystemExit("--watch-labels 감시 판 합의 라벨을 지정한다(또는 --draft 로 도구만 점검)")
        data = json.loads(args.watch_labels.read_text(encoding="utf-8"))
        if data.get("bundle") != f"situation_cards_watch{suffix}":
            raise SystemExit(f"{args.watch_labels}: situation_cards_watch{suffix} 라벨 파일이 아니다(bundle={data.get('bundle')!r})")
        human = {cid: entry for cid, entry in data["labels"].items()}
        cases, out, labeler = watch.label(cases, human, data["reviewer"]), args.out or watch_out, data["reviewer"]
    manifest = write(cases, out, {
        "path": "watch", "set": args.set, "from": source,
        "labeler": labeler, "labels_file": args.watch_labels.name if args.watch_labels else None,
        "texts": "없음(감시 경로 — customer_text=None)", "smoke": bool(args.draft),
        "watch": counts,
    })
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
