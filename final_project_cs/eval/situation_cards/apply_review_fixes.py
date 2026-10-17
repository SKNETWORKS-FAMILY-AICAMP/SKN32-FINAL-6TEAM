# -*- coding: utf-8 -*-
"""카드 검토(2026-10-16 · 작성자1 · 작성자2) 반영 — 문장 고치기 17장 + 후보 다시 뽑기 13장.

★한 번 돌리는 반영 스크립트다. 무엇을 왜 바꿨는지 남기려고 저장소에 둔다(README 「카드 검토 반영」).
★검토 시트의 판정 · 메모는 지우지 않는다 — 바뀐 카드는 메모 앞에 `[10-16 반영: …]` 을 붙이고, 상황 · 후보 칸만 결합본에 맞춘다.
★후보를 다시 뽑을 때는 검토에서 나온 문제를 거르는 **엄격한 조건**을 쓴다(아래 `strict_attrs` · `usable`):
  - 의원 · 약국 · 병원과 브랜드 전문매장(SH04 — 올리브영 · 다이소 등)은 「맞는 후보」로 세지 않는다
  - 원래 장소가 「운영 중단」인데 0.15km 안 후보(같은 부지 · 같은 건물)가 있으면 그 원래 장소를 쓰지 않는다
  - 역사 = HS01 · HS02(궁궐 · 유적, 종교시설 HS03 제외) · 전시 = VE06 · VE0701 · VE0704 · VE0706(VE0703 섞임 제외)
  - 체험 = EX(웰니스 EX05 제외) · 쇼핑 = SH(전문매장 SH04 제외) · 덜 걷기 = 실내 관광 시설(공연 · 박물관 · 미술관 · 전시 · 체험, 대리 지표)
  - 원래 장소가 확실히 야외일 때만 「비 예보」 사유를 붙인다(전에는 모름도 야외로 봐 실내 시설에 비 사유가 붙었다)
실행(final_project_cs 에서, DB 필요): `PYTHONPATH=. python eval/situation_cards/apply_review_fixes.py`
"""
from __future__ import annotations

import csv
import json
import random
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class  # noqa: E402
from app.domains.travel_ops.instances.activity.db_search.place_candidates import find_place_candidates  # noqa: E402
from bind_candidates import PREFERENCES, WEEK, draft_acceptable, sample_origins, shown_for, sync_time  # noqa: E402
from review_sheets import candidate_text, survey_text, when  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402

BOUND = HERE / "cards_llm_bound_v0.jsonl"
SHEET = HERE / "sheet_llm_bound_v0.csv"
REVIEWS = [HERE / "review_by_작성자1.csv", HERE / "review_by_작성자2.csv"]
BACKUP = HERE.parents[1] / "_backup" / "situation_cards_review_fixes_2026-10-16"

RAIN = "비 예보로 야외 일정이 어렵다는 안내를 받았습니다"
CLOSED = "운영이 임시로 중단됐다는 공지를 봤습니다"
SOLD_OUT = "특별전 표가 매진됐습니다"

