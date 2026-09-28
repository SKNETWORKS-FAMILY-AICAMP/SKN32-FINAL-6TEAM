# -*- coding: utf-8 -*-
"""경찰청 UTIC 도시교통정보센터 — 돌발정보(사고·공사·행사·집회).

실측(2026-09-14, 발급 키 둘):

    GET https://www.utic.go.kr/guide/imsOpenData.do?key=…
    → text/xml  <result><record>…</record>…</result>  (전국 182건)
      record 칸: incidentId · incidenteTypeCd · incidenteSubTypeCd · addressJibun ·
                 locationDataX(경도) · locationDataY(위도) · incidentTitle
                 (「[사고] 올림픽대로 동작대교JC 에서 … [차량사고] …」) ·
                 startDate·endDate(「2026년 09월 14일  15시 35분」) · lane · roadName ·
                 controlType · important · updateDate
    등록 안 된 IP → HTTP 200 `[{"resultCode":"03","resultMsg":"허용된 IP가 아닙니다."}]`
                    (★오류만 JSON 이다 — 공통 규칙이 「XML 아님」으로 세고 본문을 로그에 남긴다)

★키가 **IP 에 묶여 있다.** 조립이 나가는 길(바로 / 고정 IP 서버 경유)에 맞는 키를 준다
  (`Settings.utic_key`). 실측: key 1 을 서버 경유로 부르면 위의 03 이 온다.
★인자가 키뿐이라 장소가 달라도 **같은 요청**이다 — 응답 캐시를 나눠 쓴다.
★분류는 ITS 와 같은 기준으로 한다(`its_traffic.py`):
    이상: 사고 · 차로 칸 「전체」「양방향」 · 집회·행사·시위·마라톤
    주의: 그 밖(부분 차로 공사 등)
  ★「통제」 낱말로는 가르지 않는다 — ITS 에서 `[공사/통제]` 가 대부분이었다(같은 함정).
  `incidenteTypeCd`·`controlType` 의 코드표는 못 봤다 — 판정에 안 쓰고 정보로만 싣는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from .base import TravelSource
from .its_traffic import (DEFAULT_RADIUS_M, GATHERING_TAGS, OPEN_ENDED_HOURS, _distance_m,
                          _parse_time)

ENDPOINT = "https://www.utic.go.kr/guide/imsOpenData.do"
KST = ZoneInfo("Asia/Seoul")
_TAG = re.compile(r"\[([^\]]+)\]")


def title_tags(title: str | None) -> list[str]:
    """제목의 [표시] 들 — 「[사고] … [차량사고] …」 → ["사고", "차량사고"]."""
    tags: set[str] = set()
    for group in _TAG.findall(title or ""):
        tags.update(part.strip() for part in re.split(r"[/,·]", group) if part.strip())
    return sorted(tags)


def classify(record: dict[str, Any]) -> tuple[str, str]:
    """(`disruption` | `advisory`, 이유)."""
    tags = set(title_tags(record.get("incidentTitle")))
    lane = str(record.get("lane") or "")
    if any("사고" in tag for tag in tags):
        return "disruption", "교통사고"
    if "전체" in lane or "양방향" in lane:
        return "disruption", "전체 차로 통제"
    gathering = {g for g in GATHERING_TAGS if any(g in tag for tag in tags)}
    if gathering:
        return "disruption", "집회·행사 " + ",".join(sorted(gathering))
    return "advisory", "부분 차로 " + (",".join(sorted(tags)) or "돌발")


def parse_records(text: str) -> list[dict[str, str]] | None:
    """XML → 레코드 목록. 못 읽으면 `None`."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return None
    return [{child.tag: (child.text or "").strip() for child in record}
            for record in root.iter("record")]


