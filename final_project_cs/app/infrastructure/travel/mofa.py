# -*- coding: utf-8 -*-
"""외교부 국가·지역별 여행경보 어댑터 — 공공데이터포털 15076237.

★v11 은 **서울 1도시 MVP** 다(§1). 이 소스는 해외로 넓힐 때를 위한 것이라 지금
  이것을 부르는 Team 은 없다 — 도구(`read.travel_advisory`)와 소스만 붙여 둔다.
  날씨에 합치지 않은 이유: 날씨는 「그 좌표·그 시각」, 여행경보는 「그 나라·
  며칠~몇 주」다. 대체 소스 사슬(`weather_chain.py`)에 섞으면 「날씨가 없으면
  여행경보로 대신한다」가 된다.

실측(2026-09-14, 공공데이터포털 공통 키):

    GET https://apis.data.go.kr/1262000/TravelAlarmService2/getTravelAlarmList2
        ?serviceKey=…&returnType=JSON&cond[country_iso_alp2::EQ]=JP
    → header {"resultCode":"0","resultMsg":"정상"}   ★「00」이 아니라 「0」이다
      item: {"alarm_lvl":"3","country_nm":"일본","country_iso_alp2":"JP",
             "region_ty":"일부","remark":"후쿠시마 원전 반경 30km 이내 및 …",
             "written_dt":null}

    TravelWarningServiceV3 → HTTP 403 (이 키로는 안 열려 있다)

★경보가 **없는 나라**는 목록이 비어 온다. 그건 「경보 없음」이라는 아는 사실이다.
  조회 실패(`None`)와 섞지 않는다.
"""
from __future__ import annotations

import re
from typing import Any

from .base import TravelSource

ENDPOINT = "https://apis.data.go.kr/1262000/TravelAlarmService2/getTravelAlarmList2"

#: 외교부 여행경보 4단계.
LEVELS = {1: "여행유의", 2: "여행자제", 3: "출국권고", 4: "여행금지"}

_ISO2 = re.compile(r"^[A-Za-z]{2}$")


class MofaTravelAlarm(TravelSource):
    name = "mofa"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """외교부는 성공 코드가 **`0`** 이다(기상청은 `00`). 둘 다 성공으로 본다."""
        response = payload.get("response")
        header = response.get("header") if isinstance(response, dict) else None
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            return None if code in ("0", "00") else f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)

    def country(self, *, iso2: str) -> dict[str, Any] | None:
        """그 나라의 여행경보. 경보가 없으면 `alarms=[]`, 못 읽으면 `None`."""
        if not isinstance(iso2, str) or not _ISO2.match(iso2):
            # ★나라를 모르면 묻지 않는다. 전 세계 목록을 받아 추측하지 않는다.
            self._miss("bad_country_code", repr(iso2))
            return None
        code = iso2.upper()
        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "returnType": "JSON", "numOfRows": 50, "pageNo": 1,
            "cond[country_iso_alp2::EQ]": code})
        if payload is None:
            return None
        try:
            body = payload["response"]["body"]
        except (KeyError, TypeError):
            self._miss("unexpected_shape", str(list(payload))[:120])
            return None

        items = (body.get("items") or {}) if isinstance(body, dict) else {}
        rows = items.get("item") if isinstance(items, dict) else None
        if rows is None:
            rows = []                    # ★빈 목록 = 경보 없음(아는 사실)
        if isinstance(rows, dict):
            rows = [rows]

        alarms = []
        for row in rows:
            try:
                level = int(row.get("alarm_lvl"))
            except (TypeError, ValueError):
                self._miss("bad_alarm_level", repr(row.get("alarm_lvl")))
                return None              # ★단계를 못 읽은 경보는 지어내지 않는다
            alarms.append({
                "level": level,
                "level_name": LEVELS.get(level),
                "region_type": row.get("region_ty"),    # 전체 / 일부
                "remark": row.get("remark"),
                "written_at": row.get("written_dt"),
            })

        name = rows[0].get("country_nm") if rows else None
        return self.stamp({
            "country_iso2": code,
            "country_name": name,
            "alarms": alarms,
            "max_level": max((a["level"] for a in alarms), default=0),
            "kind": "travel_advisory",
        }, source=self.name)


__all__ = ["ENDPOINT", "LEVELS", "MofaTravelAlarm"]
