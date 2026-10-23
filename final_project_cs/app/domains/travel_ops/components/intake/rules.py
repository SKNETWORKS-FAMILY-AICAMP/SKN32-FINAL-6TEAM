# -*- coding: utf-8 -*-
"""규칙 읽기 — 줄 번호가 붙은 글에서 **규칙으로 읽히는 것만** 읽고, 나머지는 「남은 줄」로 돌린다. `[2026-09-27]`

설계서 §3-3. 프런트 데모 파서(`frontend/apps/web/src/lib/demo/parse-plan.ts`)의 규칙을 옮기되
**거절하지 않는다** — 데모 파서는 형식이 조금만 달라도 오류를 냈다. 여기서는 읽은 줄 / 남은 줄로 나눈다.

읽는 것
    일차 머리줄    「1일차」「DAY 1」「첫째 날」(+ 같은 줄의 날짜)
    날짜           「2026-09-15」「9월 15일」「9/15」 — 해가 없으면 해는 비운다(날짜 해석은 2주차)
    시각 줄        「09:00 경복궁」「오전 9시 경복궁」「9시 반에 경복궁」「14시~16시 한강 카약」
                   ★한 줄에 시각이 여럿이면 시각마다 나눈다 — 채팅처럼 「9시에 경복궁, 12시에 토속촌」
    끝 시각        「09:00~11:00」「09:00-11:00」「11:00 종료」「~11시」
    예약           「예약번호 KY-20931」·「예약 완료」「예약 없음」
    여행 전체      「2박3일」「4명」「넷이서」
    화살표 나열    「경복궁 → 광장시장 → 명동」(시각 없는 순서 — 배치는 뒤 단계가 한다)

★**값은 원문에서 잘라 낸다.** 이름·예약번호는 원문의 (줄, 시작, 끝) 조각 그대로다 — 바꿔 적지 않는다.
  시각은 원문 조각을 `HH:MM` 으로 **정규화**하되 원문 조각을 근거로 같이 둔다.
★모르는 것은 채우지 않는다. 「3시」처럼 오전·오후가 갈리지 않으면 값을 내되 `needs_review` 로 표시한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

# ── 패턴 ─────────────────────────────────────────────────────────
_KO_ORDINAL = {"첫": 1, "첫째": 1, "둘째": 2, "두째": 2, "셋째": 3, "세째": 3, "넷째": 4, "네째": 4,
               "다섯째": 5, "여섯째": 6, "일곱째": 7}
_KO_COUNT = {"혼자": 1, "둘이서": 2, "둘이": 2, "셋이서": 3, "셋이": 3, "넷이서": 4, "넷이": 4}

DAY_HEADING = re.compile(
    r"^\s*[\[(【]?\s*(?:(?P<n>\d{1,2})\s*일\s*차|day\s*(?P<d>\d{1,2})|(?P<ko>첫째|첫|둘째|두째|셋째|세째|넷째|네째|"
    r"다섯째|여섯째|일곱째)\s*(?:날|일))", re.IGNORECASE)
ISO_DATE = re.compile(r"(?P<y>20\d{2})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})")
KO_DATE = re.compile(r"(?:(?P<y>20\d{2})\s*년\s*)?(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일")
SLASH_DATE = re.compile(r"(?<![\d:])(?P<m>\d{1,2})/(?P<d>\d{1,2})(?![\d:/])")

# 시각: 「09:00」 또는 「(오전|오후|아침|점심|저녁|밤|새벽) 9시 (30분|반)」
_TIME = (r"(?:(?P<ampm>오전|오후|아침|점심|저녁|밤|새벽)\s*)?"
         r"(?:(?P<h>\d{1,2}):(?P<min>\d{2})|(?P<kh>\d{1,2})\s*시(?!간)(?:\s*(?P<km>\d{1,2})\s*분|\s*(?P<half>반))?)")
TIME = re.compile(_TIME)
#: 소요 시간 — 「1시간 반」 · 「2시간」 · 「1시간 30분」 · 「40분」. ★`[2026-10-02]` 「10시 경복궁 관람 1시간 반」의 「1시간」을 시각 「1시」로 읽어
#:  가짜 항목(「간 반」 01:00)이 생겼다(계획 확인 시나리오 목업의 예시 글). 이제 시각 정규식이 「시간」을 건너뛰고, 이 소요 시간이 끝 시각이 된다.
DURATION = re.compile(r"(?:약\s*)?(?:(?P<h>\d{1,2})\s*시간(?:\s*(?P<half>반)|\s*(?P<m>\d{1,2})\s*분)?|(?P<only>\d{1,3})\s*분)"
                      r"(?!\s*(?:전|후|뒤|쯤|거리|걸|이내|만에))")
RANGE_SEP = re.compile(r"^\s*(?:~|-|–|—|부터|에서)\s*")
END_MARK = re.compile(r"^\s*(?:까지|종료|끝)")
BOOKING_NO = re.compile(r"(?:예약\s*번호|예약\s*No\.?|booking\s*(?:no|number|#)|confirmation\s*(?:no|number|#))"
                        r"\s*[:：#]?\s*(?P<no>[A-Za-z0-9][A-Za-z0-9-]{3,})", re.IGNORECASE)
BARE_BOOKING_NO = re.compile(r"(?<![A-Za-z0-9-])(?P<no>[A-Z]{2,4}-\d{3,})(?![A-Za-z0-9-])")
BOOKED = re.compile(r"예약\s*(?:있음|완료|확정|함|했)|\b(?:reserved|booked)\b", re.IGNORECASE)
NOT_BOOKED = re.compile(r"예약\s*(?:없이|없음|안\s*함)|미예약|\b(?:not\s+(?:booked|reserved)|walk[- ]in)\b",
                        re.IGNORECASE)
NIGHTS_DAYS = re.compile(r"(?P<n>\d{1,2})\s*박\s*(?P<d>\d{1,2})\s*일")
#: ☆2026-09-27 실제 화면 — 「19:00 명동난타극장」의 「00 명」을 인원 0명으로 읽어 등록이 422 로 막혔다.
#:  그래서 숫자 앞에 `:`·숫자가 오면 안 받고(시각), 0 은 안 받고, 「명·인」 뒤에 **다른 한글 음절**이 붙으면
#:  안 받는다(명동 · 인사동 · 인분). 뒷말 「이서 · 과 · 와 · 이 · 은 · 는 · 도 · 의 · 가족」은 받는다.
PARTY = re.compile(r"(?<![\d:])(?P<n>[1-9]\d?)\s*(?:명|인)(?=$|[^가-힣]|이서|이|과|와|은|는|도|의|가족)")
PARTY_KO = re.compile(r"(혼자|둘이서|둘이|셋이서|셋이|넷이서|넷이)")
ARROW = re.compile(r"\s*(?:→|->|⇒|>)\s*")

# 이름 조각을 좁히는 데 쓰는 것 — ★잘라 낼 뿐 바꾸지 않는다
#: ★`[2026-10-16]` 조사 글자(에·는·은·도)는 **뒤에 띄어쓰기·구두점이 올 때만** 뗀다 — 「9시 반에 경복궁」의 「에」.
#:  ☆전에는 글자만 보고 뗐다 — 「도산공원 → 산공원」 · 「은평한옥마을 → 평한옥마을」 · 「에버랜드 → 버랜드」
#:  (eval/intake/edge.py edge-01). 붙여 쓴 「10시에경복궁」의 「에」는 이제 이름에 남는다
_LEAD = re.compile(r"^(?:[\s,.:·|/\-~]|[에는은도]+(?=[\s,.:·|/\-~]|$))+")
#: 이름 뒤에 붙는 **말**(동사·식사·연결어) — 이것이 있을 때만 그 앞의 조사도 함께 자른다.
#: ☆`[2026-09-27]` 조사만 있어도 잘랐더니 「북촌한옥마을」이 「북촌한옥마」가 됐다 — 이름 끝 글자가 조사와 같다.
_WORDS = (r"(?:점심|저녁|아침|식사|밥|커피|쇼핑|구경|관람|체험|산책)?\s*"
          r"(?:가고|가기|가서|가요|가|방문|들르고|들러서|보고|먹고|먹기|먹어요|먹을|먹|하고|해요|하기|할|"
          r"예정|그다음|그리고|다음에)")
_TAIL_WORDS = re.compile(r"\s*(?:에서|에|은|는|을|를|으로|로)?\s*" + _WORDS + r"\s*$")
_TAIL_MEAL = re.compile(r"\s*(?:에서|에)\s*(?:점심|저녁|아침|식사|밥|커피)\s*$")
_TAIL_PUNCT = re.compile(r"[\s,.;·|/\-]+$")
#: 끼니 말 — 「점심」 · 「점심식사」 · 「점심 식사」 · 「식사」. ★`[2026-10-13]` 하나의 규칙으로 바꿨다(모양마다 늘리지 않는다)
#:  ☆전에는 이름 뒤에 **띄어 쓴 한 단어**만 뗐다 — 「광장시장 점심식사」 · 「광장시장·점심」은 이름에 남고 식사가 아니었고,
#:    「점심 · 광장시장」은 이름이 「점심」이 됐다(테스트 서버). 결함: debugs/2026-10-13_시장_점심이_다른_동네의_같은_이름_가게가_된다.md
_MEAL_WORD = r"(?:(?:아침|조식|점심|중식|저녁|석식)(?:\s*식사)?|식사)"
#: 줄 어디에 있든 **낱말로 선** 끼니 말 — 앞뒤가 글자로 이어지면 이름의 일부다(「아침고요수목원」 · 「북경중식」 · 「저녁노을카페」).
#:  조사(「에서」 · 「에」) 바로 뒤는 낱말의 시작으로 본다(「광장시장에서점심」)
_MEAL_ANY = re.compile(r"(?:(?<=에서)|(?<=에)|(?<![가-힣A-Za-z0-9]))(?P<meal>" + _MEAL_WORD + r")(?![가-힣A-Za-z0-9])")
#: 이름 **앞머리**의 끼니 말(「점심 · 광장시장」 · 「점심은 광장시장」) — 띄어쓰기나 구분자가 있어야 뗀다. ☆`^` 를 쓰지 않는다 — `match(line, pos)` 에서 `^` 는 줄 맨 앞만 맞는다
#:  ☆`^` 를 쓰지 않는다 — `match(line, pos)` 에서 `^` 는 줄 맨 앞에서만 맞아 시각 뒤의 앞머리를 못 봤다
_MEAL_HEAD = re.compile(r"\s*(?P<meal>" + _MEAL_WORD + r")(?:은|는|엔)?(?:\s*[·,/:|]\s*|\s+)")
#: 이름 **뒤**의 끼니 말(「광장시장 점심식사」 · 「광장시장·점심」 · 「광장시장에서 점심」)
_MEAL_TAIL = re.compile(r"(?:\s*(?:에서|에)\s*|\s*[·,/]\s*|\s+)(?P<meal>" + _MEAL_WORD + r")\s*$")
_MEAL_CODE = {"아침": "breakfast", "조식": "breakfast", "점심": "lunch", "중식": "lunch", "저녁": "dinner", "석식": "dinner"}
#: 끼니 말 뒤가 **때**를 말한다(「저녁 무렵 남산타워」) — 시각만 주고 식사로 보지 않는다
_MEAL_AS_TIME = re.compile(r"\s*(?:무렵|쯤|즈음|께|때|시간대)")
#: 끼니 말 뒤가 **먹은 뒤**다(「아침 먹고 나와서 경복궁」) — 그 장소의 일이 아니다. 시각도 주지 않는다
_MEAL_BEFORE = re.compile(r"\s*(?:을|를)?\s*(?:먹고|먹은\s*(?:뒤|후|다음)|드시고|하고\s*나서|후|뒤|이후|다음)")


#: 낱말로 선 끼니 말 — 뒤에 조사(은·는·엔·에·도)가 붙어도 된다(「점심은 통인시장」). 이름의 일부(「아침고요수목원」)는 아니다
_MEAL_MENTION = re.compile(r"(?:(?<=에서)|(?<=에)|(?<![가-힣A-Za-z0-9]))(?P<meal>아침|조식|점심|중식|저녁|석식)"
                           r"(?=$|[^가-힣A-Za-z0-9]|은|는|엔|에|도|으로|식사|먹|무렵|쯤|즈음|께|때)")


def meal_mention(text: str, *, place_start: int | None = None) -> tuple[str, str, bool] | None:
    """조각 안 끼니 말 → (말, 끼니, 식사인가). 없거나 「먹고 나서」처럼 다른 일을 말하면 None.
    ★`[2026-10-14]` 줄 전체에 끼니 말이 있는지만 보다가 「아침 먹고 … 경복궁」이 08:00 이 되고 「저녁 무렵 남산타워」의 저녁이 서촌에 붙었다(테스트 서버 접수 87858b77)."""
    for match in _MEAL_MENTION.finditer(text):
        word = match.group("meal")
        rest = text[match.end():]
        # 「광장시장에서 점심 먹고」는 그 장소의 식사다. 장소 앞의
        # 「아침 먹고 경복궁」만 이미 끝난 식사로 제외한다.
        if _MEAL_BEFORE.match(rest) and (place_start is None or match.start() < place_start):
            continue
        return word, _MEAL_CODE[word], not _MEAL_AS_TIME.match(rest)
    return None


#: 끼니 말 없이 「먹는다」는 말 — 장소 이름 **뒤**에 있을 때만 그 장소의 식사다(`eat_mention`). `[2026-10-15 사용자 결정 (가)]`
#:  「카페거리」 · 「커피박물관」처럼 이름의 일부면 아니다. 「술」은 「미술관」 · 「기술」에 들어 있어 넣지 않는다
_EAT = re.compile(
    r"(?:먹(?:고|자|을|어|기|으러|는|었|겠|던|은|으면)|드시|마시(?:고|러|기|자|면)|마실|식사|맛집|요기"
    r"|한\s*끼|한\s*잔|한잔|브런치"
    r"|(?<![가-힣A-Za-z0-9])밥(?![가-힣])|(?<![가-힣A-Za-z0-9])(?:카페|커피)(?!거리|골목|박물관|축제))")


def eat_mention(text: str, *, place_end: int = 0) -> str | None:
    """장소 이름 뒤(`place_end` 부터)의 「먹는다」 말 → 그 말. 없으면 None.
    ★이름 **앞**의 말은 보지 않는다 — 「밥 먹고 나서 창덕궁」 · 「아침 먹고 나와서 경복궁」은 앞선 식사다(`meal_mention` 과 같은 뜻).
    ☆`[2026-10-15]` 세 방식 비교(eval/reports/2026-10-15_intake_meal_kind.md)에서 규칙만으로는 「뭐 좀 먹고」 · 「한잔하고」 · 「맛집」을 0/7 잡았다."""
    for match in _EAT.finditer(text, max(0, place_end)):
        if not _EAT_BEFORE.match(text, match.end()):
            return match.group(0)
    return None


def _meal_head(line: str, start: int, end: int) -> tuple[int, re.Match | None]:
    """이름 앞머리의 끼니 말을 건너뛴다 — 뒤에 이름이 남을 때만. (새 시작, 끼니 말)."""
    head = _MEAL_HEAD.match(line, start, end)
    if head is None or not line[head.end():end].strip():
        return start, None
    return head.end(), head


def _meal_tail(line: str, start: int, end: int) -> tuple[int, re.Match | None]:
    """이름 뒤의 끼니 말을 잘라 낸다 — 앞에 이름이 남을 때만. (새 끝, 끼니 말)."""
    tail = _MEAL_TAIL.search(line, start, end)
    if tail is None or tail.start() <= start:
        return end, None
    return tail.start(), tail


#: 「먹는다」 말 뒤가 **먹은 뒤 출발**이다(「밥 먹고 나서 창덕궁」) — 그 줄 장소의 식사가 아니다
_EAT_BEFORE = re.compile(r"\s*(?:나서|나와서|후|뒤|다음|이후)")


#: 장소 이름 뒤에 붙어 「거기서」를 뜻하는 말 — 「먹는다」 말로 제목을 자를 때 이름 끝을 찾는다
_AT_PLACE = re.compile(r"(?<=\S)\s*(?:에서|에\s*가서|가서|들러서|들려서)(?=\s|$)")


def _eat_claim(result: "ReadResult", position: int, number: int, line: str, s: int, region_end: int) -> int | None:
    """끼니 말이 없을 때 — 이름 첫 글자 **뒤**의 「먹고」 · 「맛집」 · 「한잔」이면 식사다(`eat_mention`). `[2026-10-15 사용자 결정 (가)]`
    제목 안에서 찾았으면(「익선동 맛집」) 그 앞까지가 이름이다 — 새 이름 끝을 돌려준다. 못 찾으면 None."""
    eat = _EAT.search(line, s + 1, region_end)
    if eat is None or _EAT_BEFORE.match(line, eat.end()):
        return None
    result.claims.append(Claim(f"items[{position}].kind", "dining", Span(number, eat.start(), eat.end(), eat.group(0)),
                               note="이름 뒤의 「먹는다」 말"))
    # ★`[2026-10-15]` 「통인시장에서 뭐 좀 먹고」 · 「광장시장에서 빈대떡 먹기」 — 「먹고」 앞에서만 자르면 「에서 뭐 좀」이 이름에 남아
    #   장소를 못 찾았다(로컬 접수 실측). 이름 뒤 첫 「에서 · 가서 · 들러서」 자리에서 자른다
    place_end = _AT_PLACE.search(line, s + 1, eat.start())
    return place_end.start() if place_end else eat.start()


def _meal_claim(result: "ReadResult", position: int, number: int, line: str, meal: re.Match | None) -> None:
    if meal is not None:
        m0, m1 = meal.start("meal"), meal.end("meal")
        result.claims.append(Claim(f"items[{position}].kind", "dining", Span(number, m0, m1, line[m0:m1]),
                                   note="이름 앞뒤의 끼니 말"))


@dataclass
class Span:
    """원문 조각 — ★모든 값의 근거. `line` 은 1부터."""

    line: int
    start: int
    end: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"line": self.line, "start": self.start, "end": self.end, "text": self.text}


@dataclass
class Claim:
    """값 하나 = 줄 하나(`intake_claims`). `method` 는 여기서 늘 `rule`."""

    field: str                     # 예: trip.party_size · items[3].starts_at
    value: Any
    span: Span
    needs_review: bool = False
    note: str | None = None
    method: str = "rule"

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value, "method": self.method,
                "evidence": {"source": "text", **self.span.as_dict()},
                "needs_review": self.needs_review, "note": self.note}


@dataclass
class ReadItem:
    day: int | None                 # 몇째 날(머리줄에서) — 모르면 None
    date: str | None                # YYYY-MM-DD 또는 --MM-DD(해 모름) — 모르면 None
    start: str | None               # HH:MM
    end: str | None
    title: Span | None
    booking_no: Span | None = None
    booked: bool | None = None
    order_only: bool = False        # 화살표 나열 — 시각 없이 순서만


@dataclass
class ReadResult:
    lines: list[str]
    items: list[ReadItem] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    read_lines: set[int] = field(default_factory=set)
    party_size: int | None = None
    nights: int | None = None
    days: int | None = None

    @property
    def unread_lines(self) -> list[int]:
        """규칙이 못 읽은 줄(빈 줄 제외) — LLM 이 위치만 가리키는 단계(2주차)로 간다."""
        return [n for n, text in enumerate(self.lines, start=1) if text.strip() and n not in self.read_lines]


# ── 부품 ─────────────────────────────────────────────────────────
def _hhmm(match: re.Match) -> tuple[str, bool, str | None]:
    """시각 → (HH:MM, 확인 필요, 메모). ★오전·오후를 모르면 값은 내되 확인 필요로 둔다."""
    ampm = match.group("ampm")
    if match.group("h") is not None:
        hour, minute = int(match.group("h")), int(match.group("min"))
    else:
        hour = int(match.group("kh"))
        minute = 30 if match.group("half") else int(match.group("km") or 0)
    review, note = False, None
    if ampm in ("오후", "저녁", "밤") and hour < 12:
        hour += 12
    elif ampm == "점심" and hour < 6:
        hour += 12                              # 「점심 1시」 = 13시
    elif ampm is None and match.group("kh") is not None and 1 <= hour <= 6:
        review, note = True, "오전·오후가 적혀 있지 않다 — 적힌 숫자 그대로 두었다"
    if not (0 <= hour <= 24 and 0 <= minute < 60):
        return "", True, "시각 범위를 벗어난다"
    return f"{hour % 24:02d}:{minute:02d}", review, note


def _narrow(line: str, start: int, end: int) -> tuple[int, int]:
    """이름 조각의 앞뒤 군더더기(조사·동사·구두점)를 **잘라 낸다**. 바꾸지 않는다."""
    piece = line[start:end]
    lead = _LEAD.match(piece)
    if lead:
        start += lead.end()
    piece = line[start:end]
    while True:
        tail = _TAIL_PUNCT.search(piece) or _TAIL_WORDS.search(piece) or _TAIL_MEAL.search(piece)
        if not tail or tail.start() == len(piece) or tail.start() == 0:
            break
        end = start + tail.start()
        piece = line[start:end]
    return start, end


def _date_in(text: str) -> tuple[str | None, re.Match | None]:
    for pattern in (ISO_DATE, KO_DATE, SLASH_DATE):
        match = pattern.search(text)
        if match:
            year = match.groupdict().get("y")
            month, day = int(match.group("m")), int(match.group("d"))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            return (f"{year}-{month:02d}-{day:02d}" if year else f"--{month:02d}-{day:02d}"), match
    return None, None


# ── 본체 ─────────────────────────────────────────────────────────
def read_plan(text: str) -> ReadResult:
    lines = text.splitlines()
    result = ReadResult(lines=lines)
    day: int | None = None
    date: str | None = None
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if _trip_level(result, number, line) and not TIME.search(line) and not DAY_HEADING.match(line):
            result.read_lines.add(number)           # 여행 전체 정보(인원·박일)만 있는 줄

        heading = DAY_HEADING.match(line)
        date_value, date_match = _date_in(line)
        times = list(TIME.finditer(line))
        if heading or (date_match and not times):
            if heading:
                raw = heading.group("n") or heading.group("d")
                day = int(raw) if raw else _KO_ORDINAL.get(heading.group("ko"), None)
                result.claims.append(Claim(f"days[{day}].heading", day, Span(number, heading.start(),
                                                                                 heading.end(), heading.group(0).strip())))
            if date_match:
                date = date_value
                result.claims.append(Claim(f"days[{day or '?'}].date", date_value,
                                           Span(number, date_match.start(), date_match.end(), date_match.group(0)),
                                           needs_review=date_value.startswith("--"),
                                           note="해가 적혀 있지 않다" if date_value.startswith("--") else None))
            elif heading:
                date = None                     # 새 날인데 날짜가 없다 — 앞 날짜를 끌어 쓰지 않는다
            result.read_lines.add(number)
            if not times:
                # ★`[2026-10-16]` 머리줄 · 날짜 뒤의 화살표 나열 — 「1일차 · 10월 20일: 경복궁 → 북촌 → 인사동」.
                #   ☆전에는 이 줄을 머리줄로만 읽고 넘어가 항목이 통째로 사라졌고, 줄은 「읽음」이라 모델에게도 안 갔다(edge-02)
                rest_at = max(m.end() for m in (heading, date_match) if m)
                if _arrow_list(line[rest_at:]):
                    _arrow_items(result, number, line, day, date, begin=rest_at)
                    continue
                # ★표 행 — 「1일차 | 2026-10-10 | 광장시장 빈대떡」(시각 칸이 빈 행). 머리줄·날짜 뒤에 제목이 더 있으면
                #   시각 없는 항목이다. ☆2026-09-28 평가셋: 이 행이 머리줄로 흡수돼 항목이 통째로 사라졌다
                rest = _table_rest(line, heading, date_match)
                if rest is not None:
                    _untimed_item(result, number, line, rest, day, date, note="표에서 시각 칸이 비어 있다")
                continue
        if date_match and times and not heading:
            # ★`[2026-09-28]` 줄마다 날짜를 쓴 글 — 「2026-10-05 09:00 경복궁 관람」. 전에는 날짜를 머리줄(시각 없는 줄)
            #   에서만 받아 이 날짜를 버렸고 항목 날짜가 「모름」이 됐다(ui 세션 실서버 시험). 이 줄부터 그 날짜다
            date = date_value
            result.claims.append(Claim(f"days[{day or '?'}].date", date_value,
                                       Span(number, date_match.start(), date_match.end(), date_match.group(0)),
                                       needs_review=date_value.startswith("--"),
                                       note="해가 적혀 있지 않다" if date_value.startswith("--") else None))
        if times:
            _time_items(result, number, line, times, day, date)
            continue
        if _arrow_list(line):
            _arrow_items(result, number, line, day, date)
    _sandwiched(result)
    return result


#: 문장으로 끝나는 줄 — 끼인 줄 규칙이 받지 않는다(모델에게 넘긴다). 「점심은 토속촌에서 먹을래」
_SENTENCE_END = re.compile(r"(요|다|래|자|까|죠|게|어|아|지|네|[?!.~])\s*$")
_PARTICLE = re.compile(r"(은|는|을|를|에서|으로|에게|한테)\s")


def _table_rest(line: str, heading, date_match) -> tuple[int, int] | None:
    """표 행에서 머리줄·날짜 칸을 뺀 나머지 제목의 (시작, 끝). 표 행이 아니거나 남는 글이 없으면 None."""
    if " | " not in line:
        return None
    cells, at = [], 0
    for cell in line.split("|"):
        start = line.index(cell, at)
        at = start + len(cell)
        stripped = cell.strip()
        if not stripped:
            continue
        s = start + cell.index(stripped)
        e = s + len(stripped)
        covered = any(m and m.start() <= s and e <= m.end() + 1 for m in (heading, date_match))
        if not covered:
            cells.append((s, e))
    if not cells:
        return None
    s, e = cells[0]
    return (s, e) if re.search(r"[가-힣A-Za-z]", line[s:e]) else None


def _untimed_item(result: ReadResult, number: int, line: str, span: tuple[int, int], day, date, *, note: str) -> None:
    position = len(result.items)
    start, head = _meal_head(line, span[0], span[1])
    # ★끼니 말은 이름을 좁히기(`_narrow` — 「에서 점심」 · 「점심 먹기」를 자른다) **전에** 찾는다 — 좁히면 식사 단서를 잃었다
    meal = head or _MEAL_ANY.search(line, start, span[1])
    s, e = _narrow(line, start, span[1])
    e, tail = _meal_tail(line, s, e)
    _meal_claim(result, position, number, line, meal or tail)
    if meal is None and tail is None and e > s:
        cut = _eat_claim(result, position, number, line, s, span[1])
        if cut is not None and cut < e:
            s, e = _narrow(line, s, cut)
    if e <= s:
        return
    item = ReadItem(day, date, None, None, Span(number, s, e, line[s:e]))
    result.items.append(item)
    result.claims.append(Claim(f"items[{position}].title", line[s:e], item.title, note=note))
    booking = BOOKING_NO.search(line)
    if booking:
        b0, b1 = booking.start("no"), booking.end("no")
        item.booking_no = Span(number, b0, b1, line[b0:b1])
        result.claims.append(Claim(f"items[{position}].booking_no", line[b0:b1], item.booking_no))
    result.read_lines.add(number)


def _sandwiched(result: ReadResult) -> None:
    """못 읽은 짧은 줄의 **앞뒤가 모두 읽은 일정 줄**이면 시각 없는 항목이다(「09:30 경복궁 / 광장시장 빈대떡 /
    15:00 인사동」). 문장(「~해요」)·조사가 붙은 말은 받지 않는다 — 그런 줄은 모델이 가리킨다.
    ☆2026-09-28 평가셋: 시각 없는 줄을 모델이 가리키지 않아 항목이 빠졌다(글자 PDF)."""
    item_lines = {it.title.line for it in result.items if it.title}
    heading_lines = {c.span.line for c in result.claims if c.field.startswith("days[")}
    nonblank = [n for n, line in enumerate(result.lines, start=1) if line.strip()]
    marks: list[tuple[int, int | None, str | None]] = []
    for claim in result.claims:
        if claim.field.startswith("days[") and claim.field.endswith(".heading"):
            marks.append((claim.span.line, claim.value, None))
        elif claim.field.startswith("days[") and claim.field.endswith(".date"):
            marks.append((claim.span.line, None, claim.value))
    for i, number in enumerate(nonblank):
        if number in result.read_lines:
            continue
        line = result.lines[number - 1].strip()
        before = nonblank[i - 1] if i > 0 else None
        after = nonblank[i + 1] if i + 1 < len(nonblank) else None
        if before not in item_lines or not (after in item_lines or after in heading_lines or after is None):
            continue
        if len(line) > 30 or _SENTENCE_END.search(line) or _PARTICLE.search(line + " ") or not re.search(r"[가-힣A-Za-z]", line):
            continue
        day = date = None
        for mark_line, mark_day, mark_date in sorted(marks, key=lambda m: m[0]):
            if mark_line > number:
                break
            if mark_day is not None:
                day, date = mark_day, None
            if mark_date is not None:
                date = mark_date
        raw = result.lines[number - 1]
        start = raw.index(line)
        _untimed_item(result, number, raw, (start, start + len(line)), day, date, note="시각이 없는 줄 — 앞뒤 일정 사이")


def _trip_level(result: ReadResult, number: int, line: str) -> bool:
    """여행 전체 정보를 읽었으면 True."""
    before = len(result.claims)
    nd = NIGHTS_DAYS.search(line)
    if nd and result.nights is None:
        result.nights, result.days = int(nd.group("n")), int(nd.group("d"))
        span = Span(number, nd.start(), nd.end(), nd.group(0))
        result.claims.append(Claim("trip.nights", result.nights, span))
        result.claims.append(Claim("trip.days", result.days, span))
    party = PARTY.search(line)
    if party and result.party_size is None and not TIME.search(line[party.start():party.end()]):
        result.party_size = int(party.group("n"))
        result.claims.append(Claim("trip.party_size", result.party_size,
                                   Span(number, party.start(), party.end(), party.group(0))))
    else:
        ko = PARTY_KO.search(line)
        if ko and result.party_size is None:
            result.party_size = _KO_COUNT[ko.group(1)]
            result.claims.append(Claim("trip.party_size", result.party_size,
                                       Span(number, ko.start(), ko.end(), ko.group(0))))
    return len(result.claims) > before


def _time_items(result: ReadResult, number: int, line: str, times: list[re.Match],
                day: int | None, date: str | None) -> None:
    """한 줄의 시각들 — 「시작~끝」 짝은 하나로, 나머지는 시각마다 항목 하나."""
    index = 0
    produced = 0
    while index < len(times):
        start_match = times[index]
        end_match = None
        after = line[start_match.end():]
        nxt = times[index + 1] if index + 1 < len(times) else None
        if nxt is not None and RANGE_SEP.match(line[start_match.end():nxt.start()]) \
                and not line[start_match.end():nxt.start()].strip(" ~-–—부터에서"):
            end_match, index = nxt, index + 1
        elif nxt is None and re.match(r"^\s*~\s*$", after):
            pass
        body_start = (end_match or start_match).end()
        following = times[index + 1] if index + 1 < len(times) else None
        body_end = following.start() if following is not None else len(line)
        # 「11:00 종료」처럼 끝을 말하는 시각은 항목이 아니다 — 앞 항목의 끝
        if END_MARK.match(line[start_match.end():]) and result.items and result.items[-1].end is None \
                and produced > 0:
            value, end_review, end_note = _hhmm(start_match)
            result.items[-1].end = value
            # ★`[2026-10-15 x600 실서버 확인]` 값만 항목에 달고 **값 줄(`ends_at`)을 만들지 않아** 「08:00 경복궁 · 한복 체험, 12:00 종료」의 끝이 확인 화면에서 사라지고
            #   「끝 시각이 없어 90분으로 두었어요」가 됐다 — 끝을 말한 시각도 다른 끝 시각과 같이 근거(원문 조각)를 단 값 줄로 싣는다
            result.claims.append(Claim(f"items[{len(result.items) - 1}].ends_at", value,
                                       Span(number, start_match.start(), start_match.end(), start_match.group(0)),
                                       needs_review=end_review, note=end_note))
            index += 1
            continue
        start_value, review, note = _hhmm(start_match)
        if not start_value:
            index += 1
            continue
        position = len(result.items)
        item = ReadItem(day=day, date=date, start=start_value, end=None, title=None)
        result.claims.append(Claim(f"items[{position}].starts_at", start_value,
                                   Span(number, start_match.start(), start_match.end(), start_match.group(0)),
                                   needs_review=review, note=note))
        if end_match is not None:
            end_value, end_review, end_note = _hhmm(end_match)
            if end_value:
                item.end = end_value
                result.claims.append(Claim(f"items[{position}].ends_at", end_value,
                                           Span(number, end_match.start(), end_match.end(), end_match.group(0)),
                                           needs_review=end_review, note=end_note))
        segment = line[body_start:body_end]
        booking = BOOKING_NO.search(segment) or BARE_BOOKING_NO.search(segment)
        title_end = body_start + (booking.start() if booking else len(segment))
        # 끝 시각이 없고 소요 시간이 적혀 있으면 시작 + 소요 시간이 끝이다(원문 조각을 근거로 단다). 이름에서는 뗀다
        spent = DURATION.search(segment) if item.end is None else None
        if spent is not None:
            minutes = (int(spent.group("h")) * 60 + (30 if spent.group("half") else int(spent.group("m") or 0))
                       if spent.group("h") else int(spent.group("only")))
            hh, mm = (int(x) for x in start_value.split(":"))
            end_minutes = hh * 60 + mm + minutes
            if 0 < minutes and end_minutes < 24 * 60:
                item.end = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
                result.claims.append(Claim(f"items[{position}].ends_at", item.end,
                                           Span(number, body_start + spent.start(), body_start + spent.end(), spent.group(0)),
                                           note=f"소요 시간 「{spent.group(0).strip()}」으로 끝 시각을 계산했다"))
                title_end = min(title_end, body_start + spent.start())
        # 끝 표시(「까지」「종료」)와 이름 사이의 괄호 설명은 이름에서 뺀다
        # ★표 행(「09:00 | 경복궁」)처럼 **앞머리의** 구분자는 건너뛰고 찾는다 — 전에는 그것을 설명의 시작으로 보고
        #   이름을 통째로 잘랐다(docx·xlsx 시험에서 찾았다)
        lead = _LEAD.match(line[body_start:title_end])
        name_start = body_start + (lead.end() if lead else 0)
        # ★앞머리 끼니 말(「점심 · 광장시장」)을 먼저 건너뛴다 — 아래 「 · 」 자르기가 「점심」만 이름으로 남겼다
        name_start, head = _meal_head(line, name_start, title_end)
        cut = re.search(r"[(\[（【]|\s[·|]\s", line[name_start:title_end])
        if cut:
            title_end = name_start + cut.start()
        meal = head or _MEAL_ANY.search(line, name_start, title_end)
        s, e = _narrow(line, name_start, title_end)
        e, tail = _meal_tail(line, s, e)
        _meal_claim(result, position, number, line, meal or tail)
        if meal is None and tail is None and e > s:
            cut = _eat_claim(result, position, number, line, s, body_end)
            if cut is not None and cut < e:
                s, e = _narrow(line, s, cut)
        if e > s:
            item.title = Span(number, s, e, line[s:e])
            result.claims.append(Claim(f"items[{position}].title", line[s:e], item.title))
        if booking:
            b0 = body_start + booking.start("no")
            b1 = body_start + booking.end("no")
            item.booking_no = Span(number, b0, b1, line[b0:b1])
            item.booked = True
            result.claims.append(Claim(f"items[{position}].booking_no", line[b0:b1], item.booking_no))
        elif NOT_BOOKED.search(segment):
            item.booked = False
        elif BOOKED.search(segment):
            item.booked = True
        if item.booked is not None:
            marker = (NOT_BOOKED if item.booked is False else BOOKED).search(segment)
            if marker:
                result.claims.append(Claim(f"items[{position}].booked", item.booked,
                                           Span(number, body_start + marker.start(), body_start + marker.end(),
                                                marker.group(0))))
        result.items.append(item)
        produced += 1
        index += 1
    if produced:
        result.read_lines.add(number)


def _arrow_list(text: str) -> bool:
    return bool(ARROW.search(text)) and len(ARROW.split(text.strip())) >= 2


def _arrow_items(result: ReadResult, number: int, line: str, day: int | None, date: str | None, *,
                 begin: int = 0) -> None:
    """화살표로 이은 이름들. `begin` 앞(머리줄 · 날짜)은 이름으로 읽지 않는다."""
    cursor = begin
    for piece in ARROW.split(line[begin:]):
        start = line.index(piece, cursor) if piece else cursor
        end = start + len(piece)
        cursor = end
        s, e = _narrow(line, start, end)
        if e <= s:
            continue
        position = len(result.items)
        span = Span(number, s, e, line[s:e])
        result.items.append(ReadItem(day=day, date=date, start=None, end=None, title=span, order_only=True))
        result.claims.append(Claim(f"items[{position}].title", line[s:e], span, needs_review=True,
                                   note="시각이 없다 — 순서만 적혀 있다"))
    result.read_lines.add(number)


__all__ = ["Claim", "ReadItem", "ReadResult", "Span", "eat_mention", "meal_mention", "read_plan"]