class UticIncidents(TravelSource):
    name = "utic"

    def __init__(self, *, service_key: str, now=None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        self._now = now or (lambda: datetime.now(KST))

    def records(self) -> list[dict[str, str]] | None:
        """전국 돌발 레코드(캐시를 나눠 쓴다). 못 읽으면 `None`."""
        text = self._fetch_xml(ENDPOINT, {"key": self._key})
        if text is None:
            return None
        records = parse_records(text)
        if records is None:
            self._miss("bad_xml", text[:120])
        return records

    def active_at(self, record: dict[str, str], at: datetime) -> bool:
        """그 시각에 걸리는 돌발인가 — 시작 전·끝난 뒤·끝 모르는 먼 미래는 아니다."""
        start, end = _parse_time(record.get("startDate")), _parse_time(record.get("endDate"))
        if start is not None and at < start:
            return False
        if end is not None and at > end:
            return False
        return not (end is None and at > self._now() + timedelta(hours=OPEN_ENDED_HOURS))

    def near(self, *, latitude: float, longitude: float, at: datetime,
             radius_m: int = DEFAULT_RADIUS_M) -> dict[str, Any] | None:
        """장소 반경 안에서 `at` 시각에 걸리는 돌발. 못 읽었으면 `None`(ITS 와 같은 모양)."""
        at = at if at.tzinfo else at.replace(tzinfo=KST)
        records = self.records()
        if records is None:
            return None

        now = self._now()
        disruptions, advisories = [], []
        for record in records:
            try:
                x, y = float(record.get("locationDataX")), float(record.get("locationDataY"))
            except (TypeError, ValueError):
                self._miss("bad_coordinates", repr(record.get("locationDataX")))
                continue
            distance = _distance_m(latitude, longitude, y, x)
            if distance > radius_m:
                continue
            start, end = _parse_time(record.get("startDate")), _parse_time(record.get("endDate"))
            if start is not None and at < start:
                continue                      # 그 시각엔 아직 시작 전
            if end is not None and at > end:
                continue                      # 그 시각엔 이미 끝남
            if end is None and at > now + timedelta(hours=OPEN_ENDED_HOURS):
                continue                      # ★끝 시각 모르는 돌발을 먼 미래까지 늘리지 않는다
            level, reason = classify(record)
            entry = {"reason": reason, "event_type": ",".join(title_tags(record.get("incidentTitle"))),
                     "road": record.get("roadName"), "section": record.get("addressJibun"),
                     "lanes": record.get("lane"), "tags": title_tags(record.get("incidentTitle")),
                     "distance_m": round(distance),
                     "starts_at": start.isoformat() if start else None,
                     "ends_at": end.isoformat() if end else None,
                     "message": record.get("incidentTitle"),
                     "incident_id": record.get("incidentId"),
                     "type_code": record.get("incidenteTypeCd"),
                     "control_type": record.get("controlType")}
            (disruptions if level == "disruption" else advisories).append(entry)
        return self.stamp({"radius_m": radius_m, "at": at.isoformat(),
                           "total_records": len(records), "for_place": disruptions,
                           "advisories": advisories, "kind": "traffic_events"},
                          source=self.name)


class UticRouteEvents:
    """감시 루프의 **경로 사건** 소스 — `ReplayRouteEvents.affecting()` 과 같은 모양.

    ★답하는 대상은 **도로(`도로:이름`)뿐**이다. 지금 걸려 있는 사고·전체 차로 통제·집회·행사가
      그 도로에 있으면 `road_control`. 부분 차로 공사(주의)는 경로를 끊지 않는다.
    ★지하철 무정차(`N호선:역`)·버스·도보는 실시간 소스가 없다. 그 대상은 「사건 없음」으로
      답하지 않고 `unsupported()` 로 **확인 못 한 대상**이라고 드러낸다 — 감시 결과가 센다.
    ★UTIC 를 못 읽으면 `None` — 감시 루프가 그 이동 항목을 치명으로 남긴다(결정 15).
    """

    ROAD = "도로:"

    def __init__(self, incidents: UticIncidents) -> None:
        self.incidents = incidents
        self.name = "utic_route_events"

    def unsupported(self, targets: list[str]) -> list[str]:
        return [target for target in targets if not target.startswith(self.ROAD)]

    def affecting(self, targets: list[str], at: datetime | None = None
                  ) -> dict[str, dict[str, Any]] | None:
        roads = [t for t in targets if t.startswith(self.ROAD)]
        if not roads:
            return {}
        records = self.incidents.records()
        if records is None:
            return None
        moment = at or self.incidents._now()
        found: dict[str, dict[str, Any]] = {}
        for target in roads:
            road = target[len(self.ROAD):]
            for record in records:
                if road not in (record.get("roadName") or "") and \
                        road not in (record.get("incidentTitle") or ""):
                    continue
                level, reason = classify(record)
                if level != "disruption" or not self.incidents.active_at(record, moment):
                    continue
                end = _parse_time(record.get("endDate"))
                # ★문구는 공급자 값으로만 만든다 — 없는 이유를 붙이지 않는다.
                found[target] = self.incidents.stamp({
                    "effect": "road_control", "reason": reason,
                    # ☆처음엔 「{reason}이(가) 있습니다」였다 — 실측 통지가 「통제이(가)」로 어색했다
                    "summary": f"{road} {reason}(경찰청 UTIC 돌발정보)",
                    "title": record.get("incidentTitle"),
                    "incident_id": record.get("incidentId"),
                    "ends_at": end.isoformat() if end else None}, source="utic")
                break
        return found


__all__ = ["ENDPOINT", "UticIncidents", "UticRouteEvents", "classify", "parse_records",
           "title_tags"]