#: 문장만 고치는 카드 — (옛 문구, 새 문구, 이유)
TEXT_FIXES: dict[str, list[tuple[str, str, str]]] = {
    # 실내 시설인데 「비 예보」 — 결합 스크립트 결함(실내외 모름을 야외로 봄)
    **{cid: [(RAIN, CLOSED, "실내 시설에 비 사유 → 운영 중단")] for cid in ("L-41", "L-30", "L-51", "L-44")},
    # 단서 없음(A) — 날씨 사유인데 후보가 전부 야외(운영 코드가 대체 후보에 날씨를 보지 않는다)
    "L-02": [("서울숲에 가려 했는데 비 예보가 있습니다", "서울숲에 가려 했는데 임시 휴무입니다", "날씨 사유 → 임시 휴무")],
    "L-06": [("하늘공원에 가려 했는데 강풍으로 통제됐습니다", "하늘공원에 가려 했는데 임시 휴무입니다", "날씨 사유 → 임시 휴무")],
    "L-09": [("북촌한옥마을에 가려 했는데 비 예보가 있습니다", "북촌한옥마을에 가려 했는데 임시 휴무입니다", "날씨 사유 → 임시 휴무")],
    "L-11": [("낙산공원에 가려 했는데 폭염 경보가 내려졌습니다", "낙산공원에 가려 했는데 임시 휴무입니다", "날씨 사유 → 임시 휴무")],
    # 건물 전체 휴관인데 같은 건물 안 시설이 후보(국립중앙박물관 → 어린이박물관, 광장시장 → 광장시장 한복매장)
    "L-04": [("국립중앙박물관에 가려 했는데 휴관일입니다", f"국립중앙박물관에 가려 했는데 {SOLD_OUT}", "휴관 → 특별전 매진")],
    "L-40": [("국립중앙박물관에 가려 했는데 휴관일입니다", f"국립중앙박물관에 가려 했는데 {SOLD_OUT}", "휴관 → 특별전 매진")],
    "L-43": [("국립중앙박물관에 가려 했는데 휴관일입니다", f"국립중앙박물관에 가려 했는데 {SOLD_OUT}", "휴관 → 특별전 매진")],
    "L-17": [("국립중앙박물관에 가려 했는데 가 보니 정기 휴관일이었습니다", f"국립중앙박물관에 가려 했는데 가 보니 {SOLD_OUT}",
              "휴관 → 특별전 매진")],
    "L-05": [("광장시장에 가려 했는데 임시 휴무입니다", "광장시장에 가려 했는데 단체 관광객으로 너무 붐빕니다", "휴무 → 붐빔")],
    # 문구가 속성(역사 유적)보다 좁음 — 고궁 · 궁궐 · 전통 문화
    "L-52": [("오늘은 전시 말고 고궁을 걷고 싶습니다", "오늘은 전시 말고 역사 유적을 둘러보고 싶습니다", "고궁 → 역사 유적")],
    "L-57": [("고궁이나 유적이면 좋겠습니다", "역사 유적이면 좋겠습니다", "고궁 → 역사 유적")],
    "L-60": [("다른 고궁이나 유적이면 좋겠습니다", "다른 역사 유적이면 좋겠습니다", "고궁 → 역사 유적")],
    "L-55": [("궁궐 같은 역사 유적이면 좋겠습니다", "역사 유적이면 좋겠습니다", "궁궐 → 역사 유적")],
    "L-28": [("한국 전통 문화를 보여 주고 싶습니다", "한국 역사 유적을 보여 주고 싶습니다", "전통 문화 → 역사 유적")],
}

#: ★`[2026-10-17]` 2차 검토(작성자1 시트 재판정)에서 「고침」으로 남은 카드 — `--round 1017` 로 다시 뽑는다.
#   이 회차는 문장 고치기가 없고, 모든 카드에 「화면 3곳에 생활 시설 · 브랜드 매장 없음」(`CLEAN_SET`)을 건다.
#   L-36(메모가 다시 결합 전 후보 기준) · L-76(범위 이탈 F — 후보 성격은 채점에 쓰지 않음)은 다시 뽑지 않는다.
REBIND_1017: dict[str, tuple[str, tuple[int, int]]] = {
    "L-26": ("덜 걷기 = 공연장만으로 좁힘", (14, 0)),
    "L-27": ("덜 걷기 = 공연장만으로 좁힘", (14, 0)),
    "L-45": ("덜 걷기 = 공연장만으로 좁힘(전시관은 돌아다니는 곳)", (14, 0)),
    "L-54": ("실내인데 후보가 암벽등반 · 올리브영 · 다이소", (14, 0)),
    "L-64": ("전시인데 후보 1이 다이소", (14, 0)),
    "L-63": ("전시인데 후보가 문화의집 · 복합시설(코엑스)", (14, 0)),
    "L-09": ("후보 1이 원래 장소와 같은 곳(북촌 8경 0.04km)", (14, 0)),
    "L-05": ("후보 1이 원래 장소 안 매장(광장시장 한복매장)", (14, 0)),
}

