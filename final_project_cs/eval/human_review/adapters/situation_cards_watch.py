# -*- coding: utf-8 -*-
"""상황 카드 감시 경로 판 — 고객 문장 없이 설문만 보고 다는 2인 블라인드 라벨(`acceptable` · `forbidden`). `[2026-10-19]`

원본: 동결 holdout `eval/alternative_pick/cases.jsonl` → `eval.alternative_pick.watch.variants` 가 고른 `human` 사례
(취향 설문이 있어 감시 경로에서도 LLM 을 부르는 카드). 우선순위만 있는 카드는 규칙 라벨이라 시트에 없다.
- 시트: **LLM 이 받는 입력만** — 원래 장소 · 방문 시각 · 설문(priority 뺌) · 후보 3곳(코드 순서). 고객 문장은 없다(감시 경로).
- 답은 후보 번호(1 · 2 · 3). 고른 것을 `build --watch --watch-labels` 가 id 로 바꾼다.
- 고객 문장 판(`situation_cards`)과 같은 카드다 — 그 판의 라벨을 보고 달지 않는다(고객 말이 없으면 정답이 바뀐다).
"""
from __future__ import annotations

from ..core import Bundle, Field, Item
from .paths import Sources
from .situation_cards import NO_FIT, NUMBERS, _check_overlap

CRITERIA = (
    "고객 문장이 없다 — 감시가 먼저 찾아낸 일이라 고객은 아직 아무 말도 하지 않았다. 설문만 보고 단다. "
    "후보 중 1순위로 나와도 정답인 곳(acceptable)과 1순위로 나오면 위험한 곳(forbidden · 없으면 비움)을 번호로 적는다. "
    "설문 항목끼리는 순서가 없다 — 설문 단서를 더 많이 만족하는 후보가 정답, 같으면 모두 허용. "
    f"설문에 맞는 곳이 후보에 하나도 없으면 정답 칸에 「{NO_FIT}」만 적는다. "
    "위험은 그 시각에 못 가는 곳뿐이다(고객이 거부한 말이 없으므로 취향과 다른 곳은 차선이지 위험이 아니다). "
    "바깥 지식으로 판단하지 않는다(계획서 1-1 · 1-2)."
)


def build(src: Sources | None = None, set_name: str = "v0") -> Bundle:
    from eval.alternative_pick import watch
    from eval.alternative_pick.build import DATASET, load_cases
    from eval.situation_cards import review_sheets as rs

    src = src or Sources()
    if set_name == "v0":
        dataset = src.need(src.cs / "eval" / "alternative_pick" / DATASET.name, "동결 holdout 사례(cases.jsonl)")
        chat, _ = load_cases(dataset)
    else:
        # ★`[2026-10-20]` holdout-2 — 감시 판은 고객 문장이 필요 없어 결합본 카드에서 바로 만든다(고객 요청 판 라벨과 따로 단다)
        from eval.alternative_pick.build import cards_as_chat_cases

        bound = src.need(src.cs / "eval" / "situation_cards" / rs.SETS[set_name][0], "holdout-2 결합본")
        chat = cards_as_chat_cases(bound)
    cases, _ = watch.variants(chat)
    items = []
    for c in cases:
        if c["watch_kind"] != "human":
            continue
        cands = c["inputs"]["candidates"]
        ids = [x["id"] for x in cands]
        shown = [rs.candidate_text(x) for x in cands] + [""] * (3 - len(ids))
        items.append(Item(
            id=c["case_id"],
            context={"원래 장소": c["inputs"]["origin"], "방문 시각": rs.when(c["inputs"]["at"]),
                     "설문(priority 뺌)": rs.survey_text(c["inputs"]["preference"]["survey"]),
                     "후보 1": shown[0], "후보 2": shown[1], "후보 3": shown[2]},
            criteria=CRITERIA,
            allowed={"acceptable": (*NUMBERS[:len(ids)], NO_FIT), "forbidden": NUMBERS[:len(ids)]},
            meta={"ids": ids, "stratum": c["stratum"], "from_case": c["from_case"]},
        ))
    return Bundle(
        name="situation_cards_watch" if set_name == "v0" else f"situation_cards_watch_{set_name}", title="상황 카드 감시 경로 판 — 설문만 보고 1순위 허용 · 위험 라벨(2인 블라인드)",
        fields=[Field("acceptable", "1순위로 나와도 정답(번호, ; 로 구분)", "set"),
                Field("forbidden", "1순위로 나오면 위험(번호, 없으면 비움)", "set", required=False)],
        items=items,
        context_columns=["원래 장소", "방문 시각", "설문(priority 뺌)", "후보 1", "후보 2", "후보 3"],
        notes="두 사람 모두 전부를 따로 단다. 고객 문장 판(situation_cards) 라벨을 보지 않는다.",
        normalize=_check_overlap,
    )


def build_h2(src: Sources | None = None) -> Bundle:
    """`[2026-10-20]` holdout-2 감시 경로 판 — 고객 문장 없이 설문만."""
    return build(src, "h2")
