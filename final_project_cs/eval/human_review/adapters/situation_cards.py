# -*- coding: utf-8 -*-
"""상황 카드 80장 — 작성자 문장이 들어온 뒤 2인 블라인드 라벨(`acceptable` · `forbidden`).

원본: `eval/situation_cards/cards_llm_bound_v0.jsonl`(결합본) + `responses_llm_bound_v0.csv`(작성자 문장 — `review_sheets.py merge`).
- 시트: **LLM 이 받는 입력만** — 고객 문장 · 원래 장소 · 방문 시각 · 설문(priority 뺌) · 후보 3곳(코드 순서 · 이름 · 분류 · 코드 이유 · 운영).
  계획서 1-2 「라벨러는 LLM 이 받는 입력만 보고」. 상황 문장(작성자 지시문) · 묶음 · 이길 속성 · 속성 초안은 싣지 않는다.
- 답은 후보 번호(1 · 2 · 3, 코드 순서)로 적는다 — contentid 를 손으로 옮기다 틀리지 않게. 번호 → id 는 `Item.meta["ids"]`.
- AI 초안: `acceptable_draft`(분류 태그로 기계가 고른 허용 답, `auto-tag-draft`)만 — 시트에는 안 싣고 `agree --ai` 로만 견준다.
"""
from __future__ import annotations

import csv
import json

from ..core import Bundle, Field, Item
from .paths import Sources

AI_SOURCE = "auto_tag_draft"
NUMBERS = ("1", "2", "3")
#: ★`[2026-10-19 사용자 결정 A안]` 고객이 바란 곳이 후보에 하나도 없으면 정답 칸에 이 말만 적는다 → `acceptable=[]` · `no_fit=True`.
#:  빈 칸은 그대로 「덜 채움」 오류다(구별하려고 말을 적게 한다). 위험 칸은 하드 조건 위반 · 고객이 거부한 유형만이다(1-2).
NO_FIT = "없음"
CRITERIA = (
    "후보 중 1순위로 나와도 정답인 곳(acceptable · 하나 이상)과 1순위로 나오면 위험한 곳(forbidden · 없으면 비움)을 번호로 적는다. "
    f"고객이 바란 곳이 후보에 하나도 없으면 정답 칸에 「{NO_FIT}」만 적는다. 위험은 그 시각에 못 가는 곳 · 고객이 직접 거부한 유형뿐이다. "
    "이번 고객 문장의 요청 > 설문. 설문 항목끼리 갈리면 더 많이 맞는 후보, 같으면 모두 허용. "
    "고객이 바란 기준이 후보 정보에 없으면(혼잡 · 후기 · 요금 등) 순서는 무엇이든 허용. 바깥 지식으로 판단하지 않는다(계획서 1-1 · 1-2)."
)


def build(src: Sources | None = None, set_name: str = "v0") -> Bundle:
    from eval.situation_cards import review_sheets as rs

    src = src or Sources()
    folder = src.cs / "eval" / "situation_cards"
    bound_name, _, responses_name = rs.SETS[set_name]
    bound_path = src.need(folder / bound_name, "상황 카드 결합본")
    responses_path = src.need(folder / responses_name,
                              "작성자 문장(`python eval/situation_cards/review_sheets.py merge …` 로 만든다)")
    cards = {(c := json.loads(line))["card_id"]: c for line in bound_path.open(encoding="utf-8")}
    with responses_path.open(encoding="utf-8-sig", newline="") as fh:
        responses = list(csv.DictReader(fh))
    items = []
    for r in responses:
        c = cards[r["카드"]]
        ids = [x["id"] for x in c["candidates"]]
        numbers = NUMBERS[:len(ids)]
        shown = [rs.candidate_text(x) for x in c["candidates"]] + [""] * (3 - len(ids))
        draft = [str(ids.index(i) + 1) for i in c.get("acceptable_draft", []) if i in ids]
        items.append(Item(
            id=c["card_id"],
            context={"고객 문장": r[rs.TEXT_COL], "원래 장소": c["origin"]["title"], "방문 시각": rs.when(c["at"]),
                     "설문(priority 뺌)": rs.survey_text(c["survey"]),
                     "후보 1": shown[0], "후보 2": shown[1], "후보 3": shown[2]},
            criteria=CRITERIA,
            allowed={"acceptable": (*numbers, NO_FIT), "forbidden": numbers},
            ai={AI_SOURCE: {"acceptable": draft, "forbidden": []}} if draft else {},
            meta={"ids": ids, "stratum": c["stratum"], "writer": r["작성자"]},
        ))

    def by_writer(name: str):
        return lambda: [it.id for it in items if it.meta["writer"] == name]

    writers = sorted({it.meta["writer"] for it in items})
    return Bundle(
        name="situation_cards" if set_name == "v0" else f"situation_cards_{set_name}",
        title=(f"상황 카드 {len(items)}장{'' if set_name == 'v0' else f' · holdout-{set_name[1:]}'} — 대체 후보 1순위 허용 · 위험 라벨(2인 블라인드)"),
        fields=[Field("acceptable", "1순위로 나와도 정답(번호, ; 로 구분)", "set"),
                Field("forbidden", "1순위로 나오면 위험(번호, 없으면 비움)", "set", required=False)],
        items=items,
        context_columns=["고객 문장", "원래 장소", "방문 시각", "설문(priority 뺌)", "후보 1", "후보 2", "후보 3"],
        notes="두 사람 모두 전부를 따로 단다. 같은 번호를 acceptable 과 forbidden 에 함께 적지 않는다. "
              "부분집합 writer_<작성자> 는 그 사람이 쓴 문장만.",
        subsets={f"writer_{w}": by_writer(w) for w in writers},
        normalize=_check_overlap,
    )


def _check_overlap(entry: dict) -> dict:
    from ..core import SheetError

    acceptable = entry.get("acceptable", [])
    if NO_FIT in acceptable:
        if len(acceptable) > 1:
            raise SheetError(f"「{NO_FIT}」 은 번호와 함께 적지 않는다({acceptable})")
        entry = {**entry, "acceptable": [], "no_fit": True}
    both = sorted(set(entry.get("acceptable", [])) & set(entry.get("forbidden", [])))
    if both:
        raise SheetError(f"같은 후보 {both} 가 acceptable 과 forbidden 에 함께 있다")
    return entry


def build_h2(src: Sources | None = None) -> Bundle:
    """`[2026-10-20]` holdout-2(`cards_llm_bound_h2.jsonl` + `responses_llm_bound_h2.csv`) — 고객 요청 판 라벨."""
    return build(src, "h2")


def build_h3(src: Sources | None = None) -> Bundle:
    """`[2026-10-20]` holdout-3 — 운영판(v3 + 지킴이) 판정용 고객 요청 판."""
    return build(src, "h3")


def build_h4(src: Sources | None = None) -> Bundle:
    """`[2026-10-21]` holdout-4 — 지킴이 문구를 고친 운영판의 고객 요청 경로 재판정용."""
    return build(src, "h4")


def build_h5(src: Sources | None = None) -> Bundle:
    """`[2026-10-21]` holdout-5 — 실험 지시문 v5 + 고친 지킴이의 고객 요청 경로 판정용."""
    return build(src, "h5")