#: ★`[2026-10-17 사용자 결정]` 3차 — 덜 걷기를 앉아서 하는 곳으로 넓히고, L-27(유모차)은 「유모차 접근」 속성으로 나눈다.
#   `--round 1017b`. 속성을 바꾼 뒤 다시 뽑는다.
REBIND_1017B: dict[str, tuple[str, tuple[int, int]]] = {
    "L-26": ("덜 걷기 = 앉아서 하는 곳(공연 · 영화 · 유람선 · 스파 · 공방 · 경기 관람)", (14, 0)),
    "L-27": ("유모차 접근으로 나눔(평지 · 큰 실내 시설)", (14, 0)),
    "L-45": ("덜 걷기 = 앉아서 하는 곳(공연 · 영화 · 유람선 · 스파 · 공방 · 경기 관람)", (14, 0)),
}
ATTR_FIXES_1017B = {"L-27": ("stroller", "유모차 접근")}

#: ★`[2026-10-17 사용자 결정]` 4차 — `--round 1017c`.
#:  L-27: 3차에서 후보가 전부 공원이라 유모차 접근이 분류로 가려지지 않았고, 어린이공원 「운영 중단」도 어색했다 →
#:        원래 장소를 **실내 시설**(`weather_from_class` 가 False)로 한정해 다시 뽑는다(`INDOOR_ORIGIN`).
#:  L-45: 맞는 후보가 유람선인데 사유가 「비 예보」 — 사유만 「운영 중단」으로.
REBIND_1017C: dict[str, tuple[str, tuple[int, int]]] = {
    "L-27": ("유모차 접근 — 원래 장소를 실내 시설로 한정", (14, 0)),
}
TEXT_FIXES_1017C: dict[str, list[tuple[str, str, str]]] = {
    "L-45": [(RAIN, CLOSED, "맞는 후보가 유람선인데 비 사유 → 운영 중단")],
}
INDOOR_ORIGIN: set[str] = set()

#: ★`[2026-10-17 사용자 결정]` 5차 — `--round 1017d`. 80장 전수 점검(엄격 조건)에서 29장이 걸렸고, 그중 **맞는 후보가
#:  모자란 10장만** 다시 뽑는다(정답이 성립하지 않는다). 같은 부지(12) · 생활 시설 섞임(7)은 운영 코드가 실제로 내는
#:  후보라 그대로 두고 라벨러가 판단한다.
REBIND_1017D: dict[str, tuple[str, tuple[int, int]]] = {
    **{cid: ("전수 점검 — 맞는 후보 부족", (14, 0))
       for cid in ("L-16", "L-34", "L-39", "L-41", "L-52", "L-57", "L-58", "L-62")},
}
#: ★5차 첫 실행에서 L-46(설문 체험 대 전시 요청) · L-60(역사 유적 동점 2곳)은 「화면에 생활 시설 없음」(`CLEAN_SET`)까지
#:  걸면 표본에서 못 찾았다 — `--round 1017e` 로 그 조건만 풀고 다시 뽑는다(맞는 후보에는 여전히 생활 시설을 세지 않는다).
#:  L-60 은 그래도 못 찾았다(역사 유적 HS01 · HS02 두 곳 + 아닌 곳 하나 + 코드 1순위는 아닌 곳) — 따로 정한다.
#: ★`[2026-10-17 사용자 결정]` 6차 — `--round 1017f`. L-60 은 동점(D)을 포기하고 맞는 후보 1곳짜리(B)로 바꾼다 — 지금 후보
#:  (호국공원 · 호국충혼위령비 · 미타사)가 그대로 조건을 지킨다(역사 유적 = HS01 · HS02, 절 HS03 은 아님). 후보는 다시 뽑지 않는다.
CARD_PATCHES_1017F: dict[str, tuple[dict, str]] = {
    "L-60": ({"stratum": "B", "binding": {"need_match": 1, "need_nonmatch": 1, "code_first_matches": False},
              "acceptable_draft": ["1837041"],
              "needs_review": "동점(D) → 맞는 후보 1곳(B)으로 바꿈(10-17) — 절(미타사)은 역사 유적으로 세지 않는다"},
             "동점 → 맞는 후보 1곳(B), 후보 그대로"),
}
REBIND_1017E: dict[str, tuple[str, tuple[int, int]]] = {
    "L-46": ("전수 점검 — 맞는 후보 부족(생활 시설 조건 풂)", (14, 0)),
}

