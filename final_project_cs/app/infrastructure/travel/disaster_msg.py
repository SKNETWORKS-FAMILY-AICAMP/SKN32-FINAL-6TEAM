# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 — 재난안전데이터 공유플랫폼(safetydata.go.kr).

★★★**이 파일은 `tour_api.py`와 격이 다르다 — 실 키로 검증되지 않았다.**
  `tour_api.py`는 "실측(2026-09-10, 실 키로)"라고 못박을 수 있었지만, 이
  어댑터는 **API 키를 발급받지 못해 실제 호출을 한 번도 못 해 봤다.**
  아래는 2026-09-20 웹 조사로 확인한 것과 추정한 것을 나눈 것이다 —
  실 키가 생기면 **가장 먼저 이 구분을 검증하고 이 주석을 갱신한다.**

**확인됨** (같은 플랫폼의 자매 API·공식 데이터셋 페이지에서 실제 코드/설명 확인):
  - 기본 URL 패턴: `https://www.safetydata.go.kr/V2/api/DSSP-IF-<번호>`
    (이 API는 `DSSP-IF-00247` — data.go.kr 15134001 "행정안전부_긴급재난문자"
    와 같은 데이터셋의 V2 인터페이스)
  - 공통 파라미터: `serviceKey`(대문자 K) · `returnType=json` · `pageNo` ·
    `numOfRows`
  - 지역 필터 파라미터 `rgnNm` 존재(서버가 지역명으로 거를 수 있다)
  - 응답은 최상위 `body` 키 아래 **배열**(자매 API인 대피소 DSSP-IF-00195 로
    확인 — `data.get("body", [])`)
  - 응답 필드명 `MSG_CN`·`RCPTN_RGN_NM`·`EMRG_STEP_NM`·`CRT_DT`·`DST_SE_NM`
    (검색으로 데이터셋 설명에서 확인 — `wiki/records/reports/`의 013·016
    마이그레이션 설계와 같은 이름이다)

**추정(미검증)**:
  - 서버 쪽 날짜 범위 필터 파라미터 이름 — **그래서 이 클라이언트는 서버
    필터에 기대지 않는다.** 넓게 받아서(`rgnNm`만 걸고) **클라이언트 쪽에서
    `CRT_DT`로 최근 것만 자른다**(`_recent_only`). 서버가 모르는 파라미터를
    보내 응답이 깨지는 위험을 피한다.
  - 오류 봉투 모양(`header.resultCode` 류) — data.go.kr 계열 관례를
    방어적으로만 본다. 확신하지 못하므로 **HTTP 200 이고 `body` 가 없으면
    무조건 `body_error`로 센다**(성공으로 잘못 읽지 않는다, `CLAUDE.md` §0.2).

**확인됨(2026-09-21 실호출)**:
  - `CRT_DT` 포맷: `"2023/09/19 12:22:17"` 형태 — `%Y/%m/%d %H:%M:%S`.
    처음엔 14자리 `yyyyMMddHHmmss`로 추정했으나 틀렸다. 못 읽으면
    그 메시지는 "언제인지 모름"으로 **걸러내지 않고 포함시킨다**.

★규율(①~④)은 `base.py`의 `TravelSource`를 그대로 따른다. ★★지역·주제
  관련성을 이 클라이언트가 판정하지 않는다 — 원문(`MSG_CN`)을 해석하지 않고
  원본 그대로 돌려준다. 판정(`_disaster_blocks`)은 Team 쪽(`activity.py`) 몫이다.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .base import TravelSource

BASE_URL = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"

#: `CRT_DT` 포맷 — 실호출 확인(2026-09-21): "2023/09/19 12:22:17" 형태.
_CRT_DT_FORMAT = "%Y/%m/%d %H:%M:%S"

_FIELDS = ("SN", "CRT_DT", "MSG_CN", "RCPTN_RGN_NM", "DST_SE_NM", "EMRG_STEP_NM")


