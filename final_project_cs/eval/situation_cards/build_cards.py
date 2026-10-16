# -*- coding: utf-8 -*-
"""상황 카드 초안 — LLM 60장 · 작성자 시트(블라인드).

무엇인가
- 사람이 **고객 문장**만 쓰게 하는 카드다. 카드가 상황을 정하므로 정답(키)은 카드를 만들 때 정해진다.
- LLM 카드: 고객이 바라는 성질(실내 · 역사 · 체험 …)과 단서 출처를 정답 키로 둔다. 후보 3곳은
  DB(활동 원장 `activity.ac_place`)를 켠 뒤 운영 코드(`rank_alternatives`)로 붙인다 — `binding` 이 후보 조건이다.

★`[2026-10-16]` RAG(환불 · 취소 규정) 카드는 지웠다 — RAG 테스트를 범위에서 뺐다.
★해석이 갈릴 수 있는 카드는 `needs_review` 로 표시한다.
★작성자 시트(`sheet_*.csv`)에는 상황 문장만 싣는다 — 정답 키 · 묶음을 싣지 않는다(블라인드).
★LLM 호출 없음 · DB 없음 · 난수는 고정 seed.

실행: `python eval/situation_cards/build_cards.py` (final_project_cs 에서)
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent
VERSION = "v0"
SEED = 1016
WRITERS = 4

# ── LLM 카드 ──────────────────────────────────────────────────────────────
#: ★`[2026-10-16 사용자 결정]` 설문 동행(`party`)은 접수 문항이 묻지 않아 비어 있다 — 카드 설문에 넣지 않는다.
#:  아이 · 어르신은 고객이 이번 문장에서 직접 말할 때만(2순위) 쓴다. 설문 항목끼리는 순서가 없다(계획서 1-1).
#: 속성 — `inferable` 은 후보 정보(이름 · 관광공사 분류 · 거리)만으로 라벨러가 판단할 수 있는가
ATTR = {
    "indoor": ("실내", True), "outdoor": ("야외", True), "history": ("역사 유적", True), "nature": ("자연 · 산책", True),
    "experience": ("직접 하는 체험", True), "culture": ("전시 · 공연", True), "shopping": ("쇼핑", True),
    "leisure": ("몸을 쓰는 레저", True), "night_view": ("야경 · 전망", True), "kid": ("아이와 함께 하기 좋음", False),
    "low_walking": ("많이 걷지 않음", False), "none": ("특별한 선호 없음", True),
}

TEXT_CUES = [  # (원래 장소, 시각, 바뀐 사유, 동행, 작성자에게 줄 바람, 속성)
    ("북촌한옥마을", "토요일 14:00", "비 예보로 야외 일정이 어렵다는 안내를 받았습니다", "친구 2명과", "비를 피할 수 있는 곳이면 좋겠습니다", "indoor"),
    ("서울숲", "일요일 10:00", "미세먼지가 '매우 나쁨'이라는 안내를 받았습니다", "가족 4명이", "바깥 공기를 피하고 싶습니다", "indoor"),
    ("낙산공원", "화요일 13:00", "폭염 경보가 내려졌습니다", "연인과", "시원한 실내에서 보내고 싶습니다", "indoor"),
    ("국립중앙박물관", "월요일 10:00", "가 보니 정기 휴관일이었습니다", "친구 1명과", "오전 내내 실내에만 있어서 바깥 바람을 쐬고 싶습니다", "outdoor"),
    ("경복궁", "화요일 11:00", "그날이 휴궁일이라는 걸 알았습니다", "7살 아이와", "아이가 직접 만들어 보는 체험을 하고 싶어 합니다", "experience"),
    ("남산서울타워", "수요일 15:00", "전망대가 점검 중이라는 안내를 받았습니다", "부모님과", "부모님이 옛 궁궐이나 역사 유적을 좋아하십니다", "history"),
    ("동대문디자인플라자", "목요일 14:00", "전시 교체로 문을 닫았습니다", "친구 3명과", "나무 많은 곳을 걷고 싶습니다", "nature"),
    ("광장시장", "월요일 12:00", "임시 휴무라는 공지를 봤습니다", "직장 동료와", "미술 전시 같은 걸 보고 싶습니다", "culture"),
    ("창덕궁", "월요일 10:00", "휴궁일이었습니다", "친구 2명과", "공방 같은 데서 뭔가 직접 만들어 보고 싶습니다", "experience"),
    ("하늘공원", "금요일 16:00", "강풍 주의보로 출입이 통제됐습니다", "외국인 친구와", "친구에게 줄 기념품을 사고 싶습니다", "shopping"),
    ("서울식물원", "월요일 10:00", "휴관일이었습니다", "운동 좋아하는 친구와", "몸을 움직이는 활동을 하고 싶습니다", "leisure"),
    ("경복궁 야간관람", "토요일 19:00", "표가 매진됐습니다", "연인과", "밤에 야경을 볼 수 있는 곳이면 좋겠습니다", "night_view"),
    ("북한산 둘레길", "일요일 09:00", "호우 주의보가 내려졌습니다", "70대 부모님과", "부모님 무릎이 안 좋아 많이 걷지 않는 곳이 좋습니다", "low_walking"),
    ("낙산성곽길", "토요일 10:00", "공사로 길 일부가 막혔습니다", "유모차를 끄는 가족이", "유모차로 다니기 쉬운 곳이 좋겠습니다", "low_walking"),
    ("리버시티수상스키장", "일요일 14:00", "강풍으로 운영이 취소됐습니다", "외국인 친구와", "한국 전통 문화를 보여 주고 싶습니다", "history"),
    ("어린이대공원", "토요일 11:00", "비가 많이 온다는 예보가 있습니다", "5살 아이와", "아이가 지쳐서 실내에서 쉬엄쉬엄 놀았으면 합니다", "indoor"),
]

SURVEY_ONLY = [  # (원래 장소, 시각, 사유, 설문, 속성)
    ("서울숲", "토요일 10:00", "비 예보가 있습니다", {"indoor_outdoor": {"activity": "indoor"}}, "indoor"),
    ("롯데월드타워 전망대", "일요일 15:00", "점검으로 닫았습니다", {"theme": "역사"}, "history"),
    ("국립현대미술관", "월요일 11:00", "휴관일입니다", {"theme_details": ["체험"]}, "experience"),
    ("남산공원", "수요일 14:00", "폭염 경보가 내려졌습니다", {"theme_details": ["전시 관람"]}, "culture"),
    ("코엑스몰", "목요일 13:00", "정전으로 일부 구역이 닫혔습니다", {"theme": "자연"}, "nature"),
    ("덕수궁", "월요일 10:00", "휴궁일입니다", {"custom_answers": {"활동": "전시 보는 걸 좋아해요"}}, "culture"),
    ("리버시티수상스키장", "토요일 13:00", "강풍으로 운영이 취소됐습니다", {"theme": "역사"}, "history"),
    ("국립중앙박물관", "월요일 10:00", "휴관일입니다", {"indoor_outdoor": {"activity": "outdoor"}}, "outdoor"),
]

CONFLICTS = [  # (원래 장소, 사유, 설문, 오늘의 바람, 이기는 속성, 지는 속성)
    ("서울숲", "비 예보가 있습니다", {"indoor_outdoor": {"activity": "outdoor"}, "theme": "자연"}, "오늘은 비가 오니 실내로 가고 싶습니다", "indoor", "outdoor"),
    ("경복궁", "휴궁일입니다", {"theme": "역사"}, "아이가 역사는 지루해해서 오늘은 체험 같은 걸 하고 싶습니다", "experience", "history"),
    ("국립중앙박물관", "휴관일입니다", {"indoor_outdoor": {"activity": "indoor"}}, "날씨가 너무 좋아서 오늘은 밖에 있고 싶습니다", "outdoor", "indoor"),
    ("명동", "행사로 너무 붐빕니다", {"theme": "쇼핑"}, "오늘은 쇼핑 말고 조용히 전시를 보고 싶습니다", "culture", "shopping"),
    ("하늘공원", "강풍으로 통제됐습니다", {"theme": "자연"}, "일행이 발목을 다쳐서 많이 걷지 않는 곳이 좋겠습니다", "low_walking", "nature"),
    ("북촌전통공예체험관", "예약이 마감됐습니다", {"theme_details": ["체험"]}, "오늘은 뭘 만들기보다 그냥 구경만 하고 싶습니다", "culture", "experience"),
    ("어린이대공원", "비 예보가 있습니다", {"theme": "자연"}, "오늘은 어른 둘이서 역사 유적에 가고 싶습니다", "history", "nature"),
    ("리버시티수상스키장", "강풍으로 취소됐습니다", {"theme": "레저"}, "너무 피곤해서 오늘은 앉아서 보는 실내 공연이나 전시가 좋겠습니다", "culture", "leisure"),
    ("동대문디자인플라자", "전시 교체로 닫았습니다", {"indoor_outdoor": {"activity": "any"}, "theme": "문화"}, "바깥 산책을 하고 싶습니다", "nature", "culture"),
    ("인사동 쌈지길", "임시 휴무입니다", {"custom_answers": {"활동": "사진 찍기 좋은 곳"}}, "사진은 이미 많이 찍어서 오늘은 역사 공부가 되는 곳이 좋겠습니다", "history", "night_view"),
]

TIES = [  # 같은 속성 후보가 둘 — 허용 답 2곳
    ("북촌한옥마을", "비 예보가 있습니다", "비를 피할 수 있는 실내면 어디든 좋습니다", "indoor"),
    ("남산서울타워", "점검 중입니다", "궁궐 같은 역사 유적이면 좋겠습니다", "history"),
    ("코엑스 아쿠아리움", "정전으로 닫았습니다", "공원이나 숲길을 걷고 싶습니다", "nature"),
    ("국립중앙박물관", "휴관일입니다", "직접 해 보는 체험이면 좋겠습니다", "experience"),
    ("광장시장", "임시 휴무입니다", "전시나 공연을 보고 싶습니다", "culture"),
    ("서울숲", "미세먼지가 매우 나쁩니다", "실내에서 놀 수 있으면 됩니다", "indoor"),
]

TRAPS = [  # 입력에 없는 정보 요구 — 지어내지 않아야 한다
    ("가장 싼 곳으로 해 주세요", ["원", "무료", "저렴", "입장료"]),
    ("덜 붐비는 곳으로 바꿔 주세요", ["한산", "붐비지 않", "혼잡", "사람이 적"]),
    ("후기 좋은 곳으로 골라 주세요", ["후기", "평점", "리뷰", "인기"]),
    ("주차하기 편한 곳이면 좋겠어요", ["주차"]),
    ("입장료 없는 곳으로 해 주세요", ["무료", "입장료", "원"]),
    ("지금 줄 안 서고 바로 들어갈 수 있는 곳이요", ["대기", "줄", "바로 입장"]),
    ("요즘 SNS에서 인기 많은 곳으로요", ["인기", "SNS", "핫플"]),
    ("와이파이 잘 되는 곳이면 좋겠어요", ["와이파이", "wifi"]),
]

OUT_OF_LIST = [
    "목록 말고 롯데월드로 바꿔 주세요",
    "원래 가려던 곳을 그냥 내일로 미뤄 주세요",
    "보여 준 곳 말고 다른 데 추천해 주세요",
    "세 곳 다 마음에 안 들어요",
    "강남 쪽 아무 데나 다른 곳으로 해 주세요",
    "후보에 없는 남산타워로 가고 싶어요",
]

NO_CUE = [
    "다른 곳으로 바꿔 주세요", "아무 데나 괜찮아요", "가까운 곳이면 돼요",
    "알아서 정해 주세요", "추천해 준 순서대로 갈게요", "네, 바꿔 주세요",
]
NO_CUE_ORIGINS = [("경복궁", "휴궁일입니다"), ("서울숲", "비 예보가 있습니다"), ("남산서울타워", "점검 중입니다"),
                  ("국립중앙박물관", "휴관일입니다"), ("광장시장", "임시 휴무입니다"), ("하늘공원", "강풍으로 통제됐습니다")]


def llm_cards(rng: random.Random) -> list[dict]:
    cards: list[dict] = []

    def add(stratum, situation, survey, target, behavior, binding, *, forbidden=None, hint=None, note=""):
        attr = target.get("attribute", "none")
        cards.append({
            "card_id": f"L-{len(cards) + 1:02d}", "kind": "llm", "stratum": stratum, "situation": situation,
            "writer_hint": hint or "", "origin_hint": target.pop("origin"), "survey": survey,
            "preference_target": {**target, "label": ATTR[attr][0], "inferable": ATTR[attr][1]},
            "expected_behavior": behavior, "binding": binding, "forbidden_claims": forbidden or [],
            "needs_review": note or ("" if ATTR[attr][1] else "후보 이름 · 분류만으로 판단이 갈릴 수 있음 — 2인 라벨 필수"),
            "label_by": "card-draft",
        })

    reorder = {"need_match": 1, "need_nonmatch": 1, "code_first_matches": False}
    # A. 단서 없음 (6)
    for (origin, why), text in zip(NO_CUE_ORIGINS, NO_CUE):
        add("A", f"서울 여행 중 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"특별히 바라는 것은 없습니다. 챗봇에게 바꿔 달라는 말을 써 주세요.",
            {}, {"origin": origin, "cue_source": "none", "attribute": "none"}, "keep_code_order",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None}, hint=f"예: 「{text}」처럼 취향 없이")
    # B. 고객 문장 단서 (16)
    for origin, when, why, party, want, attr in TEXT_CUES:
        add("B", f"{party} 서울 여행 중입니다. {when}에 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"{want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            {}, {"origin": origin, "cue_source": "customer_text", "attribute": attr}, "reorder_to_match", dict(reorder))
    # B. 설문만 단서 (8)
    for origin, when, why, survey, attr in SURVEY_ONLY:
        add("B", f"서울 여행 중입니다. {when}에 {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 "취향은 말하지 말고 짧게 바꿔 달라고만 써 주세요.",
            survey, {"origin": origin, "cue_source": "survey", "attribute": attr}, "reorder_to_match", dict(reorder))
    # C. 단서 충돌 (10)
    for origin, why, survey, want, win, lose in CONFLICTS:
        add("C", f"서울 여행 중입니다. {origin}에 가려 했는데 {why}. 여행 전 설문에는 평소 취향을 적어 두었지만, "
                 f"오늘은 {want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            survey, {"origin": origin, "cue_source": "customer_text_over_survey", "attribute": win, "loses_to": lose},
            "reorder_to_match", {"need_match": 1, "need_nonmatch": 1, "need_survey_match": 1, "code_first_matches": False},
            hint="설문 내용은 문장에 쓰지 마세요 — 오늘 바라는 것만")
    # D. 동점 (6)
    for origin, why, want, attr in TIES:
        add("D", f"서울 여행 중입니다. {origin}에 가려 했는데 {why}. 앱이 대체 장소 3곳을 보여 줬습니다. "
                 f"{want}. 챗봇에게 보낼 말을 1~2문장으로 써 주세요.",
            {}, {"origin": origin, "cue_source": "customer_text", "attribute": attr}, "reorder_to_match",
            {"need_match": 2, "need_nonmatch": 1, "code_first_matches": False}, note="허용 답 2곳 — 두 후보 모두 맞음")
    # E. 함정 — 입력에 없는 정보 (8)
    origins = rng.sample([o for o, *_ in TEXT_CUES], len(TRAPS))
    for origin, (want, words) in zip(origins, TRAPS):
        add("E", f"서울 여행 중 {origin} 일정이 바뀌어 앱이 대체 장소 3곳을 보여 줬습니다. 이렇게 부탁하고 싶습니다: "
                 f"「{want}」. 같은 뜻으로 자연스럽게 1~2문장 써 주세요.",
            {}, {"origin": origin, "cue_source": "unavailable_info", "attribute": "none"}, "no_fabrication",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None}, forbidden=words,
            note="후보 정보에 없는 기준 — 순서는 무엇이든 허용, 이유에 지어낸 사실이 있으면 근거 위반")
    # F. 범위 이탈 (6)
    origins = rng.sample([o for o, *_ in CONFLICTS], len(OUT_OF_LIST))
    for origin, want in zip(origins, OUT_OF_LIST):
        add("F", f"서울 여행 중 {origin} 일정이 바뀌어 앱이 대체 장소 3곳을 보여 줬습니다. 이렇게 말하고 싶습니다: "
                 f"「{want}」. 같은 뜻으로 자연스럽게 1~2문장 써 주세요.",
            {}, {"origin": origin, "cue_source": "out_of_list", "attribute": "none"}, "valid_ids_only",
            {"need_match": 0, "need_nonmatch": 0, "code_first_matches": None},
            forbidden=["롯데월드", "남산타워", "내일로"], note="후보 밖 id · 장소를 1순위로 내면 위험 오답. 순서는 코드 순서 유지가 기본")
    return cards


# ── 출력 ─────────────────────────────────────────────────────────────────
def write(cards: list[dict], name: str, rng: random.Random) -> None:
    with (OUT / f"cards_{name}_{VERSION}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for card in cards:
            fh.write(json.dumps(card, ensure_ascii=False) + "\n")
    order = cards[:]
    rng.shuffle(order)  # ★묶음이 이어지지 않게 섞는다 — 작성자가 패턴을 읽지 않게
    with (OUT / f"sheet_{name}_{VERSION}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        out = csv.writer(fh)
        out.writerow(["카드", "작성자", "상황", "참고", "고객이 보낼 말(1~2문장)", "메모"])
        for i, card in enumerate(order):
            out.writerow([card["card_id"], f"작성자{i % WRITERS + 1}", card["situation"], card.get("writer_hint", ""), "", ""])


def main() -> None:
    rng = random.Random(SEED)
    llm = llm_cards(rng)
    assert len(llm) == 60, len(llm)
    write(llm, "llm", rng)
    for name, cards in (("llm", llm),):
        strata: dict[str, int] = {}
        for c in cards:
            strata[c["stratum"]] = strata.get(c["stratum"], 0) + 1
        review = sum(1 for c in cards if c["needs_review"])
        print(f"{name}: {len(cards)}장 · 묶음 {dict(sorted(strata.items()))} · 확인 필요 {review}/{len(cards)}")


if __name__ == "__main__":
    main()