#: 후보를 다시 뽑는 카드 — 이유와 방문 시각(시 · 분, 없으면 토 14:00)
REBIND: dict[str, tuple[str, tuple[int, int]]] = {
    "L-26": ("덜 걷기인데 후보가 전부 둘레길", (14, 0)),
    "L-27": ("유모차 · 덜 걷기인데 후보가 전부 둘레길", (14, 0)),
    "L-45": ("덜 걷기인데 후보가 전부 야외 공원(강풍)", (14, 0)),
    "L-18": ("만들기 체험인데 맞는 후보가 스파뿐 · 성형외과", (14, 0)),
    "L-59": ("실내 놀이인데 맞는 후보가 의원 · 화장품 매장", (14, 0)),
    "L-29": ("실내 놀이인데 맞는 후보가 반야외 책방뿐", (14, 0)),
    "L-36": ("후보 1이 원래 장소(석파정)와 같은 곳", (14, 0)),
    "L-49": ("출발지가 기념비 · 후보 둘이 같은 부지", (14, 0)),
    "L-50": ("후보 1이 원래 장소(팔각정)와 같은 곳", (14, 0)),
    "L-47": ("역사 유적인데 후보가 성당뿐", (14, 0)),
    "L-23": ("기념품인데 후보가 아웃도어 전문매장뿐", (14, 0)),
    "L-48": ("실내 전시인데 후보가 창작스튜디오뿐", (14, 0)),
    "L-25": ("야경인데 14시로 뽑음 → 19시", (19, 0)),
}

CLINIC = re.compile(r"의원|약국|병원|치과|한의원")
NIGHT = re.compile(r"전망|타워|스카이|야경|루프탑")
VIEWING = re.compile(r"야구장|체육관|경기장|돔|아레나|스타디움")
STROLLER = {"SH0101", "SH0201", "SH0202", "VE0204", "VE0201", "VE0701", "VE0702", "VE0704", "VE0705", "VE0305", "EX0701"}


def usable(c: dict) -> bool:
    """「맞는 후보」로 셀 수 있나 — 의원 · 약국, 브랜드 전문매장(SH04), 섞인 전시관 분류(VE0703 — 견본주택 갤러리 ·
    키즈카페 · 역사 같은 곳이 함께 든다, 2차에서 L-59 로 확인)는 세지 않는다."""
    cls = c.get("class") or ""
    return not CLINIC.search(c["title"] or "") and not cls.startswith("SH04") and not cls.startswith("VE0703")


def _key(title: str | None) -> str:
    return re.sub(r"[\s()（）\[\]·]+", "", title or "")