class DisasterMsgSource(TravelSource):
    name = "disaster_msg"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    def _common(self) -> dict[str, Any]:
        return {"serviceKey": self._key, "returnType": "json",
                "pageNo": "1", "numOfRows": "100"}

    # ── 조회 ────────────────────────────────────────────────────
    def recent(self, *, since_hours: float = 6.0,
               region_name: str | None = None) -> dict[str, Any] | None:
        """최근 `since_hours` 시간 안에 발령된 재난문자. 못 가져오면 `None`.

        ★`region_name`을 주면 서버 쪽 `rgnNm`으로 좁혀 받는다(확인된 파라미터).
          안 주면 **전국**이 돌아온다 — 이 API는 좌표로 거르지 않는다.

        ★★**날짜 범위는 서버가 아니라 여기서 자른다.** 서버 쪽 날짜 파라미터
          이름을 확신하지 못해서(위 모듈 docstring), 넓게 받고
          `_recent_only()`로 클라이언트가 자른다. `numOfRows=100`을 넘는
          발령이 `since_hours` 안에 실제로 있으면 놓칠 수 있다 —
          `[미확보]` 페이지네이션 루프는 아직 안 붙였다.
        """
        if not self._key:
            self._miss("no_service_key")
            return None

        params = self._common()
        if region_name:
            params["rgnNm"] = region_name

        payload = self._fetch_json(BASE_URL, params)
        if payload is None:
            return None

        rows = payload.get("body")
        if not isinstance(rows, list):
            self._miss("unexpected_envelope", str(list(payload))[:120])
            return None

        messages = self._recent_only(
            [self._row(r) for r in rows if isinstance(r, dict)], since_hours)
        return self.stamp({"messages": messages}, source=self.name)

    def near(self, latitude: float, longitude: float,
             at: Any = None, **_: Any) -> dict[str, Any] | None:
        """`read_tools.disaster()`가 기대하는 인터페이스와 맞춘 얇은 래퍼.

        ★★**위도·경도를 실제로 쓰지 않는다.** 이 API는 좌표가 아니라
          지역명(`rgnNm`)으로 거른다 — `places`엔 지역명이 없어서 지금은
          전국을 그대로 받는다. `activity.py`의 `_disaster_blocks()`가
          "지역·주제 관련성을 확인하지 않는다"고 경고하는 게 판단이 아니라
          **이 API의 실제 한계**라는 뜻이다. `latitude`·`longitude`를
          지역명으로 바꾸는 역지오코딩이 생기면 그때 `region_name`을 채운다.
        """
        return self.recent()

    # ── 부품 ────────────────────────────────────────────────────
    @staticmethod
    def _row(row: dict[str, Any]) -> dict[str, Any]:
        return {field: str(row.get(field) or "") for field in _FIELDS}

    @staticmethod
    def _recent_only(messages: list[dict[str, Any]], since_hours: float
                     ) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
        kept = []
        for message in messages:
            when = DisasterMsgSource._parse_crt_dt(message.get("CRT_DT"))
            # ★언제인지 못 읽으면 **뺴지 않는다** — 모르는 걸 "오래됐다"로
            #   단정하면 실제 최근 발령을 놓칠 수 있다.
            if when is None or when >= cutoff:
                kept.append(message)
        return kept

    @staticmethod
    def _parse_crt_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value), _CRT_DT_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            return None   # ★포맷 추정이 틀렸을 수 있다 — 모름으로 둔다

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """★확신 없는 오류 봉투를 방어적으로만 본다 — 위 모듈 docstring 참고."""
        header = payload.get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode") or header.get("errorCode") or "")
            if code and code not in ("00", "0", "success", "SUCCESS"):
                message = header.get("resultMsg") or header.get("errorMsg") or ""
                return f"{code} {message}".strip()
        return TravelSource._body_error(payload)


__all__ = ["DisasterMsgSource", "BASE_URL"]
