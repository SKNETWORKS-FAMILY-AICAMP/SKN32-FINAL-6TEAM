# -*- coding: utf-8 -*-
"""공지 · 재난 문자 본문이 **「끝났다」를 말하나** — 공용 판정 한 곳 `[2026-10-12 사용자 결정 — 공용 층에서 판정]`.

★왜 한 곳인가. 같은 공지를 액티비티 · 요식 · 이동이 함께 본다. 전에는 읽는 곳마다 끝 낱말이 달랐다
  (지하철 무정차 공지 7낱말 · 재난 문자 「해제」 하나 · 안전 정지 「해제」 하나) — 한 고객이 「끝났다」와 「진행 중」을
  같이 받을 수 있었다. 이제 지하철 공지 · 재난 문자 · 안전 정지가 이 함수 하나를 쓴다. 에이전트는 결과(`state` · `basis`)를 받아
  자기 일정에 무슨 뜻인지만 정한다.
★왜 글자를 읽나. 재난 문자에는 「해제」를 알리는 칸이 따로 없다 — 해제 문자도 통제 문자와 같은 긴급단계 · 재해구분으로 온다
  (샘플 2023-09 100건 실측: 「봉은사로 차량 통제가 완전 해제」가 안전안내 · 교통통제). 지하철 공지의 `nonstopYn` 도 종료 알림에 Y 였다.

판정(원문 조각을 `basis` 로 남긴다 — 근거 없는 판정을 만들지 않는다):

    ended          끝났다 — 「집회 종료되어 정상 운행」 · 「파업 철회」 · 「모든 차로 개방」 · 「복구완료」 · 「경보 해제」
    partial        일부만 풀렸다 — 「1개 차로 개방」 · 「그 외 구간 해제」 · 「일부 구간 운행 재개」 (끝난 것이 아니다)
    scheduled      앞으로 끝날 것이라는 예상 — 「종료 예정」 · 「해제 시까지」 · 「종료 후 정상 운행 예정」 (끝난 것이 아니다)
    unsettled      정해지지 않았다 — 「해제 여부 확인 중」 · 「복구 작업 중」 · 「철회 촉구」 · 「재개되지 않」
    no_end_signal  끝을 말하는 낱말이 없다

★끝났다고 보는 것은 `ended` 하나뿐이다. 나머지는 모두 「아직 끝나지 않음」으로 쓴다 — 정보가 모자란 문장을 정상으로 읽지 않는다
  (`knowledge/travel/documents/t08_mobility_disruption.md` 「재개 예정은 예상이며 이미 재개했다는 사실과 다르다」).
★`[2026-10-12 밤 보강]` 서울 재난문자 956건(`datasets/safety/disaster_msg_seoul_2026`)에 돌려 보니 진행 중인 문자 15건을 ended 로 읽었다 —
  「복구에 장시간 소요 예상」 · 「복구완료될 때까지 운행을 중지 … 1호선 정상운행」 · 「복구 지연」 · 「단계적 정상화중」 · 「주불진화 완료, 잔불정리 중」.
  그래서 「복구완료」를 한 덩어리로 읽고, 「될 때까지」 · 「에 장시간」 · 「지연」 꼬리와 「복구로」(원인)를 더했고, 같은 문자에 운행 중지가 살아 있으면
  「정상 운행」 낱말로는 끝남을 내지 않는다(다른 노선 이야기). 실제 문자는 시험 `test_notice_status.py` 의 REAL_ONGOING · REAL_ENDED 에 있다.
★남은 한계: 낱말 규칙이다. 한 문장에 두 사건이 섞이면(「A 통제, B 해제」) 일부 풀림으로만 본다. 규칙에 없는 새 말투는 `no_end_signal` 로
  남는다(끝나지 않은 쪽 — 경고가 더 오래 남는 방향으로 틀린다). 실제 공지 전체로 잰 정확도는 아직 없다.
★`[2026-10-13 사용자 지시]` **2차 확인**: 조립이 모델을 꽂으면(`set_second_opinion` — `notice_end_model.py`) 규칙이 「끝남」이라 한 본문만 모델이 한 번 더 본다.
  모델이 「끝남 아님」이면 `disputed`(끝난 것이 아니다)로 바꾼다. 모델은 끝남을 거부만 하고 새로 만들지 않는다. 모델을 못 부르면 규칙 결과 그대로다.
  서울 재난 문자 190건에서 잘못 끝남 규칙 5 → 둘 다 끝남일 때만 2, 놓침 0 → 0(정답은 Claude — `wiki/records/reports/2026-10-13_0100_끝남판정_규칙대모델_실수율.md`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

ENDED = "ended"
PARTIAL = "partial"
SCHEDULED = "scheduled"
UNSETTLED = "unsettled"
NO_END_SIGNAL = "no_end_signal"
#: 규칙은 끝남이라 했지만 2차 확인(모델)이 「끝남 아님」이라 한 것 — 끝난 것이 아니다
DISPUTED = "disputed"

#: 2차 확인 — 본문 → True(끝남) · False(끝남 아님) · None(못 정함). 조립이 꽂는다(`notice_end_model.register_from_settings`). 비어 있으면 규칙만
_second_opinion: Callable[[str], bool | None] | None = None


def set_second_opinion(judge: Callable[[str], bool | None] | None) -> None:
    global _second_opinion
    _second_opinion = judge

#: 끝을 말하는 낱말. ★「정상」은 운행 · 통행 같은 말이 붙을 때만 — 「정상 운행 여부」는 아래 꼬리 규칙이 거른다
#: ★`[2026-10-12 실측 보강]` 「복구완료」는 한 덩어리로 읽는다 — 따로 읽으면 「복구」의 꼬리가 「완료될 때까지」가 되어 예정을 놓친다
_END = re.compile(
    r"종료|해제|재개|해소|철회|개방|복구\s*[완왼]료|복구|완료|완진|정상화|정상적으로|"
    r"정상\s*(?:운행|운영|통행|정차|소통|영업|개통|개방|운항|공급)|"
    # `[2026-10-13 전국 문자 보강]` 「통행 가능」도 끝이다(「전면 통행 가능하오니」 · 「양방향 통행 가능함을 알려드립니다」). 「통행 불가능」은 안 걸린다
    r"(?:통행|운행)\s*(?:이\s*)?가능")
#: 끝 낱말 **바로 뒤**가 이러면 예상이다 — 「종료 예정」 · 「해제될 것으로 전망」 · 「해제 시까지」 · 「종료 후」 · 「재개되면」 ·
#: 「복구완료될 때까지」 · 「복구될때까지」 · 「복구 완료(왼료) 시 재안내」
_SCHEDULED_TAIL = re.compile(
    r"\s*(?:(?:될|할|되는|하는|될\s*것으로|할\s*것으로)\s*)?(?:예정|계획|전망|예상)"
    r"|\s*(?:(?:될|할|되는|하는)\s*)?(?:되면|하면|후|시(?![각간])|때까지|까지|되는\s*대로|하는\s*대로)"
    r"|\s*[완왼]료\s*(?:시(?![각간])|후|되면|될)"
    # `[2026-10-13]` 앞으로 하겠다는 말 — 「신속히 복구하겠습니다」
    r"|\s*[가-힣]{0,2}겠|\s*할\s*것")
#: 끝 낱말 **바로 뒤**가 이러면 정해지지 않았다 — 「여부」 · 「촉구」 · 「작업 중」 · 「되지 않」 · 「지연」 · 「복구에 장시간 소요」
_UNSETTLED_TAIL = re.compile(
    r"\s*[가-힣]{0,3}?\s*(?:[되하돼]지\s*(?:않|못)|안\s*[되돼])|\s*(?:못|여부|촉구|요구|요청|검토|협상|논의|불투명|미정|"
    r"작업|공사|진행|확인\s*중|지연)"
    r"|에\s*(?:장시간|상당|많은|약\s*\d|\d|시간)"
    # `[2026-10-13]` 끝났다고 했다가 뒤집는 말 — 「통제가 해제되었으나 재통제될 수 있으니」 · 「진화 완료 되었으나 연기 발생 중」 · 「복구 시간이 소요될 예정」
    r"|\s*[가-힣]{0,4}(?:으나|지만|하나)(?![가-힣])|\s*시간이?\s*소요|에\s*(?:최선|만전|노력)")
#: `[2026-10-13]` 끝 낱말이 목적일 뿐이다 — 「응급실 과밀해소를 위해」 · 「대중교통 정상화를 위해 최선」
_PURPOSE_TAIL = re.compile(r"\s*(?:를|을)?\s*위(?:해|한|하여)")
#: `[2026-10-13]` 끝 낱말 앞 12자가 이러면 사건의 끝이 아니다 — 「수문을 0.6m 개방하여 방류」 · 「수도꼭지 미세개방」 · 「축제가 종료되었습니다(이제 귀가 혼잡)」 · 「수해복구 작업」
_NOT_EVENT_HEAD = {"개방": re.compile(r"수문|꼭지|미세|창문"), "종료": re.compile(r"축제|공연|행사|경기|콘서트|불꽃"),
                   "복구": re.compile(r"수해\s*$")}
#: `[2026-10-13]` 「마을버스는 정상운행」 — 다른 대상이 정상이라는 말이다(파업으로 시내버스는 멈췄다)
_CONTRAST_HEAD = re.compile(r"[은는]\s*$")
#: `[2026-10-13]` 「임시 해제 … 일시통제 예정」 — 임시로 푼 것은 끝이 아니다
_TEMPORARY_HEAD = re.compile(r"임시\s*$")
#: `[2026-10-13]` 「11:00부터 … 통제를 해제합니다」 — 정해진 시각부터 하겠다는 알림(보낸 시각보다 앞인지 모른다)
_FROM_TIME = re.compile(r"\d{1,2}\s*[:시]\s*\d{0,2}\s*분?\s*부터")
_PRESENT_TAIL = re.compile(r"\s*(?:합니다|하오니|할)")
#: 「복구로 열차 운행이 정상화 중」의 「복구로」는 끝이 아니라 원인이다(「복구」 낱말에만 건다)
_CAUSE_TAIL = re.compile(r"(?:으)?로\s")
#: 같은 문자에 지금 멈춰 있다는 말이 있으면, 「정상 운행」은 **다른 노선** 이야기다 —
#: 「서울~수색 구간 운행을 중지합니다 △1호선 및 경의중앙선 정상운행」. ★「중지되었던 구간 정상 운행」은 끝난 것이라 거르지 않는다
_STILL_STOPPED = re.compile(
    r"운행\s*중지(?!\s*(?:되었던|됐던|되었|됐|가\s*해제|해제))|운행을\s*중지(?:합니다|하오니|하니|중)|운행\s*중단\s*(?:중|합니다)|"
    r"운행을\s*중단(?:합니다|하오니)|중지합니다")
#: 「복구 중」 · 「해제 중」은 아직이다. ★「정상 운행 중」은 끝난 뒤의 상태라 이 규칙을 걸지 않는다
_IN_PROGRESS_TAIL = re.compile(r"\s*중(?![앙구지])")
#: 끝 낱말 **바로 앞**이 「미」면 끝이 아니다 — 「미복구」 · 「미해제」
_NEGATED_HEAD = re.compile(r"미$")
#: 「종료」 바로 앞이 이러면 사건의 끝이 아니라 그날 운행 · 영업이 끝난 것이다 — 「열차 운행 종료」 · 「영업 종료」
_SERVICE_END_HEAD = re.compile(r"(?:운행|영업|운영)\s*$")
#: 일부만 풀렸다는 표시
#: `[2026-10-13 전국 문자 보강]` 「일부」·「차로」는 그 자리에서 쓰일 때만 — 「실란가스 일부 유출 사고 대응이 종료」 · 「양방향 2차로 구간의 통제를 해제」는 전부 끝났다.
#:  「주불」은 빼고 「잔불」만 본다(「주불 진화. 대피명령 해제」는 끝). 반대 방향 · 「~방향은」 · 「만 통행」 · 「통행 불가」 · 「차단 중」 · 「경보로 변경」도 일부다
_PARTIAL = re.compile(r"일부\s*(?:구간|차로|차선|노선|지역|방향|도로|만|해제|재개|개방|통행|운행)|부분\s*(?:통행|개방|재개|해제)|한쪽|편도|그\s*외|나머지|"
                      r"\d+\s*개?\s*(?:차로|차선)\s*(?:만|통행|개방|통제|재개)|잔불|단계적|순차적|반대\s*방향|[가-힣\-→]+\s*방향은|"
                      r"만\s*(?:통행|운행|가능)|통행\s*불가|차단\s*중|통제\s*중(?!이던|이었)|(?:으)?로\s*변경|하향")   # 「주불진화 완료, 잔불정리 중」 · 「단계적 정상화중 … 운행재개」
#: 전부 풀렸다는 표시 — 있으면 일부 표시를 덮는다(「1개 차로 통제했으나 모든 차로 개방」)
#: ★「완전」은 끝 낱말이 바로 붙을 때만 — 「완전 해제」는 전부지만 「완전진화를 위해 최선」은 앞으로의 목표다
_FULL = re.compile(r"모든|전\s*차로|전체\s*차로|전면\s*(?:통행|개방|해제|재개|정상)|전\s*구간|전체\s*구간|양방향\s*모두|완전히?\s*(?:해제|개방|복구|종료|재개|정상)")


@dataclass(frozen=True)
class NoticeStatus:
    state: str
    #: 판정 근거가 된 원문 조각(끝 낱말 앞뒤). 끝 낱말이 없으면 None
    basis: str | None = None

    @property
    def ended(self) -> bool:
        return self.state == ENDED


def _around(text: str, start: int, end: int) -> str:
    return text[max(0, start - 8):min(len(text), end + 8)].strip()


def notice_status(text: str | None) -> NoticeStatus:
    """본문 하나의 끝남 판정. 판정 규칙은 모듈 docstring."""
    text = str(text or "")
    clean: list[str] = []
    scheduled: list[str] = []
    unsettled: list[str] = []
    still_stopped = bool(_STILL_STOPPED.search(text))
    for match in _END.finditer(text):
        head, tail = text[max(0, match.start() - 4):match.start()], text[match.end():match.end() + 12]
        basis = _around(text, match.start(), match.end())
        word = match.group()
        if _NEGATED_HEAD.search(head):
            unsettled.append(basis)
            continue
        if word == "종료" and _SERVICE_END_HEAD.search(head):
            continue
        head12, head40 = text[max(0, match.start() - 12):match.start()], text[max(0, match.start() - 40):match.start()]
        key = "복구" if word.startswith("복구") else word
        if key in _NOT_EVENT_HEAD and _NOT_EVENT_HEAD[key].search(head12 if key != "복구" else head):
            continue
        if word == "복구" and re.match(r"\s*(?:및|등)", tail):
            continue                                   # 「수해복구 및 논·밭 작업자」 — 이름으로 쓰인 「복구」
        if _PURPOSE_TAIL.match(tail):
            continue
        if word.startswith("정상") and _CONTRAST_HEAD.search(head):
            continue
        if _TEMPORARY_HEAD.search(head):
            unsettled.append(basis)
            continue
        if _FROM_TIME.search(head40) and _PRESENT_TAIL.match(tail):
            scheduled.append(basis)
            continue
        if still_stopped and word.startswith("정상") and word != "정상화":
            continue                                   # 멈춘 구간이 따로 있다 — 이 「정상 운행」은 다른 노선이다
        if word == "복구" and _CAUSE_TAIL.match(tail):
            unsettled.append(basis)
            continue
        # 「정상 운행 중」은 끝난 뒤의 상태다. ★「정상화 중」은 아직 진행이다
        in_progress = _IN_PROGRESS_TAIL.match(tail) and not (word.startswith("정상") and word != "정상화")
        if _UNSETTLED_TAIL.match(tail) or in_progress:
            unsettled.append(basis)
        elif _SCHEDULED_TAIL.match(tail):
            scheduled.append(basis)
        else:
            clean.append(basis)
    if clean:
        # `[2026-10-13]` 끝났다는 말과 「아직 ~ 예정」이 같이 있으면 끝이 아니다 — 「응급 복구 완료, 내일 오전 중 정상 공급 예정」
        if scheduled and not _FULL.search(text):
            return NoticeStatus(SCHEDULED, scheduled[0])
        if _PARTIAL.search(text) and not _FULL.search(text):
            return NoticeStatus(PARTIAL, clean[0])
        if _second_opinion is not None and _second_opinion(text) is False:
            return NoticeStatus(DISPUTED, clean[0])
        return NoticeStatus(ENDED, clean[0])
    if scheduled:
        return NoticeStatus(SCHEDULED, scheduled[0])
    if unsettled:
        return NoticeStatus(UNSETTLED, unsettled[0])
    return NoticeStatus(NO_END_SIGNAL)


__all__ = ["DISPUTED", "ENDED", "NO_END_SIGNAL", "NoticeStatus", "PARTIAL", "SCHEDULED", "UNSETTLED", "notice_status", "set_second_opinion"]
