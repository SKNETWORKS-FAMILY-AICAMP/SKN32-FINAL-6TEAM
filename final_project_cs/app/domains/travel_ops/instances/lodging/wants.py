# -*- coding: utf-8 -*-
"""숙소 찾기 — 고객 문장의 **유형 · 성급 · 싼 순 · 거리** 말을 서버 규칙으로 읽는다. `[2026-10-15 검수 D · 사용자 결정 「서버 규칙으로」]`

모델 해석(`interpret.py`)에는 이 칸이 없다(프롬프트는 DB 등록으로만 모델에 간다 — LB-15). 그래서 문장에서 정해 둔 낱말만 찾는다.
뜻을 넓게 짐작하지 않는다 — 여기 없는 말(「넓은 방」 「분위기」 그 자체)은 모델의 「반영 못 한 요청」에 남는다.

- 유형: 한옥 · 게스트하우스(게하) · 호스텔 · 모텔 · 펜션 · 리조트 · 호텔(앞의 것이 없을 때). 「○○ 말고 · 빼고 · 제외 · 싫」은 뺄 유형.
- 성급: 「5성급」 「4.5성」 → 그 값 이상만.
- 호스텔 · 게스트하우스 빼기: 커플 · 연인 · 기념일 · 분위기 · 신혼 · 고급 · 럭셔리 말이 있거나 4성급 이상을 원할 때(사용자 판정 L01).
- 싼 순: 싼 · 싸게 · 저렴 · 가성비 · 최저가(「비싼」은 아님).
- 거리: 도보 · 걸어(서) · 역세권 → `walk`, 근처 · 가까운 · 인근 · 주변 → `near`. 기준점은 숙소 팀이 카카오로 찾는다(`read.landmark`).

숙소 쪽 유형 · 성급은 목록 칸에서 읽는다 — 마이리얼트립 `description`(「3성급 · 호텔 · 강남 · 서울」 — 성급 · 유형 · 구 · 시 순서,
☆10-15 playdata 검수 결과에서 본 모양), 숙소 이름 낱말, 구글 호텔 `hotel_class`. 모양이 늘 같은지는 **확인 안 함**.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

#: 유형 낱말(문장) → 유형. 앞에서부터 본다(「게스트하우스」를 「호텔」보다 먼저)
_KIND_WORDS = (("한옥", "한옥"), ("게스트하우스", "게스트하우스"), ("게하", "게스트하우스"), ("호스텔", "호스텔"),
               ("모텔", "모텔"), ("펜션", "펜션"), ("리조트", "리조트"), ("호텔", "호텔"),
               # `[2026-10-16 평가 2차]` 오타 · 영어 — 「호탤」 「hotel」 「guesthouse」 「게스트하우쓰」를 못 읽어 호텔 요청에 게스트하우스가 섞였다
               ("hanok", "한옥"), ("게스트하우쓰", "게스트하우스"), ("게스트 하우스", "게스트하우스"), ("guesthouse", "게스트하우스"),
               ("guest house", "게스트하우스"), ("hostel", "호스텔"), ("motel", "모텔"), ("호탤", "호텔"), ("hotel", "호텔"))
#: 숙소 이름 · 설명에서 유형을 알아보는 낱말(영어 포함). 「호스텔」 · 「hostel」에는 「호텔」 · 「hotel」이 들어 있지 않다
_STAY_KIND_WORDS = (("한옥", "한옥"), ("hanok", "한옥"), ("han-ok", "한옥"), ("韓屋", "한옥"), ("韩屋", "한옥"), ("ハノク", "한옥"), ("게스트하우스", "게스트하우스"), ("guesthouse", "게스트하우스"),
                    ("guest house", "게스트하우스"), ("호스텔", "호스텔"), ("hostel", "호스텔"), ("모텔", "모텔"), ("motel", "모텔"),
                    ("펜션", "펜션"), ("리조트", "리조트"), ("resort", "리조트"), ("호텔", "호텔"), ("hotel", "호텔"))
DORMS = frozenset({"게스트하우스", "호스텔"})
#: 「호텔」을 원할 때 뺄 유형(유형을 모르면 남긴다)
NOT_HOTEL = frozenset({"게스트하우스", "호스텔", "모텔", "한옥", "펜션"})
_AVOID = re.compile(r"(한옥|게스트하우스|게하|호스텔|모텔|펜션|리조트)\s*(?:은|는|이나|나)?\s*(?:말고|빼고|제외|싫|아니)")
_STARS = re.compile(r"(?<![\d.])([1-5](?:\.5)?)\s*성(?!인)(?:급|짜리)?")
_NO_DORM = re.compile(r"여자\s*친구|남자\s*친구|여친|남친|커플|연인|기념일|분위기|신혼|허니문|프러포즈|프로포즈|고급|럭셔리")
#: 「반영 못 함」에서 지울 동행 말(호스텔 · 게스트하우스를 빼는 것으로 반영) — 「분위기 좋은」 「고급」은 숙소 성격이라 남긴다(☆10-15 17:32 검수 L01)
_COMPANION = re.compile(r"여자\s*친구|남자\s*친구|여친|남친|커플|연인|신혼|허니문")
_CHEAP = re.compile(r"(?<!비)싼|(?<!비)싸게|저렴|가성비|최저가")
_WALK = re.compile(r"도보|걸어서|걸어\s*갈|걸어\s*다닐|걸을\s*수|역세권|walk|on\s*foot", re.I)
_NEAR = re.compile(r"근처|가까운|가까이|가깝|인근|주변|바로\s*앞")


#: `[2026-10-16 사용자 판정 L05]` 묵을 사람 — 게스트하우스 · 호스텔은 여성 전용 · 외국인 전용 · 나이 제한이 붙은 곳이 많아
#:  찾기 전에 묻고(나이 · 성별 · 내국인/외국인), 받은 값으로 이름에 보이는 이용 조건을 거른다
_FEMALE = re.compile(r"(?:여자|여성|female|woman|women)(?!\s*(?:친구|전용|만))", re.I)
_MALE = re.compile(r"(?<![여fe])(?:남자|남성|male|man|men)(?!\s*(?:친구|전용|만))", re.I)
_LOCAL = re.compile(r"내국인(?!\s*(?:전용|만))|한국인|한국\s*사람|한국\s*국적")
_FOREIGN = re.compile(r"외국인(?!\s*(?:전용|만))|foreigner", re.I)
_AGE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:살|세)(?!\s*(?:미만|이하|이상))")
_DECADE = re.compile(r"(?<!\d)([1-7])0\s*대")
_MINOR = re.compile(r"미성년|고등학생|중학생|고딩|중딩")


@dataclass(frozen=True)
class Guest:
    gender: str | None = None                      # 여성 · 남성 · 혼성
    nation: str | None = None                      # 내국인 · 외국인 · 섞임
    age: int | None = None                         # 대략 나이(「20대」 → 20)
    words: tuple[str, ...] = field(default_factory=tuple)

    def missing(self) -> list[str]:
        return [label for label, value in (("나이", self.age), ("성별", self.gender), ("내국인/외국인", self.nation)) if value is None]

    def text(self) -> str:
        age = None if self.age is None else (f"{self.age}대" if self.age % 10 == 0 and self.age >= 10 else f"{self.age}세")
        return " · ".join(part for part in (age, self.gender, self.nation) if part)


def read_guest(text: str | None) -> Guest:
    """문장에서 묵을 사람의 나이 · 성별 · 내국인/외국인을 읽는다. 「여자친구」 「여성 전용」은 성별로 보지 않는다."""
    text = str(text or "")
    words: list[str] = []

    def seen(pattern: re.Pattern[str]) -> bool:
        found = [match.group(0) for match in pattern.finditer(text)]
        words.extend(found)
        return bool(found)
    female, male = seen(_FEMALE), seen(_MALE)
    gender = "혼성" if female and male else "여성" if female else "남성" if male else None
    local, foreign = seen(_LOCAL), seen(_FOREIGN)
    # 「외국인 친구랑」은 말하는 사람 + 외국인 친구 — 섞인 것으로 본다(☆검수 L04 문장)
    mixed = foreign and re.search(r"외국인\s*친구", text) is not None
    nation = "섞임" if (local and foreign) or mixed else "내국인" if local else "외국인" if foreign else None
    age = None
    exact, decade = _AGE.search(text), _DECADE.search(text)
    if exact:
        age, _ = int(exact.group(1)), words.append(exact.group(0))
    elif decade:
        age, _ = int(decade.group(1)) * 10, words.append(decade.group(0))
    elif _MINOR.search(text):
        age, _ = 17, words.append(_MINOR.search(text).group(0))
    return Guest(gender=gender, nation=nation, age=age, words=tuple(words))


@dataclass(frozen=True)
class Wants:
    kind: str | None = None
    avoid: frozenset[str] = frozenset()
    stars: float | None = None
    no_dorm: bool = False
    cheapest: bool = False
    near: str | None = None                        # "walk" · "near" · None
    #: 읽은 말(「반영 못 한 요청」에서 지울 때 쓴다)
    words: tuple[str, ...] = field(default_factory=tuple)
    guest: Guest = field(default_factory=Guest)
    #: `[2026-10-16]` 1박 아래 끝 · 「N만 원대」 위 끝 · 걸어서 N분(문장에 있을 때만)
    min_price: int | None = None
    band_max: int | None = None
    walk_min: int | None = None

    @property
    def asks_guest(self) -> list[str]:
        """게스트하우스 · 호스텔을 찾는데 묵을 사람 정보가 빠졌으면 빠진 칸(묻기 전에는 찾지 않는다 — 사용자 판정 L05)."""
        return self.guest.missing() if self.kind in DORMS else []

    @property
    def any(self) -> bool:
        return bool(self.kind or self.avoid or self.stars or self.no_dorm or self.cheapest or self.near)


def read_wants(text: str | None) -> Wants:
    text = str(text or "")
    words: list[str] = []
    avoid = set()
    for match in _AVOID.finditer(text):
        avoid.add(dict(_KIND_WORDS)[match.group(1)])
        words.append(match.group(0))
    rest = _AVOID.sub(" ", text).lower()
    kind = next((name for word, name in _KIND_WORDS if word in rest), None)
    if kind:
        words += [match.group(0) for word, name in _KIND_WORDS if name == kind
                  for match in re.finditer(re.escape(word), text, re.I)]
    star = _STARS.search(text)
    stars = float(star.group(1)) if star else None
    if star:
        words.append(star.group(0))
    no_dorm = bool(_NO_DORM.search(text)) or (stars is not None and stars >= 4)
    words += [match.group(0) for match in _COMPANION.finditer(text)]
    cheap = _CHEAP.search(text)
    if cheap:
        words.append(cheap.group(0))
    near = "walk" if _WALK.search(text) else "near" if _NEAR.search(text) else None
    for pattern in (_WALK, _NEAR):
        found = pattern.search(text)
        if found:
            words.append(found.group(0))
    if kind in avoid:
        kind = None
    guest = read_guest(text)
    low, high, price_words = read_price_band(text)
    minutes, minute_word = read_walk_minutes(text) if near == "walk" else (None, None)
    return Wants(kind=kind, avoid=frozenset(avoid), stars=stars, no_dorm=no_dorm, cheapest=bool(cheap), near=near,
                 words=tuple(words) + guest.words + price_words + ((minute_word,) if minute_word else ()), guest=guest,
                 min_price=low, band_max=high, walk_min=minutes)


#: `[2026-10-16 평가 2차]` 1박 가격의 아래 끝 — 해석 칸에 최저가가 없어 「10만 원대」 「15만~20만」에서 하한 아래 숙소가 나왔다
_KO_TENS = {"십": 10, "이십": 20, "삼십": 30, "사십": 40, "오십": 50, "육십": 60, "칠십": 70, "팔십": 80, "구십": 90}
_BAND_WORD = re.compile(r"(?<![\d만])(\d{1,3}|이십|삼십|사십|오십|육십|칠십|팔십|구십|십)\s*만\s*원?\s*대")
_RANGE_MAN = re.compile(r"(?<![\d,])(\d{1,3})\s*만\s*(?:원)?\s*(?:~|-|에서|부터)\s*(\d{1,3})\s*만")
_RANGE_WON = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})+|\d{5,7})\s*(?:원|krw)?\s*(?:~|-)\s*(\d{1,3}(?:,\d{3})+|\d{5,7})", re.I)
_AT_LEAST = re.compile(r"(?:최소\s*)?(\d{1,3})\s*만\s*원?\s*(?:이상|부터|넘는)")


def read_price_band(text: str | None) -> tuple[int | None, int | None, tuple[str, ...]]:
    """문장의 1박 가격 아래 끝(과 「N만 원대」의 위 끝). (최저, 구간 상한, 읽은 말). 하나로 정해지지 않으면 `None`."""
    text = str(text or "")
    ranges = _RANGE_MAN.findall(text)
    if len(ranges) == 1:
        low, high = int(ranges[0][0]) * 10000, int(ranges[0][1]) * 10000
        return (low, high, (_RANGE_MAN.search(text).group(0),)) if low < high else (None, None, ())
    won = _RANGE_WON.findall(text)
    if len(won) == 1:
        low, high = (int(value.replace(",", "")) for value in won[0])
        return (low, high, (_RANGE_WON.search(text).group(0),)) if low < high else (None, None, ())
    bands = _BAND_WORD.findall(text)
    if len(bands) == 1:
        n = _KO_TENS.get(bands[0]) or int(bands[0])
        return n * 10000, n * 10000 + (99999 if n % 10 == 0 else 9999), (_BAND_WORD.search(text).group(0),)
    least = _AT_LEAST.findall(text)
    if len(least) == 1:
        return int(least[0]) * 10000, None, (_AT_LEAST.search(text).group(0),)
    return None, None, ()


#: `[2026-10-16 평가 2차]` 「걸어서 5분」 「도보 10분 이내」 — 전에는 15분 고정이었다
_KO_MINUTES = {"삼": 3, "오": 5, "칠": 7, "십": 10, "십오": 15, "이십": 20}
_WALK_MINUTES = re.compile(r"(?:걸어서|도보|walk)\s*(?:로\s*)?(\d{1,2}|십오|이십|십|오|삼|칠)\s*(?:분|min)"
                           r"|(\d{1,2}|십오|이십|십|오|삼|칠)\s*(?:분|min(?:ute)?s?)\s*(?:이내|안|안쪽|거리|컷|on\s*foot)", re.I)


def read_walk_minutes(text: str | None) -> tuple[int | None, str | None]:
    found = list(_WALK_MINUTES.finditer(str(text or "")))
    if len(found) != 1:
        return None, None
    word = found[0].group(1) or found[0].group(2)
    minutes = _KO_MINUTES.get(word) or (int(word) if word.isdigit() else None)
    return (minutes, found[0].group(0)) if minutes and 1 <= minutes <= 30 else (None, None)


def _parts(description: str | None) -> list[str]:
    return [part.strip() for part in str(description or "").split("·") if part.strip()]


def stay_kinds(description: str | None = None, name: str | None = None) -> frozenset[str]:
    """설명의 유형 칸 + 이름 낱말로 본 유형들. 모르면 빈 집합."""
    found = set()
    for part in _parts(description):
        found |= {kind for word, kind in _KIND_WORDS if part == word}
    lowered = str(name or "").casefold()
    found |= {kind for word, kind in _STAY_KIND_WORDS if word in lowered}
    if found - {"호텔"} and "호텔" in found and "호텔" not in _parts(description):
        found.discard("호텔")                    # 「호텔 ○○ 게스트하우스」 같은 이름 — 더 좁은 유형을 믿는다
    return frozenset(found)


def stay_stars(description: str | None = None, hotel_class: object = None) -> float | None:
    if isinstance(hotel_class, (int, float)) and not isinstance(hotel_class, bool) and hotel_class > 0:
        return float(hotel_class)
    for part in _parts(description):
        match = re.fullmatch(r"([1-5](?:\.5)?)\s*성급", part)
        if match:
            return float(match.group(1))
    return None


def stay_city(description: str | None) -> str | None:
    """설명 마지막 칸(시 · 도) — 「3성급 · 호텔 · 강남 · 서울」 → 서울, 「모텔 · 군산」 → 군산. 유형 · 성급 칸뿐이면 `None`."""
    parts = _parts(description)
    if len(parts) < 2:
        return None
    last = parts[-1]
    if stay_stars(last) is not None or any(last == word for word, _ in _KIND_WORDS):
        return None
    return last


def price_reason(wants: Wants, price: float | None, max_price: int | None = None) -> str | None:
    """1박 가격이 아래 끝보다 낮거나 위 끝보다 높으면 까닭. 가격을 모르면 `None`(다른 곳에서 뺀다)."""
    if price is None:
        return None
    if wants.min_price and price < wants.min_price:
        return "price_low"
    top = max_price or wants.band_max
    return "price_high" if top and price > top else None


def kind_reason(wants: Wants, kinds: frozenset[str], *, strict: bool = True) -> str | None:
    """유형이 맞지 않으면 까닭(「kind」 · 「dorm」 · 「avoid」), 맞거나 모르면 `None`.
    `strict` — 원하는 유형(호텔 밖)이 **확인될 때만** 남긴다. 구글 호텔은 검색어에 유형을 넣어 찾으므로 `strict=False`(맞지 않는 게 보일 때만 뺀다)."""
    if kinds & wants.avoid:
        return "avoid"
    if wants.no_dorm and kinds & DORMS:
        return "dorm"
    if wants.kind is None:
        return None
    if wants.kind == "호텔":
        return "kind" if kinds and kinds & NOT_HOTEL and "호텔" not in kinds else None
    if wants.kind in kinds:
        return None
    # `[2026-10-15 사용자 판정 L06]` 한옥은 이름에 「한옥 · hanok(韓屋 · ハノク)」이 확실히 있을 때만(구글 칸도) — 「나인트리 인사동」이 한옥처럼 섞였다
    return "kind" if strict or kinds or wants.kind == "한옥" else None


#: `[2026-10-15 사용자 판정 L05]` 이용 조건이 붙은 숙소 이름(「YAB-GuestHouse, FemaleOnly, ForeignOnly」) — 성별 · 국적 · 나이를 모르면 바로 주지 않는다
_RESTRICTED = (("여성 전용", re.compile(r"female\s*only|women\s*only|ladies\s*only|여성\s*전용|여성만|여자\s*전용", re.I)),
               ("남성 전용", re.compile(r"male\s*only|men\s*only|남성\s*전용|남성만|남자\s*전용", re.I)),
               ("외국인 전용", re.compile(r"foreign(?:er)?s?\s*only|외국인\s*전용|외국인만", re.I)),
               ("내국인 전용", re.compile(r"korean\s*only|내국인\s*전용|내국인만", re.I)),
               ("성인 전용", re.compile(r"adults?\s*only|성인\s*전용|노\s*키즈|no\s*kids", re.I)))


def restriction(name: str | None) -> str | None:
    """숙소 이름에 보이는 이용 조건(「여성 전용」 · 「외국인 전용」 …). 여럿이면 「 · 」로 잇는다. 없으면 `None`.
    ★「female only」 안에 「male only」가 들어 있어 남성 쪽은 앞 글자가 없을 때만 본다."""
    text = str(name or "")
    found = []
    for label, pattern in _RESTRICTED:
        for match in pattern.finditer(text):
            if label == "남성 전용" and match.start() > 0 and text[match.start() - 2:match.start()].lower().endswith("fe"):
                continue
            found.append(label)
            break
    return " · ".join(found) or None


def guest_block(name: str | None, guest: Guest, *, children: int = 0) -> str | None:
    """이름에 보이는 이용 조건 중 **묵을 사람에게 맞지 않는 것**. 맞거나 조건이 없으면 `None`. `[2026-10-16 사용자 판정 L05]`
    모르는 칸(성별 · 국적 · 나이)이 걸린 조건은 맞지 않는 것으로 본다(전처럼 뺀다). 이름에 없는 조건은 알 수 없다 — 링크에서 확인."""
    found = restriction(name)
    if not found:
        return None
    fits = {"여성 전용": guest.gender == "여성", "남성 전용": guest.gender == "남성",
            "외국인 전용": guest.nation == "외국인", "내국인 전용": guest.nation == "내국인",
            "성인 전용": guest.age is not None and guest.age >= 19 and not children}
    bad = [label for label in found.split(" · ") if not fits.get(label, False)]
    return " · ".join(bad) or None


#: `[2026-10-15 사용자 판정 L10]` 반려동물 말
_PET = re.compile(r"반려\s*(?:견|동물|묘)|강아지|애견|댕댕|고양이|(?<![가-힣])펫(?!트)")


def wants_pet(text: str | None) -> bool:
    return bool(_PET.search(str(text or "")))


def stars_reason(wants: Wants, stars: float | None) -> str | None:
    if wants.stars is None:
        return None
    return None if stars is not None and stars >= wants.stars else "stars"


def strip_handled(requests: list[str], wants: Wants, *, near_done: bool) -> list[str]:
    """「반영 못 한 요청」에서 이 규칙이 반영한 조각을 뺀다. 거리 말은 기준점을 찾았을 때만(`near_done`) 뺀다."""
    patterns = [re.escape(word) for word in wants.words
                if near_done or not (_WALK.fullmatch(word) or _NEAR.fullmatch(word))]
    if wants.kind == "호텔":
        patterns.append("비즈니스\\s*호텔")
    if not patterns:
        return list(requests)
    handled = re.compile("|".join(patterns))
    return [item for item in requests if not handled.search(item)]


def summary(wants: Wants) -> list[str]:
    """답에 적을 「반영한 조건」 조각."""
    out = []
    if wants.kind:
        out.append(f"{wants.kind}만" if wants.kind != "호텔" else "호텔(게스트하우스 · 호스텔 · 모텔 제외)")
    if wants.avoid:
        out.append(" · ".join(sorted(wants.avoid)) + " 제외")
    if wants.stars:
        out.append(f"{wants.stars:g}성급 이상")
    if wants.no_dorm and wants.kind not in DORMS and not (wants.kind == "호텔"):
        out.append("호스텔 · 게스트하우스 제외")
    if wants.min_price:
        out.append(f"1박 {wants.min_price:,}원 이상")
    if wants.cheapest:
        out.append("1박 가격 낮은 순")
    if wants.guest.text() and wants.kind in DORMS:
        out.append(f"묵을 분 {wants.guest.text()}")
    return out


__all__ = ["DORMS", "NOT_HOTEL", "Guest", "Wants", "guest_block", "price_reason", "read_guest", "read_price_band", "read_walk_minutes", "kind_reason", "read_wants", "restriction", "wants_pet", "stars_reason", "stay_city", "stay_kinds", "stay_stars",
           "strip_handled", "summary"]
