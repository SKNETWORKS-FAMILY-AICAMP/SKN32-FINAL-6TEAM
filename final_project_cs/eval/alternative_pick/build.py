# -*- coding: utf-8 -*-
"""대체 후보 1순위 판정 평가 사례 — 상황 카드(결합본)를 채점용 사례로 바꾸고 해시를 매니페스트에 적는다.

    python -m eval.alternative_pick.build                      # holdout 80: 작성자 문장 + 합의 라벨
    python -m eval.alternative_pick.build --labels 라벨.json    # 라벨 파일(human_review 형식)을 지정
    python -m eval.alternative_pick.build --smoke               # 도구 점검용: 템플릿 문장 + 분류 태그 초안 라벨

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
            label_by: str, text_by: str) -> dict:
    return {
        "case_id": card["card_id"], "kind": "alternative_pick", "split": split, "stratum": card["stratum"],
        "inputs": {
            "origin": card["origin"]["title"], "at": card["at"],
            "candidates": [{"id": c["id"], "title": c["title"], "code_reason": c["code_reason"],
                            "distance_km": c["distance_km"], "class": c["class"]} for c in card["candidates"]],
            "preference": {"survey": card.get("survey") or {}, "customer_text": text},
        },
        "acceptable": acceptable, "forbidden": forbidden,
        # ★단서 없음(A) — M4 「코드 순서를 지켰나」 의 분모
        "expects_code_order": card["expected_behavior"] == "keep_code_order",
        "forbidden_claims": card.get("forbidden_claims") or [],
        "rationale": f"{card['preference_target']['label']} ({card['preference_target']['cue_source']})",
        "label_by": label_by, "text_by": text_by,
        # ★`[2026-10-17]` 작성자를 바꾼 카드(L-01 · L-55) — 새 작성자가 문장을 쓰기 전에 후보를 봤다. 분석에서 가려 볼 수 있게
        "writer_saw_candidates": bool(card.get("writer_saw_candidates")),
    }


def load_cards() -> list[dict]:
    return [json.loads(line) for line in BOUND.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_texts(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {r["카드"]: r[TEXT_COL].strip() for r in csv.DictReader(fh)}


def load_labels(path: Path) -> tuple[dict[str, dict], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("bundle") != "situation_cards":
        raise SystemExit(f"{path}: situation_cards 라벨 파일이 아니다(bundle={data.get('bundle')!r})")
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
                             split="holdout", label_by=labeler, text_by="writer"))
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
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    cards = load_cards()
    if args.smoke:
        cases = build(cards, smoke=True)
        out = args.out or SMOKE
        extra = {"labeler": "auto-tag-draft — 사람 검토 전", "texts": "template", "smoke": True}
    else:
        if not args.responses.exists():
            raise SystemExit(f"{args.responses} 가 없다 — 작성자 문장을 먼저 합친다(review_sheets.py merge)")
        if args.labels is None:
            raise SystemExit("--labels 합의 라벨 파일을 지정한다(2인 라벨 → agree → 합의본)")
        labels, reviewer = load_labels(args.labels)
        cases = build(cards, smoke=False, texts=load_texts(args.responses), labels=labels, labeler=reviewer)
        out = args.out or DATASET
        extra = {"labeler": reviewer, "labels_file": args.labels.name, "texts": args.responses.name, "smoke": False}
    manifest = write(cases, out, extra)
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
