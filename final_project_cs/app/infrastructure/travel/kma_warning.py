# -*- coding: utf-8 -*-
"""기상청 기상특보 어댑터 — 공공데이터포털 「기상청_기상특보 조회서비스」(15000415).

★예보는 **당길 때** 오고 특보는 **사건 때** 온다. 그래서 지속관리 루프의 트리거
  재료이고(`.env.apikeys.example` 53행), Team 에게는 「지금 그 지역에 무엇이
  발효 중인가」라는 **사실 한 줄**이다.

실측(2026-09-14):

    GET https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus
        ?serviceKey=…&dataType=JSON
    → header {"resultCode":"00"}, item 1건:
      {"t6":"o 없 음","t7":"o 없음","tmEf":"202609110800","tmFc":202609110600,"tmSeq":77}

    getWthrWrnMsg(stnId=109) 의 t6 표본:  "o 풍랑주의보 : 서해중부바깥먼바다"

  ★`t6`(발효 현황)·`t7`(예비특보)은 **정해진 필드가 아니라 글**이다. 한 줄이
  `o {특보 종류} : {구역, 구역, …}` 이고, 구역 안에 괄호와 쉼표가 들어가며
  (`경기도(수원, 성남)`), 긴 목록은 다음 줄로 이어진다. 파서가 그 셋을 다룬다.
  「없음」은 **`o 없 음`(띄어 씀)** 과 `o 없음` 두 모양이 실제로 섞여 온다.

★이력(`getWthrWrnMsg`)은 **오늘 기준 6일 전까지만** 조회된다 —
  `resultCode 99 「최대 조회 기간은 오늘 기준으로 6일 전까지입니다」`(실측).
  그래서 과거 특보로 무엇을 재구성하려면 우리가 받아 쌓아야 한다.

★「발효 중인 특보 없음」은 **아는 사실**이다(빈 목록). 「조회 실패」는 모름이다
  (`None`). 둘을 섞으면 조회가 죽은 날 「특보 없음」이라고 답한다.
"""
from __future__ import annotations

import re
from typing import Any

from .base import TravelSource

ENDPOINT = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getPwnStatus"

#: 「없음」 판정. ★띄어 쓴 「없 음」이 실제로 온다(2026-09-14 실측).
_NONE = re.compile(r"^없\s*음$")


def _split_areas(text: str) -> list[str]:
    """쉼표로 가르되 **괄호 안 쉼표는 가르지 않는다** — `경기도(수원, 성남)`."""
    areas, depth, current = [], 0, []
    for char in text:
        if char in "(（":
            depth += 1
        elif char in ")）":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            areas.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    areas.append("".join(current).strip())
    return [area for area in areas if area]


def parse_status(text: Any) -> list[dict[str, Any]] | None:
    """`t6`/`t7` 글 → `[{"kind": "호우경보", "areas": [...]}]`.

    빈 목록 = 발효 중인 것이 **없다**(아는 사실). `None` = 글을 못 읽었다(모름).
    """
    if text is None:
        return None
    lines = [line.strip() for line in str(text).replace("\r", "").split("\n")]
    entries: list[list[str]] = []
    for line in lines:
        if not line:
            continue
        if line.startswith("o ") or line.startswith("o\t") or line == "o":
            entries.append([line[1:].strip()])
        elif entries:
            entries[-1].append(line)        # ★긴 구역 목록이 다음 줄로 이어진다
        else:
            return None                      # ★모르는 모양 — 지어내지 않는다
    warnings = []
    for parts in entries:
        body = " ".join(parts).strip()
        if _NONE.match(body.replace(" ", " ")) or _NONE.match(body):
            continue
        kind, sep, rest = body.partition(":")
        if not sep:
            return None
        warnings.append({"kind": kind.strip(), "areas": _split_areas(rest)})
    return warnings


def _as_iso(value: Any) -> str | None:
    """`202609110600` → `2026-09-11T06:00`. 못 읽으면 `None`."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 12:
        return None
    return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}"


class KmaWarningSource(TravelSource):
    name = "kma_warning"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """기상청은 `response.header.resultCode` 로 답한다. `00` 만 성공이다."""
        response = payload.get("response")
        header = response.get("header") if isinstance(response, dict) else None
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            return None if code == "00" else f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)

    def active(self, *, region: str = "서울") -> dict[str, Any] | None:
        """지금 발효 중인 특보와, 그중 `region` 을 덮는 것. 못 읽으면 `None`."""
        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "pageNo": 1, "numOfRows": 10, "dataType": "JSON"})
        if payload is None:
            return None
        try:
            items = payload["response"]["body"]["items"]["item"]
        except (KeyError, TypeError):
            self._miss("empty_items", str(list(payload))[:120])
            return None
        if not isinstance(items, list) or not items:
            self._miss("empty_items", "item 없음")
            return None

        # ★가장 최근 발표 한 건. 순서를 믿지 않고 (발표시각, 차수)로 고른다.
        latest = max(items, key=lambda item: (str(item.get("tmFc")), int(item.get("tmSeq") or 0)))
        in_effect = parse_status(latest.get("t6"))
        preliminary = parse_status(latest.get("t7"))
        if in_effect is None:
            self._miss("unparsed_status", repr(latest.get("t6"))[:160])
            return None

        covering = [w for w in in_effect if any(region in area for area in w["areas"])]
        return self.stamp({
            "region": region,
            "announced_at": _as_iso(latest.get("tmFc")),
            "effective_at": _as_iso(latest.get("tmEf")),
            "in_effect": in_effect,
            # ★예비특보를 못 읽어도 발효 현황은 살린다 — 둘은 다른 사실이다.
            "preliminary": preliminary,
            "for_region": covering,
            "kind": "warning_status",
        }, source=self.name)


__all__ = ["ENDPOINT", "KmaWarningSource", "parse_status"]
