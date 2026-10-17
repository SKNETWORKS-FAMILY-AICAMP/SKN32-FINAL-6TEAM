# -*- coding: utf-8 -*-
"""booking · offers — 기차 · 버스 **예매 링크**(조건을 채워 여는 주소). `[2026-10-14 저녁]` 예약 모듈 확장 3차.

어느 사이트가 GET 주소로 조건(출발 · 도착 · 날짜 · 시각 · 인원)을 받는지 2026-10-14 playdata 에서 직접 열어 봤다(기록 `transit_deeplink_probe`):
- SRT(`etk.srail.kr`) — 받음(조회 폼이 채워져 열림 · 목록까지 자동으로 뜨는지는 확인 안 함). 역 코드 = 코레일 역 코드(수서 0551 · 부산 0020).
- 트립닷컴 기차(`kr.trip.com/trains`) — 받음(KTX 목록 · 시각 · 요금까지 바로 뜸). 도시 코드 = 「KR」+ 코레일 역 코드. 수서 출발(SRT) 운행도 목록에 나온다(17:0x).
- 버스타고(`bustago.or.kr`) — 받음(폼이 채워짐 · 목록 자동 표시는 확인 안 함). 터미널 id 는 버스타고 고유(`SUBURBS_TERMINALS`).
- 코레일(세션 · 자동화 차단) · 코버스(POST 전용) · 티머니(GET 405) — 안 받음 → 첫 화면 주소(`transit.BOOKING_SITES`)만.

★사전은 그날 페이지에서 읽은 값이다(코레일 역 코드 = SRT 역 목록 36곳 + 트립닷컴 역 검색 25곳, 버스타고 터미널 목록 820곳 중 예매 가능 큰 곳).
  없는 곳은 링크를 **안 만든다**(틀린 역으로 가지 않게) — 그때는 첫 화면 링크로 떨어진다. 어느 운행을 고른 채로 여는 주소는 어디에도 없다 →
  모두 `link_kind="route_search"`(항공의 「검색 결과 페이지」와 같은 등급).
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

#: 코레일 역 코드(= SRT · 트립닷컴). 열쇠는 TAGO 역 이름(`transit.STATIONS` 값) — 괄호 · 표기 차이는 `_rail_code` 가 맞춘다.
RAIL_CODES: dict[str, str] = {
    "서울": "0001", "용산": "0104", "수서": "0551", "청량리": "0090", "영등포": "0002", "행신": "0390", "광명": "0501", "수원": "0003",
    "평택": "0004", "평택지제": "0553", "동탄": "0552", "천안아산": "0502", "천안": "0005", "오송": "0297", "대전": "0010", "서대전": "0025",
    "김천구미": "0507", "김천": "0012", "구미": "0013", "동대구": "0015", "서대구": "0506", "경산": "0024", "경주": "0508", "포항": "0515",
    "안동": "0526", "영주": "0098", "울산": "0509", "부산": "0020", "구포": "0019", "물금": "0224", "밀양": "0017", "마산": "0059",
    "창원": "0057", "창원중앙": "0512", "진영": "0056", "진주": "0063", "익산": "0030", "전주": "0045", "정읍": "0033", "남원": "0048",
    "광주송정": "0036", "나주": "0037", "목포": "0041", "순천": "0051", "여수엑스포": "0053", "여천": "0139", "곡성": "0049", "구례구": "0050",
    "강릉": "0115", "춘천": "0153", "원주": "0525", "만종": "0326", "평창": "0518", "진부": "0519", "동해": "0113", "제천": "0093",
    "충주": "0073", "논산": "0027", "공주": "0514",
}
#: 트립닷컴 · SRT 가 안 받는 곳(역 검색에 없음, 10-14): 인천공항T1 · 검암 — 사전에 없으니 링크가 안 만들어진다.

#: 버스타고 터미널 — 이름 → (id, 구분값). 구분값은 버스타고가 준 `TERMINAL_TYPE`(동서울 「I」 처럼 주소의 `startType` 으로 그대로 보낸다 —
#: 「I」 말고 「1」 「2」 로도 열리는지는 확인 안 함). 820곳 중 시 · 도 큰 터미널만 손으로 옮김(10-14).
SUBURBS_TERMINALS: dict[str, tuple[str, str]] = {
    "동서울": ("0001", "I"), "서울남부": ("0004", "I"), "김포공항": ("0010", "1"), "잠실역": ("0009", "I"),
    "부산동부(노포)": ("9001", "I"), "부산서부": ("9002", "1"), "부산해운대": ("9007", "1"), "부산동래": ("9010", "2"),
    "동대구": ("9201", "1"), "대구북부": ("9202", "1"), "대구서부": ("9204", "I"), "서대구역": ("9265", "2"),
    "광주(유ㆍ스퀘어)": ("9401", "I"), "송정역": ("9428", "I"), "대전복합": ("9503", "I"), "대전서부": ("9504", "I"), "유성복합": ("9502", "I"),
    "대전청사(선사유적)": ("9505", "1"), "울산": ("9601", "1"), "언양": ("9602", "1"),
    "인천": ("9302", "I"), "인천공항T1": ("9303", "I"), "인천공항T2": ("9337", "I"),
    "수원터미널": ("1012", "1"), "서수원": ("1008", "I"), "성남종합": ("1010", "I"), "고양종합터미널": ("1782", "1"), "부천": ("1007", "1"),
    "안산": ("1015", "I"), "안양": ("1018", "2"), "의정부": ("1027", "I"), "용인": ("1025", "1"), "평택": ("1035", "I"), "이천": ("1028", "I"),
    "하남": ("1051", "1"), "동두천": ("1004", "I"), "여주": ("1021", "I"), "안성": ("1232", "1"), "오산": ("1023", "I"), "시흥": ("1013", "I"),
    "춘천": ("2037", "1"), "강릉시외터미널": ("2051", "1"), "원주": ("2028", "I"), "속초시외": ("2019", "I"), "동해": ("2671", "1"),
    "삼척": ("2015", "I"), "양양": ("2024", "I"), "평창": ("2040", "I"), "횡성": ("2047", "1"), "영월": ("2025", "I"), "태백": ("2039", "1"),
    "정선": ("2033", "1"), "홍천": ("2044", "I"), "인제": ("2031", "I"), "주문진": ("2034", "I"),
    "청주": ("3015", "I"), "청주북부터미널": ("3026", "I"), "충주": ("3017", "I"), "제천": ("3011", "1"), "단양": ("3003", "1"),
    "보은": ("3094", "1"), "증평": ("3013", "1"), "음성": ("3010", "1"), "진천": ("3014", "1"),
    "천안": ("4019", "I"), "천안아산역": ("4354", "I"), "아산(온양)": ("4333", "I"), "공주": ("4003", "I"), "논산": ("4023", "I"),
    "서산": ("4010", "I"), "태안": ("4021", "I"), "보령": ("4024", "1"), "홍성": ("4090", "I"), "예산": ("4015", "I"), "당진": ("4006", "I"),
    "부여": ("4008", "I"), "세종시": ("4292", "I"), "세종청사": ("4318", "1"), "조치원": ("4068", "I"), "안면도": ("4025", "I"),
    "전주": ("7033", "1"), "익산": ("7026", "1"), "군산": ("7006", "1"), "정읍": ("7084", "1"), "남원": ("7010", "1"), "김제": ("7009", "I"),
    "부안": ("7018", "1"), "고창": ("7003", "I"), "무주": ("7015", "I"),
    "목포": ("8024", "I"), "순천": ("8038", "I"), "여수": ("8041", "I"), "광양": ("8006", "1"), "나주": ("8009", "I"), "담양": ("8014", "I"),
    "해남": ("8062", "I"), "완도": ("8050", "I"), "보성": ("8031", "1"), "강진": ("8001", "1"), "영암": ("8047", "1"), "무안": ("8025", "I"),
    "경주시외": ("5007", "1"), "포항": ("5071", "1"), "안동": ("5043", "1"), "영주": ("5046", "I"), "구미": ("5011", "I"), "김천": ("5016", "1"),
    "경산": ("5005", "1"), "영천": ("5047", "I"), "상주종합버스터미널": ("5033", "I"), "문경": ("5026", "I"), "영덕": ("5044", "1"),
    "울진": ("5054", "I"), "점촌": ("5060", "1"),
    "마산": ("6010", "I"), "마산남부": ("6009", "I"), "진주": ("6038", "1"), "통영종합터미널": ("6029", "1"), "거제(고현)": ("6003", "I"),
    "김해": ("6006", "I"), "김해공항": ("6295", "1"), "양산": ("6018", "1"), "밀양": ("6011", "1"), "사천": ("6014", "I"), "남해": ("6007", "1"),
    "하동": ("6030", "I"), "거창": ("6001", "1"), "합천": ("6033", "I"), "함양": ("6032", "1"), "창녕": ("6044", "1"), "진해": ("6025", "1"),
    "장승포": ("6455", "1"),
}

#: SRT 만 서는 역 — 이 역이 출발 · 도착에 끼면 SRT 운행이다(등급 이름으로는 못 가른다)
SRT_ONLY_STATIONS = frozenset({"수서", "동탄"})

SRT_URL = "https://etk.srail.kr/hpg/hra/01/selectScheduleList.do"
TRIP_URL = "https://kr.trip.com/trains/asia/list"
BUSTAGO_URL = "https://www.bustago.or.kr/newweb/kr/ticket/ticket.do"

_PAREN = re.compile(r"\(.*?\)|\s+")
_DROP = re.compile(r"터미널|종합|시외버스|고속버스|시외|고속|버스|공용|정류소|정류장|역$")


def _rail_code(name: str | None) -> str | None:
    """TAGO 역 이름 → 코레일 역 코드. 그대로 → 괄호 뺀 이름(「울산(통도사)」 → 「울산」 · 「진부(오대산)」 → 「진부」 · 「김천(구미)」 → 「김천구미」)."""
    if not name:
        return None
    text = str(name).strip()
    if text in RAIL_CODES:
        return RAIL_CODES[text]
    squashed = re.sub(r"[()\s]", "", text)                                    # 「김천(구미)」 → 「김천구미」
    if squashed in RAIL_CODES:
        return RAIL_CODES[squashed]
    bare = _PAREN.sub("", text).replace("역", "")                             # 「울산(통도사)」 → 「울산」
    return RAIL_CODES.get(bare)


def _bare(name: str | None) -> str:
    return _PAREN.sub("", str(name or "")).replace("역", "")


def _norm_terminal(name: str) -> str:
    return _DROP.sub("", _PAREN.sub("", str(name or ""))).strip()


def _terminal(name: str | None) -> tuple[str, str, str] | None:
    """TAGO 터미널 이름 → 버스타고 (이름, id, 구분값). 그대로 → 정리한 이름 같음 → 정리한 이름이 하나뿐인 앞머리 관계. 애매하면 `None`."""
    if not name:
        return None
    text = str(name).strip()
    if text in SUBURBS_TERMINALS:
        return (text, *SUBURBS_TERMINALS[text])
    wanted = _norm_terminal(text)
    if len(wanted) < 2:
        return None
    same = [(key, *value) for key, value in SUBURBS_TERMINALS.items() if _norm_terminal(key) == wanted]
    if len(same) == 1:
        return same[0]
    near = [(key, *value) for key, value in SUBURBS_TERMINALS.items()
            if _norm_terminal(key).startswith(wanted) or wanted.startswith(_norm_terminal(key))]
    return near[0] if len(near) == 1 else None


def _ymd(date: str | None) -> str | None:
    text = str(date or "")
    return text.replace("-", "") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None


def _hour(clock: str | None) -> str:
    text = str(clock or "")
    return text[:2] if re.match(r"\d{2}:\d{2}", text) else "00"


def srt_link(dep: str | None, arr: str | None, date: str | None, *, hour: str = "00", adults: int = 1) -> str | None:
    dep_code, arr_code, ymd = _rail_code(dep), _rail_code(arr), _ymd(date)
    if not (dep_code and arr_code and ymd):
        return None
    people = max(1, int(adults or 1))
    return (f"{SRT_URL}?pageId=TK0101010000&dptRsStnCd={dep_code}&arvRsStnCd={arr_code}&dptDt={ymd}&dptTm={hour}0000"
            f"&psgNum={people}&psgInfoPerPrnb1={people}")


def trip_link(dep: str | None, arr: str | None, date: str | None, *, hour: str = "00", adults: int = 1) -> str | None:
    dep_code, arr_code = _rail_code(dep), _rail_code(arr)
    if not (dep_code and arr_code and _ymd(date)):
        return None
    people = max(1, int(adults or 1))
    return (f"{TRIP_URL}?tripTab=train&scheduleType=single&hidadultnum={people}&hidchildnum=0&biztype=SouthKorea"
            f"&departurecountrycode=KR&arrivalcountrycode=KR&departdate={date}&departhouript={hour}&departminuteipt=00"
            f"&departurecitycode=KR{dep_code}&arrivalcitycode=KR{arr_code}")


def bustago_link(dep: str | None, arr: str | None, date: str | None, *, hour: str = "00", adults: int = 1) -> str | None:
    start, finish = _terminal(dep), _terminal(arr)
    if not (start and finish and _ymd(date)):
        return None
    people = max(1, int(adults or 1))
    return (f"{BUSTAGO_URL}?startType={start[2]}&start={quote(start[0])}&startId={start[1]}&finish={quote(finish[0])}&finishId={finish[1]}"
            f"&goDateField={date}&goTimeField={hour}&adultCnt={people}&universityCnt=0&studentCnt=0&childrenCnt=0")


def run_links(option: dict[str, Any], *, adults: int | None = None) -> list[dict[str, Any]]:
    """운행 하나의 예매 링크(조건을 채워 여는 주소) — 열차는 SRT 운행이면 SRT, 아니면 트립닷컴(코레일 열차); 시외버스는 버스타고.
    고속버스 · 사전에 없는 역 · 터미널은 빈 목록(부르는 쪽이 첫 화면 링크로 떨어뜨린다)."""
    hour = _hour(option.get("depart"))
    people = adults or 1
    dep, arr, date = option.get("origin"), option.get("destination"), option.get("date")
    links: list[dict[str, Any]] = []
    if option.get("mode") == "train":
        # ★TAGO 는 SRT 운행도 등급을 「KTX」 「KTX-산천」으로 준다(10-14 17:06 수서→부산 40편 전부) — 등급으로는 SRT 를 못 가른다.
        #   수서 · 동탄은 SRT 만 서는 역이라 그 역이 끼면 SRT 주소를 앞에 둔다. 트립닷컴은 수서 출발 운행도 목록에 보여 줬다(17:0x 직접 열어 봄).
        grade = str(option.get("grade") or "")
        is_srt = grade.upper().startswith("SRT") or bool({_bare(dep), _bare(arr)} & SRT_ONLY_STATIONS)
        if is_srt:
            url = srt_link(dep, arr, date, hour=hour, adults=people)
            if url:
                links.append({"name": "SRT 예매(출발 · 도착 · 날짜 · 시각 채움)", "url": url, "link_kind": "route_search", "site": "srt"})
        url = trip_link(dep, arr, date, hour=hour, adults=people)
        if url:
            links.append({"name": "트립닷컴 기차(출발 · 도착 · 날짜 채움)", "url": url, "link_kind": "route_search", "site": "trip"})
    elif option.get("mode") == "bus" and option.get("kind") == "suburbs":
        url = bustago_link(dep, arr, date, hour=hour, adults=people)
        if url:
            links.append({"name": "버스타고 시외버스 예매(터미널 · 날짜 · 시각 · 인원 채움)", "url": url, "link_kind": "route_search", "site": "bustago"})
    return links


__all__ = ["RAIL_CODES", "SUBURBS_TERMINALS", "bustago_link", "run_links", "srt_link", "trip_link"]
