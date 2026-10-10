# -*- coding: utf-8 -*-
"""장소 찾기 — 고객이 쓴 이름 하나 → 장소 **하나**. `[2026-09-27]` 설계서 §4

    1  우리 장소 표(`places`) 정확 일치 — NFKC·공백·괄호·지점 접미어 정규화
    2  (별칭 — 표가 아직 없다. 쌓이면 여기)
    3  자모 오타 교정 — 우리 장소 이름과 자모 편집거리 ÷ 이름 길이 ≤ 0.2 `[추정]`
    4  관광공사 이름 정확 일치(서울 법정동 필터) → 없으면 카카오로 이름을 찾고 그 이름으로 관광공사 재확인
       → 관광공사에도 없으면 카카오 값을 **그 여행 항목에만**(출처 표시)
    5  (Places 유료 — 예산 장치는 있다. 이 단계는 아직 잇지 않았다)

★`[2026-10-01]` 요식 원장(`dining`) — 미리 적재해 둔 식당 데이터. 관광공사 자리(`tour`)는 지금 액티비티 CSV 라
  식당이 없다(액티비티 쪽 결정 8e9d8d0). 식당을 그 자리에 기대지 않고 요식이 따로 찾는다.
    식사(`kind_hint="dining"` 또는 앞에 끼니 말) — 1 → 3 → **요식 원장** → 관광공사 자리 → 카카오. 끼니 말(「점심」)은 뗀다
    그 밖의 항목                           — 1 → 3 → 관광공사 자리 → **요식 원장** → 카카오(관광공사 자리가 그대로 먼저)
    카카오가 찾은 이름도 원장에서 다시 확인한다 — 확인되면 원장 값(관광공사 ID 포함)을 싣는다.

★「원문이 가리킨 만큼만 좁힌다」(§4-2) — 「광장시장 빈대떡」은 전체로 먼저 찾고, 안 되면 **뒤 단어를 떼어**
  「광장시장」으로 찾는다. ★좁힌 이름은 우리 표·관광공사에서만 받는다(카카오는 원문 전체로만). 카카오 1위 가게(원문에 없는 이름)를 고르지 않는다 — 카카오 결과는 **원문 조각과 이름이
  같거나 원문 조각으로 시작할 때만** 받는다.
★서울 밖 — 관광공사는 서울 법정동으로 거르고, 카카오는 서울 사각 + 주소로 거른다. 그래도 없으면 `unresolved`.
★약관 — 관광공사·카카오 값은 **공용 표에 넣지 않는다**(콘텐츠랩 「로컬서버 저장방식 금지」 해석 대기 ·
  카카오 「디렉터리 입력」 금지). 결과는 이 접수의 값(`intake_claims`, 근거에 출처)으로만 남는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any

SEOUL_AREA_CODE = "1"
#: 이름 끝의 지점 표시 — 「토속촌삼계탕 본점」 = 「토속촌삼계탕」
_BRANCH = re.compile(r"\s*(본점|직영점|\S+점)$")
#: 자모 오타로 받는 상한(편집거리 ÷ 긴 이름의 자모 수) — 설계서 §4-1 `[추정]`
TYPO_RATIO = 0.2
#: 관광공사 종류 → 우리 종류
KIND_BY_CONTENT_TYPE = {"39": "dining"}
#: 「그 이름이 없다」는 뜻의 실패 — 나머지(속도 제한 · 시간 초과 · 연결 · 응답 이상)는 **조회가 막힌 것**이다.
#: ☆2026-09-27 실측: 9개 질의 중 11번째 관광공사 호출이 속도 제한에 걸렸는데 「장소를 정하지 못했다」로만 남았다 —
#:   없는 것과 못 물어본 것이 같은 말이 되면 고객은 틀린 이유로 고치고, 우리는 한도 부족을 모른다.
NOT_THERE = {"not_found", "no_exact_title", "ambiguous", "no_coordinates", "no_place_name"}
_HANGUL = re.compile(r"[가-힣]")
#: 식사 항목 앞의 끼니 말 — 뒤에서부터 좁히는 규칙으로는 떼지 못한다(「점심 토속촌삼계탕」 → 「점심」만 남는다)
MEAL_WORDS = frozenset({"아침", "조식", "점심", "중식", "저녁", "석식", "브런치", "식사"})
#: 떼어도 확인이 필요 없는 말 — **무엇을 하는지**만 말하고 다른 곳을 가리키지 않는다(「경복궁 관람」 = 경복궁).
#: ☆2026-09-27 실제 확인 화면: 이런 항목까지 전부 「확인 필요」가 붙어 정작 확인할 곳이 묻혔다.
#: ★「빈대떡」(음식 — 가게일 수 있다) · 「카약」(활동 자체 — 다른 업체일 수 있다)은 여기 넣지 않는다.
PLAIN_TAILS = frozenset({"관람", "산책", "구경", "투어", "방문", "둘러보기", "나들이", "견학", "탐방", "관광"})


@dataclass
class Resolved:
    status: str                         # resolved · unresolved
    method: str | None = None           # places · typo · tour_api · kakao
    name: str | None = None             # 고른 장소의 이름(출처가 준 그대로)
    query: str | None = None            # 실제로 찾은 원문 조각(좁힌 결과)
    kind: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_id: str | None = None         # 우리 장소 표의 id(1·3단계)
    content_id: str | None = None       # 관광공사 id
    #: ★`[2026-10-07 팀]` 요식 원장 가게 id — 원장에서 찾은 곳(관광공사 id 가 없어도). 등록 때 이 id 로 원장과 잇는다
    dining_place_uid: str | None = None
    #: 관광공사 종류 번호(12 관광지 · 39 음식점 …). ★`[2026-09-28]` 운영시간 조회(`detailIntro2`)의 필수 값이다 —
    #: 전에는 싣지 않아 계획 읽기로 등록한 장소의 운영시간 조회가 늘 「필수 값 없음」 오류였다(ui 세션 실서버 시험)
    content_type_id: str | None = None
    needs_review: bool = False
    note: str | None = None
    tried: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)   # 막힌 조회(「소스:사유」) — 없음과 다르다
    #: 이름이 딱 맞지 않지만 **종류가 맞는** 카카오 후보(「한강 카약」 → 카약 업체들, 「북한산 둘레길」 → 구간들).
    #: 여기서는 고르지 않는다 — 처리 흐름이 앞뒤 일정에 가장 가까운 하나를 고른다(설계서 §4-2)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    #: ★`[2026-10-07 팀]` 체인인데 기준 위치(지점명 · 앞뒤 일정)가 없어 고르지 않았다 — 다른 장소가 정해진 뒤 다시 찾는다(2차 찾기)
    chain_deferred: bool = False
    #: 항목 종류 단서 — 원문 전체로 찾은 카카오 결과가 대부분 음식점이면 「dining」(「광장시장 빈대떡」 → 광장시장 + 식사)
    item_kind: str | None = None

    def evidence(self) -> dict[str, Any]:
        source = {"places": "places", "typo": "places", "tour_api": "tour_api", "kakao": "kakao",
                  "kakao_branch": "kakao", "dining_ledger": "dining_ledger", "dining_license": "dining_license"}.get(self.method or "")
        return {"source": source, "method": self.method, "name": self.name, "query": self.query,
                "place_id": self.place_id, "content_id": self.content_id, "tried": self.tried,
                "blocked": self.blocked}


def normalize_full(name: str) -> str:
    """`normalize` 에서 지점 접미어 떼기만 뺀 것 — 「올리브영 광화문점」과 「올리브영 종각역점」을 구별할 때 쓴다."""
    text = unicodedata.normalize("NFKC", name or "").strip()
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", text)
    return re.sub(r"[\s·\-_/]+", "", text).lower()


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKC", name or "").strip()
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", text)
    text = _BRANCH.sub("", text)
    return re.sub(r"[\s·\-_/]+", "", text).lower()


def jamo(text: str) -> str:
    """한글 음절을 자모로 푼다(오타 비교용). 한글이 아니면 그대로."""
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out += [chr(0x1100 + code // 588), chr(0x1161 + (code % 588) // 28)]
            if code % 28:
                out.append(chr(0x11A7 + code % 28))
        else:
            out.append(ch)
    return "".join(out)


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def narrowings(title: str) -> list[str]:
    """원문 조각 → 찾을 이름들(긴 것부터). 「광장시장 빈대떡」 → [「광장시장 빈대떡」, 「광장시장」]."""
    words = title.split()
    return [" ".join(words[:n]) for n in range(len(words), 0, -1) if len(" ".join(words[:n])) >= 2]


def resolve(title: str, *, our_places: list[dict[str, Any]], tour: Any = None, kakao: Any = None,
            kind_hint: str | None = None, aliases: dict[str, str] | None = None, dining: Any = None,
            near: tuple[float, float] | None = None) -> Resolved:
    # ★앞에 끼니 말이 있으면 식사다 — 규칙 읽기는 「12:00 점심 토속촌삼계탕」에 식사 표시를 하지 않는다(모델이 읽은 줄만)
    words = title.split()
    meal = kind_hint == "dining" or (len(words) > 1 and words[0] in MEAL_WORDS)
    if meal:
        while len(words) > 1 and words[0] in MEAL_WORDS:
            words = words[1:]
        title = " ".join(words)
        kind_hint = "dining"
    # 2 — 별칭(고객이 고친 표현 · 우리가 넣은 기본값). ★값은 고객 글이다 — 바꾼 이름으로 **다시 찾는다**
    alias = (aliases or {}).get(normalize(title))
    if alias and normalize(alias) != normalize(title):
        found = resolve(alias, our_places=our_places, tour=tour, kakao=kakao, kind_hint=kind_hint, dining=dining,
                        near=near)
        found.tried = [f"alias:{title}→{alias}"] + found.tried
        found.needs_review = True
        found.note = "; ".join(filter(None, [f"별칭으로 「{alias}」를 찾았다", found.note]))
        return found
    tried: list[str] = []
    blocked: list[str] = []
    candidates: list[dict[str, Any]] = []
    full_hits: list[dict[str, Any]] = []
    by_name = {normalize(p["name"]): p for p in our_places if p.get("name")}
    # ★`[2026-09-28]` 요식 식당이 공용 장소가 되면서 같은 이름 지점이 여럿일 수 있다 — 고른 뒤 「확인 필요」로 남긴다
    seen: dict[str, int] = {}
    for p in our_places:
        if p.get("name"):
            seen[normalize(p["name"])] = seen.get(normalize(p["name"]), 0) + 1
    for query in narrowings(title):
        key = normalize(query)
        # 1 — 우리 장소 표 정확 일치
        if key in by_name:
            place = by_name[key]
            return Resolved("resolved", "places", place["name"], query, place.get("kind"), place.get("latitude"),
                            place.get("longitude"), place_id=str(place["place_id"]),
                            needs_review=not _plain(query, title) or seen.get(key, 0) > 1,
                            tried=tried + [f"places:{query}"],
                            note="; ".join(filter(None, [
                                None if query == title else f"원문 「{title}」에서 「{query}」로 좁혔다",
                                f"같은 이름이 {seen[key]}곳 — 어느 지점인지 확인해 주세요" if seen.get(key, 0) > 1 else None]))
                            or None)
        tried.append(f"places:{query}")
        # 3 — 자모 오타(우리 장소 이름과)
        best = _typo(key, by_name)
        if best is not None:
            place, ratio = best
            return Resolved("resolved", "typo", place["name"], query, place.get("kind"), place.get("latitude"),
                            place.get("longitude"), place_id=str(place["place_id"]), needs_review=True,
                            tried=tried, note=f"오타로 보고 「{place['name']}」로 고쳤다(자모 거리 비율 {ratio:.2f})")
        # 4 — 관광공사(서울) 정확 일치 · 요식 원장. 식사면 원장이 먼저다(관광공사 자리는 지금 액티비티 CSV)
        for slot in (("dining", "tour") if meal else ("tour", "dining")):
            if slot == "dining":
                if dining is None:
                    continue
                found = _tour(dining, query, blocked, label="dining_ledger")
                tried.append(f"dining_ledger:{query}")
                if found is not None:
                    # ★`[2026-10-05]` 원장에 없어 인허가(사업자 등록) 자료에서 찾은 가게는 출처가 따로다 — 영업시간을 모른다
                    return _from_tour(found, query, title, tried,
                                      method="dining_license" if found.get("license") else "dining_ledger")
                continue
            found = _tour(tour, query, blocked)
            tried.append(f"tour_api:{query}")
            if found is not None:
                shop = _dish_inside(dining, query, title, found, tried)
                if shop is not None:
                    return shop
                done = _from_tour(found, query, title, tried)
                done.item_kind = _food_hint(query, title, full_hits)
                return done
        # 4 — 카카오로 이름 찾기 → 관광공사 재확인 → 없으면 카카오 값(그 여행에만)
        # ★카카오는 **원문 전체**로만 찾는다. 좁힌 이름(뒤 단어를 뗀 것)은 우리 표·관광공사에서만 받는다 —
        #   「한강 카약」을 「한강」으로 좁혀 카카오가 강 자체를 골랐다(2026-09-27 실측). 뗀 말이 활동 자체일 수 있다.
        if kakao is not None and query == title:
            # ★`[2026-10-07]` 로마자는 서울 전역 · 관련도 순 — 글자로 맞출 수 없어 관련도가 단서다. 거리순이면 앞 일정 근처의
            #   상관없는 가게가 섞였다(「Gwangjang Market」 → 「제로커피」 …). 체인이면 `_chain_branch` 가 근처를 다시 찾는다
            hits = kakao.search(query, anywhere=True) if not _HANGUL.search(query) else kakao.search(query)
            tried.append(f"kakao:{query}")
            if hits is None:                        # ★못 불렀다(예산 · 시간 초과 · 연결) — 결과 0건과 다르다
                blocked.append("kakao:" + (max(kakao.misses, key=kakao.misses.get)
                                           if getattr(kakao, "misses", None) else "unavailable"))
                hits = []
            full_hits = hits
            landmarks = set(by_name) | set((aliases or {}).keys())
            if not _HANGUL.search(query):
                found = _romanized(query, title, hits, tour, tried, blocked, dining=dining)
                if found is not None:
                    return found
                found = _chain_branch(query, hits, kakao, near, landmarks, tried, blocked)
                if found is not None:
                    return found
                continue
            # ★`[2026-10-07]` 체인이면 지점을 고른다(`chain_pick`) — 지점 표시를 뗀 이름 비교(`_kakao_match`)보다 먼저.
            #   ☆전에는 「스타벅스」가 아무 지점(관련도 1위)과 「같은 이름」이 돼 확인 없이 확정됐다(장소 찾기 평가 v0 — 11건)
            found = _chain_branch(query, hits, kakao, near, landmarks, tried, blocked)
            if found is not None:
                return found
            match = _kakao_match(query, hits)
            if match is None:
                # ★이름이 특정하지 않는다 — 종류가 맞는 후보를 **남겨 두기만** 하고 좁혀 찾기를 계속한다.
                #   ☆2026-09-28 실측: 여기서 바로 돌려주니 「광장시장 빈대떡」이 「순희네빈대떡」(원문에 없는 가게)이 됐다 —
                #   설계서 §4-2 가 막은 바로 그것. 좁힌 이름(「광장시장」)이 먼저이고, 후보는 좁혀도 못 찾을 때만 쓴다
                candidates = candidates or _kind_hits(query, hits)[:5]
            if match is not None:
                # 카카오가 찾은 이름을 미리 적재한 데이터에서 다시 확인한다 — 식당(FD6 · CE7)이나 식사면 원장부터
                food = meal or match["category_group"] in ("FD6", "CE7")
                for slot in (("dining", "tour") if food else ("tour", "dining")):
                    if slot == "dining":
                        again = (_tour(dining, match["name"], blocked, label="dining_ledger")
                                 if dining is not None and match["name"] != query else None)
                        if again is not None:
                            tried.append(f"dining_ledger:{match['name']}")
                            return _from_tour(again, query, title, tried, via=match["name"],
                                              method="dining_license" if again.get("license") else "dining_ledger")
                        continue
                    again = _tour(tour, match["name"], blocked) if match["name"] != query else None
                    if again is not None:
                        tried.append(f"tour_api:{match['name']}")
                        return _from_tour(again, query, title, tried, via=match["name"])
                exact = normalize(match["name"]) == key
                return Resolved("resolved", "kakao", match["name"], query,
                                "dining" if match["category_group"] in ("FD6", "CE7") else (kind_hint or "activity"),
                                match["latitude"], match["longitude"], needs_review=not exact or query != title,
                                tried=tried, note=("카카오에서 찾은 곳 — 관광공사에 없어 이 여행에만 싣는다"
                                                   + ("" if exact else f" · 이름이 원문과 달라 확인이 필요하다(「{match['name']}」)")))
    if candidates:
        return Resolved("unresolved", tried=tried, needs_review=True, blocked=blocked, candidates=candidates,
                        note=f"이름이 특정하지 않아 종류가 맞는 {len(candidates)}곳 중 앞뒤 일정에 가까운 곳으로 고른다")
    note = "장소를 정하지 못했다 — 고객이 고친다"
    if blocked:
        note = f"조회가 막혀({', '.join(sorted(set(blocked)))}) 장소를 정하지 못했다 — 없는 곳이라는 뜻이 아니다. 고객이 고친다"
    return Resolved("unresolved", tried=tried, needs_review=True, note=note, blocked=blocked)


def _romanized(query: str, title: str, hits: list[dict[str, Any]], tour: Any, tried: list[str],
               blocked: list[str], *, dining: Any = None) -> Resolved | None:
    """로마자 이름(「Gyeongbokgung」) — 원문과 글자가 같을 수 없어서 카카오 이름을 **관광공사 확인용으로만** 쓴다.

    ☆2026-09-27 실측: 설계서 실측 8 에서는 카카오 1위가 경복궁이었는데, 다시 재니 1~5위가 모두 식당 체인
      「경복궁 ○○점」이었다. 1위를 받으면 식당을 고른다. 그래서 지점 표시를 뗀 이름(「경복궁」)을 관광공사에
      물어 **관광공사가 확인한 것만** 받는다(확인 필요). 카카오 값 자체는 싣지 않는다.
    """
    names: list[str] = []
    for hit in hits:
        base = _BRANCH.sub("", hit["name"]).strip()
        if base and base not in names:
            names.append(base)
    # ★`[2026-10-07]` 그다음 첫 단어 — 근처 결과는 「광장시장 서문」 · 「광장시장 ○○집」처럼 온다(관련도 1위 「광장시장」이 밀린다)
    for base in list(names):
        first = base.split()[0] if " " in base else ""
        if len(first) >= 2 and first not in names:
            names.append(first)
    food = sum(1 for h in hits if h.get("category_group") in ("FD6", "CE7")) * 2 > len(hits)
    for name in names[:6]:                      # 확인할 이름 수 상한(관광공사 자리가 실제 API 인 판에서 호출을 아낀다)
        again = _tour(tour, name, blocked)
        tried.append(f"tour_api:{name}")
        if again is not None:
            return _from_tour(again, query, title, tried, via=name)
        # ★`[2026-10-07]` 결과가 대부분 음식점이면 요식 원장에서도 확인한다(「Tosokchon Samgyetang」 → 토속촌삼계탕).
        #   관광공사 자리가 액티비티 CSV 라 식당은 여기서만 확인된다. 원장이 확인한 곳만 받는다(카카오 값은 싣지 않는다)
        if food and dining is not None:
            again = _tour(dining, name, blocked, label="dining_ledger")
            tried.append(f"dining_ledger:{name}")
            if again is not None:
                return _from_tour(again, query, title, tried, via=name, method="dining_ledger")
    return None


def _chain_branch(query: str, hits: list[dict[str, Any]], kakao: Any, near: tuple[float, float] | None,
                  landmarks: set[str], tried: list[str], blocked: list[str]) -> Resolved | None:
    """체인점이면 어느 지점인지 고른다(`chain_pick`). 체인이 아니면 None — 부르는 쪽이 지금까지의 이름 찾기를 한다. `[2026-10-07]`

    기준 위치 — 입력의 지점명(「강남역점」 · 「홍대입구역」, 카카오로 그 위치를 찾는다) > 앞뒤 일정 좌표(`near`).
    기준이 있으면 그 근처를 거리순 · 그 브랜드 업종으로 1 → 3 → 5km 넓혀 다시 찾고 가장 가까운 지점을 **언제나 확인 필요**로.
    기준이 없거나 · 지점명이 맞는 지점이 없거나 · 5km 밖이면 고르지 않는다(「어느 지점인가요?」). 기준이 없어 미룬 것은
    `chain_deferred` — 다른 장소가 정해진 뒤 2차 찾기에서 다시 본다.
    """
    from .chain_pick import Neighbour, anchor_for, hint_request, needs_branch_pick, pick_branch, search_requests

    chain = needs_branch_pick(query, hits, landmarks=landmarks)
    if chain is None:
        return None
    hint_point = None
    request = hint_request(chain)
    if request is not None:
        got = kakao.search(request["query"], size=1, category_group_code=request["category_group_code"], anywhere=True)
        tried.append(f"kakao:{request['query']}(지점 위치)")
        if got:
            hint_point = (got[0]["latitude"], got[0]["longitude"])
    anchor = anchor_for(hint_point=hint_point, neighbours=[Neighbour(*near)] if near else [])
    pool = list(hits)
    pick = pick_branch(chain, pool, anchor)
    # ★`[2026-10-08]` 멈추는 기준은 **이미 찾아 본 반경**이다. 처음 결과(`hits`)는 관련도 순이라 더 가까운 지점이 빠져 있을 수 있다.
    #   ☆통합 뒤 카카오에 앞 일정 좌표를 자동으로 넣던 감싸개(`_KakaoNearHint`)가 빠지자, 관련도 순 결과의 「종로R점」(829m)이
    #   1km 안이라는 이유로 근처를 한 번도 찾지 않고 골랐다 — 가까운 「적선점」(470m)을 놓쳤다(장소 찾기 평가 PL-011 · PL-025).
    searched = 0
    for ask in search_requests(chain, anchor):
        # 같은 반경의 다른 업종(음식점 · 카페)은 마저 찾는다 — 더 넓은 반경으로 넘어갈 때만 멈춘다
        if pick.status == "picked" and (pick.distance_m or 0) <= searched < ask["radius"]:
            break
        more = kakao.search(ask["query"], near=ask["near"], radius=ask["radius"],
                            category_group_code=ask["category_group_code"], size=ask["size"])
        tried.append(f"kakao:{ask['query']}@{ask['radius']}m")
        if more is None:
            blocked.append("kakao:" + (max(kakao.misses, key=kakao.misses.get)
                                       if getattr(kakao, "misses", None) else "unavailable"))
            break
        pool += more
        searched = max(searched, ask["radius"])
        pick = pick_branch(chain, pool, anchor)
    others = ", ".join(h["name"] for h in pick.alternatives)
    note = pick.note + (f" (다른 지점: {others})" if others else "")
    if pick.status == "picked":
        place = pick.place
        return Resolved("resolved", "kakao_branch", place["name"], query, "dining", place["latitude"],
                        place["longitude"], needs_review=True, tried=tried, blocked=blocked, note=note)
    return Resolved("unresolved", tried=tried, needs_review=True, blocked=blocked, note=note,
                    chain_deferred=anchor is None)


def _typo(key: str, by_name: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], float] | None:
    if len(key) < 2:
        return None
    target = jamo(key)
    best = None
    for name_key, place in by_name.items():
        other = jamo(name_key)
        ratio = edit_distance(target, other) / max(len(target), len(other))
        if 0 < ratio <= TYPO_RATIO and (best is None or ratio < best[1]):
            best = (place, ratio)
    return best


def _tour(tour: Any, name: str, blocked: list[str], *, label: str = "tour_api") -> dict[str, Any] | None:
    """관광공사 자리 · 요식 원장이 같은 계약(`find` + `misses`)이다. `label` 은 막힌 조회에 붙는 이름."""
    if tour is None:
        return None
    before = dict(getattr(tour, "misses", {}) or {})
    found = tour.find(name, area_code=SEOUL_AREA_CODE)
    for reason, count in (getattr(tour, "misses", {}) or {}).items():
        if count > before.get(reason, 0) and reason not in NOT_THERE:
            blocked.append(f"{label}:{reason}")
    if found is None or not str(found.get("address") or "").startswith("서울"):
        return None
    return found


def _from_tour(found: dict[str, Any], query: str, title: str, tried: list[str], via: str | None = None,
               method: str = "tour_api") -> Resolved:
    note = []
    if query != title:
        note.append(f"원문 「{title}」에서 「{query}」로 좁혔다")
    if via:
        note.append(f"카카오로 「{via}」를 찾아 {'요식 원장' if method == 'dining_ledger' else '인허가 자료' if method == 'dining_license' else '관광공사'}에서 확인했다")
    if method == "dining_license":
        note.append("인허가(사업자 등록) 자료에서 찾은 식당이라 영업시간은 아직 모른다")
    if found.get("note"):
        note.append(str(found["note"]))         # 원장이 정확히 같은 이름 하나가 아닌 곳을 낸 이유(지점 · 앞부분 · 오타 · 메뉴)
    return Resolved("resolved", method, found.get("matched_title"), query,
                    KIND_BY_CONTENT_TYPE.get(str(found.get("content_type_id")), "activity"),
                    found.get("latitude"), found.get("longitude"), content_id=found.get("content_id"),
                    content_type_id=str(found["content_type_id"]) if found.get("content_type_id") else None,
                    dining_place_uid=found.get("dining_place_uid"),
                    # ★카카오로 찾은 이름이 원문과 다르면(「토속촌」 → 「토속촌삼계탕」) 확인을 받는다.
                    #   ★`[2026-10-07 팀]` 원장이 확인 필요라고 한 곳(정확히 같은 이름 하나가 아님)도
                    needs_review=(not _plain(query, title) or (via is not None and normalize(via) != normalize(query))
                                  or bool(found.get("needs_review"))),
                    tried=tried, note=" · ".join(note) or None)


def _dish_inside(dining: Any, query: str, title: str, place: dict[str, Any], tried: list[str]) -> Resolved | None:
    """「광장시장 빈대떡」 — 좁혀 찾은 장소(광장시장) 좌표 근처에서 **뗀 말(빈대떡)이 이름에 든 원장 가게**. `[2026-10-07]`

    ★뗀 말에 메뉴 말이 있을 때만(`ledger.dish_words`). 원장 가게가 없으면 None — 예전처럼 좁힌 장소를 쓴다.
    ★언제나 확인 필요다 — 원문은 가게 이름을 말하지 않았다(「순희네빈대떡」을 원문에 없는 가게로 확정하던 사고를 되풀이하지 않는다).
    ☆전에는 좁힌 장소(시장 · 골목)를 그대로 골라 식사가 활동이 됐다(장소 찾기 평가 v0 — 008 · 009 · 034).
    """
    finder = getattr(dining, "find_dish_near", None)
    if finder is None or query == title or place.get("latitude") is None:
        return None
    dropped = title[len(query):].strip()
    shop = finder(dropped, place["latitude"], place["longitude"])
    tried.append(f"dining_ledger:{query} 근처 {dropped}")
    if shop is None:
        return None
    done = _from_tour(shop, title, title, tried, method="dining_ledger")
    done.kind, done.needs_review = "dining", True
    done.note = " · ".join(filter(None, [f"「{query}」 안의 가게로 보고 찾았다", done.note]))
    return done


def _plain(query: str, title: str) -> bool:
    """좁히지 않았거나, 뗀 말이 전부 `PLAIN_TAILS` 인가 — 그러면 확인이 필요 없다."""
    dropped = title.split()[len(query.split()):] if title.startswith(query) else None
    return query == title or bool(dropped) and all(word in PLAIN_TAILS for word in dropped)


def _kakao_match(query: str, hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    """★원문 조각과 **같은 이름**이 먼저(하나뿐일 때), 없으면 원문 조각으로 **시작하는** 이름이 **하나뿐일 때**.
    원문에 없는 가게는 고르지 않는다. 같거나 시작하는 이름이 여럿이면(둘레길 구간들 · **체인 지점들**) 고르지 않고 후보로 넘긴다.

    ☆`[2026-10-02]` 지점 접미어를 뗀 이름이 같은 곳이 여럿이면(「올리브영 광화문점」 · 「올리브영 종각역점」 … 모두 「올리브영」) 전에는 카카오의
      **첫 결과**(관련도 순 — 가까운 곳이 아니다)를 골라 확인 표시도 없이 썼다. 「11시 올리브영」이 아무 지점이 되던 사고다(2026-10-01 「강남 올리브영 →
      명동 다이소」). 이제 하나로 정해질 때만 고르고, 여럿이면 후보로 넘겨 처리 흐름이 **앞뒤 일정에 가장 가까운 곳**을 고르고 확인을 받는다.
      고객이 지점 이름까지 적었으면(「올리브영 광화문점」) 지점까지 같은 하나가 먼저다."""
    full_key = normalize_full(query)
    same_full = [h for h in hits if normalize_full(h["name"]) == full_key]
    if len(same_full) == 1:
        return same_full[0]
    if len(same_full) > 1:
        return None
    key = normalize(query)
    exact = [h for h in hits if normalize(h["name"]) == key]
    prefix = [h for h in hits if normalize(h["name"]).startswith(key)]
    # 지점 접미어 덕에 「같은 이름」이 된 곳은(「올리브영 광화문점」 = 「올리브영」) 형제 지점이 하나라도 더 보이면 어느 지점인지 모른다
    if len(exact) == 1 and len(prefix) == 1:
        return exact[0]
    if exact:
        return None
    return prefix[0] if len(prefix) == 1 else None


def _food_hint(query: str, title: str, hits: list[dict[str, Any]]) -> str | None:
    """좁혀서 찾았는데(뗀 말이 있는데) 원문 전체로 찾은 카카오 결과의 과반이 음식점·카페면 항목은 식사다."""
    if query == title or not hits:
        return None
    food = sum(1 for h in hits if h.get("category_group") in ("FD6", "CE7"))
    return "dining" if food * 2 > len(hits) else None


def _kind_hits(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """종류가 맞는 후보 — 이름이 원문으로 시작하거나(구간들), 원문의 **마지막 말**(활동 · 종류, 2자 이상)이 이름이나
    분류에 든 것. 「한강 카약」 → 「○○카약」 업체들, 「북한산 둘레길」 → 「북한산둘레길 n구간」들."""
    key = normalize(query)
    words = query.split()
    last = normalize(words[-1]) if len(words) > 1 else ""
    out = []
    for hit in hits:
        name, category = normalize(hit["name"]), normalize(hit.get("category") or "")
        if name.startswith(key) or (len(last) >= 2 and (last in name or last in category)):
            out.append(hit)
    return out


def distance_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """두 좌표 사이 거리(미터, 구면 근사)."""
    import math

    r = 6_371_000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def nearest(candidates: list[dict[str, Any]], neighbours: list[tuple[float, float]]) -> tuple[dict[str, Any], float | None]:
    """앞뒤 일정 좌표에 가장 가까운 후보(거리 합이 가장 작은 것). 이웃이 없으면 카카오 첫 후보(관련도 순)."""
    if not neighbours:
        return candidates[0], None
    scored = [(sum(distance_m(c["latitude"], c["longitude"], lat, lon) for lat, lon in neighbours), c)
              for c in candidates]
    best = min(scored, key=lambda s: s[0])
    return best[1], best[0] / len(neighbours)


__all__ = ["Resolved", "_kind_hits", "distance_m", "edit_distance", "jamo", "narrowings", "nearest", "normalize",
           "normalize_full", "resolve"]