def strict_attrs(c: dict) -> set[str]:
    cls = c.get("class") or ""
    l1, l2 = cls[:2], cls[:4]
    out: set[str] = set()
    weather = weather_from_class(l1, l2)
    if weather is False and usable(c):
        out.add("indoor")
    # ★4차 — 「덜 걷기」는 실내 관광 시설만. 도서관(VE09)은 뺀다 — 폭포책방 아름인도서관(반야외)이 L-26 · L-27 둘 다의
    #   유일한 정답이 됐다. ★`[2026-10-17 사용자 결정]` 박물관 · 미술관 · 전시장은 실내라도 돌아다니는 곳이다(작성자1 검토
    #   L-45 「실내지만 전시관은 돌아다니는 곳임」) — 앉아서 하는 곳만: 공연장 · 영화관(VE06) · 유람선(EX0701) ·
    #   스파 · 온천(EX05) · 공방 체험(EX0204 · SH0501) · 경기장 관람(VE1001 중 관람 시설 이름)
    if usable(c) and (l2 == "VE06" or l2 == "EX05" or cls[:6] in ("EX0701", "EX0204", "SH0501")
                      or (l2 == "VE10" and cls[:6] == "VE1001" and VIEWING.search(c["title"] or ""))):
        out.add("low_walking")
    # ★`[2026-10-17 사용자 결정]` 유모차 접근 — 덜 걷기와 다르다(공연장 · 영화관은 유모차를 들이기 어렵다). 턱 없는 평지 ·
    #   큰 실내 시설: 백화점 · 쇼핑몰 · 아울렛 · 아쿠아리움 · 테마파크 · 박물관 · 기념관 · 전시장 · 과학관 · 광장형 공원 · 유람선
    if usable(c) and cls[:6] in STROLLER:
        out.add("stroller")
    if weather is True:
        out.add("outdoor")
    if l2 in ("HS01", "HS02"):
        out.add("history")
    if l1 == "NA" or l2 in ("VE03", "VE04"):
        out.add("nature")
    if l1 == "EX" and l2 != "EX05":
        out.add("experience")
    if l2 == "VE06" or cls[:6] in ("VE0701", "VE0704", "VE0706"):
        out.add("culture")
    if l1 == "SH" and l2 != "SH04":
        out.add("shopping")
    if l1 == "LS":
        out.add("leisure")
    if NIGHT.search(c["title"] or ""):
        out.add("night_view")
    return out


#: ★3차(L-26 · L-27 · L-29) — 맞는 후보 말고 나머지에도 생활 시설 · 브랜드 매장이 끼면 그 원래 장소를 쓰지 않는다
CLEAN_SET: set[str] = set()


def strict_ok(card: dict, shown: list[dict], origin_title: str = "") -> bool:
    target, rule = card["preference_target"], card["binding"]
    attr = target["attribute"]
    if len(shown) < 3 or any(c["distance_km"] < 0.15 for c in shown):     # 같은 부지 · 같은 건물 후보
        return False
    if origin_title and any(_key(c["title"]) == _key(origin_title) for c in shown):
        return False                       # ★2차 — 원장에 같은 장소가 좌표만 다른 두 행으로 있다(L-45 용산공원 부분개방부지)
    if card["card_id"] in CLEAN_SET and not all(usable(c) for c in shown):
        return False
    if attr == "none":
        return True                        # ★10-17 — 단서 없음(A) · 함정 · 범위 이탈은 맞는 후보 조건이 없다
    hit = [attr in strict_attrs(c) for c in shown]
    if sum(hit) < max(rule.get("need_match", 1), 1) or len(hit) - sum(hit) < rule.get("need_nonmatch", 1):
        return False
    if rule.get("code_first_matches") is False and hit[0]:
        return False
    lose = target.get("loses_to")
    if rule.get("need_survey_match") and lose and lose not in ("kid", "low_walking", "stroller"):
        return any(lose in strict_attrs(c) for c in shown)
    return True


