# -*- coding: utf-8 -*-
"""기상청 지진정보 어댑터 — 공공데이터포털 「기상청_지진정보 조회서비스」(15000420).

실측(2026-09-14):

    GET http://apis.data.go.kr/1360000/EqkInfoService/getEqkMsg
        ?serviceKey=…&dataType=JSON&fromTmFc=YYYYMMDD&toTmFc=YYYYMMDD
    지진 있음 → header {"resultCode":"00"}, item 예:
      {"fcTp":2,"tmEqk":20260912062355,"tmFc":202609120645,"lat":-5.09,"lon":106.9,
       "mt":6.6,"dep":359,"loc":"인도네시아 자카르타 북쪽 125km 해역","inT":"",
       "rem":"국내영향없음. …","stnId":108,"tmSeq":1081,"cnt":1,"img":"…"}
    지진 없음 → header {"resultCode":"03","resultMsg":"NO_DATA"}, body 없음 (09-13·09-14 둘 다)

★★`03 NO_DATA` 는 **「지진 없음」(아는 사실)** 이다. 공통 규칙대로 `00` 만 성공으로
  보면 지진이 없는 평소에 늘 「모름」→ 치명(결정 15)이 된다. 그래서 여기서만 03 을
  빈 목록으로 읽는다. 다른 코드는 그대로 모름(`None`)이다.
★조회는 **오늘 기준 3일 전까지**다(실측). 그보다 옛 시각을 물으면 공급자가 거절하고
  그건 모름이다 — 지어내지 않는다.
★`fcTp`(통보 종류)는 판정에 쓰지 않는다. 실제로 본 값은 `2`(국외) 하나뿐이라 코드표를
  믿고 국내·국외를 가르면 모르는 코드에서 틀린다. 판정은 **거리·규모**로 한다
  (`DisruptionCheck._earthquake`). 코드는 정보로만 싣는다.
★항목 하나라도 못 읽으면(좌표·규모 없음) 목록 전체를 모름으로 둔다. 못 읽은 것이
  가까운 강진일 수 있다 — 조용히 빼면 「지진 없음」이 거짓말이 된다.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo

from .base import TravelSource

#: ★https 로도 된다(2026-09-14 실측 200). 키가 평문으로 가지 않게 https 를 쓴다.
ENDPOINT = "https://apis.data.go.kr/1360000/EqkInfoService/getEqkMsg"
KST = ZoneInfo("Asia/Seoul")

#: 성공으로 보는 결과 코드. ★03 = NO_DATA = 그 기간에 지진 없음(실측).
_OK_CODES = {"00", "03"}


def _kst_time(value: Any) -> datetime | None:
    """`20260912062355`(14자리) 또는 `202609120645`(12자리) → KST 시각. 못 읽으면 `None`."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12:
        digits += "00"
    if len(digits) != 14:
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except ValueError:
        return None


def parse_event(item: dict[str, Any]) -> dict[str, Any] | None:
    """공급자 항목 하나 → 사건. 판정에 필요한 값(시각·좌표·규모)이 없으면 `None`."""
    at = _kst_time(item.get("tmEqk"))
    try:
        latitude, longitude = float(item["lat"]), float(item["lon"])
        magnitude = float(item["mt"])
    except (KeyError, TypeError, ValueError):
        return None
    if at is None:
        return None
    announced = _kst_time(item.get("tmFc"))
    depth = item.get("dep")
    return {"at": at.isoformat(), "latitude": latitude, "longitude": longitude,
            "magnitude": magnitude,
            "depth_km": float(depth) if isinstance(depth, (int, float)) else None,
            "location": item.get("loc"), "intensity": item.get("inT") or None,
            "remark": (item.get("rem") or "").strip() or None,
            "notice_type": item.get("fcTp"),
            "announced_at": announced.isoformat() if announced else None}


class KmaEarthquakeSource(TravelSource):
    name = "kma_earthquake"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        response = payload.get("response")
        header = response.get("header") if isinstance(response, dict) else None
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            return None if code in _OK_CODES else f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)

    def recent(self, *, since: datetime, until: datetime) -> dict[str, Any] | None:
        """`[since, until]` 에 난 지진 목록. 없으면 빈 목록, 못 읽으면 `None`."""
        since_kst, until_kst = since.astimezone(KST), until.astimezone(KST)
        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "pageNo": 1, "numOfRows": 100, "dataType": "JSON",
            "fromTmFc": since_kst.strftime("%Y%m%d"), "toTmFc": until_kst.strftime("%Y%m%d")})
        if payload is None:
            return None
        response = payload.get("response") or {}
        code = str((response.get("header") or {}).get("resultCode", ""))
        items: Any = []
        if code != "03":
            try:
                items = response["body"]["items"]["item"]
            except (KeyError, TypeError):
                self._miss("empty_items", str(list(response))[:120])
                return None
        items = items if isinstance(items, list) else [items]
        events = []
        for item in items:
            event = parse_event(item) if isinstance(item, dict) else None
            if event is None:
                self._miss("unparsed_event", repr(item)[:160])
                return None
            # ★날짜 단위로 물었으니 시각으로 다시 자른다(발표일 기준 조회라 앞뒤가 섞인다).
            if since_kst <= datetime.fromisoformat(event["at"]) <= until_kst:
                events.append(event)
        return self.stamp({"events": events, "window": {"from": since_kst.isoformat(),
                                                        "to": until_kst.isoformat()},
                           "kind": "earthquake_list"}, source=self.name)


def window_until(at: datetime | None, now: datetime) -> datetime:
    """판정 창의 끝. ★미래 일정이면 지금까지만 본다 — 아직 안 난 지진은 없다."""
    if at is None:
        return now
    at = at if at.tzinfo else at.replace(tzinfo=KST)
    return min(at, now)


__all__ = ["ENDPOINT", "KmaEarthquakeSource", "parse_event", "window_until"]