def situation_for(card: dict, old_title: str, title: str, outdoor: bool | None, at: datetime) -> str:
    """상황 문장의 「OOO에 가려 했는데 사유.」에서 장소 이름과 사유만 바꾸고, 요일 · 시각을 후보를 뽑은 시각으로 맞춘다."""
    rainy = outdoor is True and card["preference_target"]["attribute"] in ("indoor", "culture", "shopping", "low_walking")
    why = RAIN if rainy else CLOSED
    text, n = re.subn(rf"{re.escape(old_title)}에 가려 했는데 [^.]*\.", f"{title}에 가려 했는데 {why}.", card["situation"], count=1)
    if n != 1:
        raise SystemExit(f"{card['card_id']}: 상황 문장에서 원래 장소({old_title})를 못 찾았다")
    return sync_time(text, at)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--round", choices=("1016", "1017", "1017b", "1017c", "1017d", "1017e", "1017f"), default="1016")
    args = parser.parse_args()
    global TEXT_FIXES, REBIND, BACKUP
    label = {"1016": "10-16", "1017": "10-17", "1017b": "10-17 3차", "1017c": "10-17 4차", "1017d": "10-17 5차", "1017e": "10-17 5차", "1017f": "10-17 6차"}[args.round]
    if args.round == "1017":
        TEXT_FIXES, REBIND = {}, REBIND_1017
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17")
        CLEAN_SET.update(REBIND_1017)
    if args.round == "1017f":
        TEXT_FIXES, REBIND = {}, {}
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17f")
    if args.round == "1017e":
        TEXT_FIXES, REBIND = {}, REBIND_1017E
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17e")
    if args.round == "1017d":
        TEXT_FIXES, REBIND = {}, REBIND_1017D
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17d")
        CLEAN_SET.update(REBIND_1017D)
    if args.round == "1017c":
        TEXT_FIXES, REBIND = TEXT_FIXES_1017C, REBIND_1017C
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17c")
        CLEAN_SET.update(REBIND_1017C)
        INDOOR_ORIGIN.update(REBIND_1017C)
    if args.round == "1017b":
        TEXT_FIXES, REBIND = {}, REBIND_1017B
        BACKUP = BACKUP.with_name("situation_cards_review_fixes_2026-10-17b")
        CLEAN_SET.update(REBIND_1017B)
    if BACKUP.exists():
        raise SystemExit(f"{BACKUP} 가 이미 있다 — 이 회차를 이미 돌렸다")
    BACKUP.mkdir(parents=True)
    for p in [BOUND, SHEET, *REVIEWS]:
        shutil.copy2(p, BACKUP / p.name)
    cards = [json.loads(line) for line in BOUND.open(encoding="utf-8")]
    by_id = {c["card_id"]: c for c in cards}
    notes: dict[str, str] = {}
    if args.round == "1017f":
        for cid, (patch, why) in CARD_PATCHES_1017F.items():
            by_id[cid].update(patch)
            notes[cid] = why
    if args.round == "1017b":
        for cid, (attr, name) in ATTR_FIXES_1017B.items():
            by_id[cid]["preference_target"].update(attribute=attr, label=name)

    # 1) 문장 고치기
    for cid, fixes in TEXT_FIXES.items():
        c = by_id[cid]
        for old, new, why in fixes:
            if old not in c["situation"]:
                raise SystemExit(f"{cid}: 옛 문구가 없다 — {old!r}")
            c["situation"] = c["situation"].replace(old, new, 1)
        notes[cid] = " · ".join(why for _, _, why in fixes)

    # 2) 후보 다시 뽑기 — 표본 원래 장소마다 (14:00 · 19:00) × 선호도 화면 3곳을 한 번에 계산
    used = {c["origin"]["id"] for c in cards if c["card_id"] not in REBIND and c.get("origin")}
    origins = sample_origins("demo", 800, seed=1016)
    random.Random(1017).shuffle(origins)          # 앞 결합과 다른 순서 — 같은 원래 장소를 다시 집지 않게
    times = {hm: WEEK["토"] + timedelta(hours=hm[0], minutes=hm[1]) for hm in {v[1] for v in REBIND.values()}}
    todo = dict(REBIND)
    for origin in origins:
        if not todo:
            break
        if origin["id"] in used:
            continue
        pool = find_place_candidates(get_connection, "demo", origin["id"])
        if not pool:
            continue
        outdoor = weather_from_class(pool["origin"].get("lclsSystm1"), pool["origin"].get("lclsSystm2"))
        for cid, (why, hm) in list(todo.items()):
            if cid in INDOOR_ORIGIN and outdoor is not False:
                continue
            card = by_id[cid]
            for pref in PREFERENCES:
                shown = shown_for(pool, times[hm], pref)
                if not strict_ok(card, shown, origin["title"]):
                    continue
                at = times[hm]
                old_title = card["origin"]["title"] if f"{card['origin']['title']}에 가려 했는데" in card["situation"]                     else card["origin_hint"]
                survey = {k: v for k, v in card["survey"].items() if k != "priority"}
                if pref is not None:
                    survey["priority"] = [pref]
                card.update({
                    "situation": situation_for(card, old_title, origin["title"], outdoor, at),
                    "survey": survey, "origin_rebound_from": card.get("origin_rebound_from") or card["origin_hint"],
                    "origin": {"id": origin["id"], "title": origin["title"]}, "at": at.isoformat(), "candidates": shown,
                    "acceptable_draft": draft_acceptable(card, shown), "binding_status": "ok",
                    "binding_note": f"카드 검토 반영({label}) — 엄격 조건으로 다시 결합: {why}", "label_by": "auto-tag-draft",
                    "needs_review": f"카드 검토 반영({label})으로 다시 결합 — 상황 문장 · 후보 다시 확인",
                })
                used.add(origin["id"])
                notes[cid] = f"다시 결합({why}) → 원래 장소 {origin['title']}"
                del todo[cid]
                break
            if origin["id"] in used:
                break
    if todo:
        raise SystemExit(f"다시 결합 실패 {sorted(todo)} — 아무것도 쓰지 않았다(백업 {BACKUP})")

    with BOUND.open("w", encoding="utf-8", newline="\n") as fh:
        for c in cards:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 3) 작성자 시트 — 상황 칸만 결합본에 맞춘다
    with SHEET.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    col = rows[0].index("상황")
    for r in rows[1:]:
        r[col] = by_id[r[0]]["situation"]
    with SHEET.open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows(rows)

    # 4) 검토 시트 — 판정 · 메모는 그대로, 상황 · 원래 장소 · 시각 · 설문 · 후보 칸은 결합본에 맞추고 바뀐 카드는 메모 앞에 표시
    for path in REVIEWS:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        head = rows[0]
        idx = {h: i for i, h in enumerate(head)}
        changed = 0
        for r in rows[1:]:
            c = by_id[r[0]]
            shown = [candidate_text(x) for x in c["candidates"]] + [""] * 3
            r[idx["상황(작성자에게 보일 문장)"]] = c["situation"]
            r[idx["원래 장소"]], r[idx["방문 시각"]] = c["origin"]["title"], when(c["at"])
            r[idx["설문(priority 뺌)"]] = survey_text(c["survey"])
            r[idx["후보 1(코드 순서)"]], r[idx["후보 2"]], r[idx["후보 3"]] = shown[:3]
            r[idx["원래 장소를 다시 고름"]] = "예" if c.get("origin_rebound_from") else "아니요"
            if r[0] in notes:
                memo = r[idx["메모"]]
                r[idx["메모"]] = f"[{label} 반영: {notes[r[0]]} · 다시 확인] {memo}".strip()
                changed += 1
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh).writerows(rows)
        print(f"{path.name} — 반영 표시 {changed}장")
    print(f"문장 고침 {len(TEXT_FIXES)}장 · 다시 결합 {len(REBIND)}장 · 백업 {BACKUP}")
    for cid in sorted(notes, key=lambda x: int(x[2:])):
        print(f"  {cid}: {notes[cid]}")


if __name__ == "__main__":
    main()
