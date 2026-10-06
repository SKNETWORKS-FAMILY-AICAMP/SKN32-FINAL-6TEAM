# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 — **API 판**(`DisasterMsgApi`)과 **샘플 CSV 판**(`DisasterMsgCsv`).

★두 판은 같은 파서(`parse_row`)와 같은 판정(`judge`)을 쓰고 같은 `active()` 모양으로 답한다.
  조립은 키(`ACOP_DISASTER_MSG_API_KEY`)가 있으면 API 판, 없으면 샘플 판을 붙인다.
★키가 나오기 전(2026-09-14 까지)에는 사용자가 받아 둔 샘플 CSV 로 **파서와 판정 규칙**을
  먼저 돌렸다. 샘플 판은 시험과 키 없는 자리를 위해 남긴다.

★★샘플은 **2023-09-16 ~ 09-19 의 100건**뿐이다(실측). 그 기간 밖의 시각을 물으면
  `covered=False` 로 답한다 — 「그 시각에 재난문자 없음」이라고 답하지 않는다.
  샘플 기간 밖을 「없음」으로 읽으면 실제 운영에서 늘 조용한 거짓말이 된다.

실측한 샘플 모양(2026-09-14):
    열  SN · CRT_DT(「2023/09/19 14:24:55」) · MSG_CN · RCPTN_RGN_NM · EMRG_STEP_NM ·
        DST_SE_NM · …  ★2행이 한국어 열 이름이다(데이터가 아니다)
    재해구분  호우 61 · 기타 31 · 교통통제 4 · 산사태 4
    긴급단계  안전안내 99 · 긴급재난 1
    수신지역  「서울특별시 강남구 역삼동,서울특별시 강남구 삼성동」처럼 쉼표로 잇고,
              시도 단위는 「부산광역시 전체」로 온다

판정에 넣는 기준(데이터를 보고 정했다):
    - 「기타」는 넣지 않는다 — 샘플의 기타 31건은 **실종자 찾기**다. 넣으면 실종자
      문자 한 통으로 서울 전역의 일정이 바뀐다
    - 본문에 「해제」가 있으면 넣지 않는다 — 「통제가 완전 해제되었음」이 실제로 있다
    - 목록에 없는 재해구분은 이상으로 세지 않고 `unclassified` 로 **보이게** 남긴다
"""
from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .base import TravelSource

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
#: ★저장소 **안의** 합성 픽스처를 읽는다(2026-09-14). 처음엔 저장소 밖
#:  `datasets/travel/…_sample.csv` 를 읽었는데, 코드가 git 밖 데이터에 기대면 다른
#:  사람 자리에서 조용히 비고, 원본에는 **실종자 실명·나이·인상착의 31건**이 있어
#:  그대로 옮기면 공개 저장소에 개인정보가 올라간다. 그래서 기타(실종) 31건의
#:  본문을 합성 문구로 바꾸고 나머지의 이름·나이·링크 패턴을 가린 사본을 둔다.
#:  재해구분·지역·시각 분포는 원본 그대로다(호우 61·기타 31·교통통제 4·산사태 4).
DEFAULT_SAMPLE_PATH = Path(__file__).resolve().parent / "samples" / "disaster_msg_2023-09.csv"

#: 날씨가 일으키는 재해 — ★날씨 영향을 받는 장소에만 적용한다(점검이 가른다).
WEATHER_KINDS = frozenset({"호우", "태풍", "대설", "강풍", "폭염", "한파", "산사태",
                           "풍랑", "황사", "홍수", "낙뢰"})
#: 장소를 가리지 않는 재해 — 가는 길이 막히거나 시설이 닫힌다.
#: ★`[2026-10-06 사용자 결정 — 재난 시 일정 정지]` 민방위 · 화산 · 원전 · 방사능을 더했다 — 전쟁 · 활화산 폭발 같은 심각한 사건이 「모르는 구분」으로 빠져 정지 판정에 안 닿던 것을 막는다
#:   `[미확인]` 실제 재해구분명이 이 이름들인지는 못 봤다 — 모르는 이름이어도 본문 낱말(`travel.safety.trip_keywords`)이 있으면 들어온다(`judge`)
PLACE_KINDS = frozenset({"교통통제", "화재", "산불", "지진", "지진해일", "붕괴",
                         "정전", "가스", "폭발", "테러", "민방위", "화산", "원전", "방사능"})
DISRUPTIVE_KINDS = WEATHER_KINDS | PLACE_KINDS
#: 설정(`config/guardrails.yaml`)을 못 읽을 때만 쓰는 값 — 정본은 `travel.safety.*` 한 곳이다
_FALLBACK_SEVERE = ("공습경보", "경계경보", "화산", "분화", "전쟁", "미사일", "방사능", "생화학")
_FALLBACK_EXCLUDE = ("훈련", "해제", "실제 상황이 아")


def _safety_words() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(심각 낱말, 제외 낱말) — 정본은 `travel.safety`. 설정이 없는 환경(시험 · 옛 설정)에서는 기본값."""
    try:
        from app.core.settings import get_guardrails

        guard = get_guardrails()
        return (tuple(str(w) for w in guard.get("travel.safety.trip_keywords")),
                tuple(str(w) for w in guard.get("travel.safety.exclude_keywords")))
    except Exception:                                  # noqa: BLE001 — 설정 오류가 재난문자 판정을 죽이지 않는다
        return _FALLBACK_SEVERE, _FALLBACK_EXCLUDE

#: 우리 지역 이름 → 재난문자 수신지역 표기.
REGION_NAMES = {"서울": "서울특별시"}

#: 그 시각 **이전 몇 시간** 안에 온 문자를 본다. ★우리가 고른 값이다(측정 아님).
DEFAULT_LOOKBACK_HOURS = 6


def _regions(text: str) -> list[str]:
    return [part.strip() for part in str(text or "").split(",") if part.strip()]


def _covers(tokens: list[str], region: str, district: str | None) -> bool:
    full = REGION_NAMES.get(region, region)
    for token in tokens:
        if not token.startswith(full):
            continue
        # ★구까지 알면 구로 좁힌다 — 강남 도로 통제로 종로 일정을 바꾸지 않게.
        if district is None or token.endswith("전체") or district in token:
            return True
    return False


def parse_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """공급자 한 줄(CSV·API 공통 열 이름) → 판정용 행. 생성 시각을 못 읽으면 `None`.

    ★샘플 CSV 와 API 는 같은 열 이름을 쓴다(샘플이 그 API 에서 받은 것이다).
      그래서 두 판이 **같은 파서와 같은 판정**을 쓴다 — 규칙이 두 벌로 갈라지지 않게.
    """
    try:
        created = datetime.strptime(str(raw["CRT_DT"]).strip(),
                                    "%Y/%m/%d %H:%M:%S").replace(tzinfo=KST)
    except (KeyError, ValueError, AttributeError):
        return None
    return {
        "created_at": created,
        "kind": (raw.get("DST_SE_NM") or "").strip(),
        "step": (raw.get("EMRG_STEP_NM") or "").strip(),
        "regions": _regions(raw.get("RCPTN_RGN_NM", "")),
        "text": (raw.get("MSG_CN") or "").replace("\r\n", " ").strip(),
        "serial": raw.get("SN"),
    }


def judge(rows: list[dict[str, Any]], *, region: str, district: str | None,
          window_start: datetime, at: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """창 안·지역 안의 행 → (이상으로 셀 문자, 모르는 구분). 판정 규칙은 모듈 docstring."""
    messages, unclassified = [], []
    severe_words, exclude_words = _safety_words()
    for row in rows:
        if not (window_start <= row["created_at"] <= at
                and _covers(row["regions"], region, district)):
            continue
        # ★해제 문자는 이상이 아니다. ★`[2026-10-06]` 훈련 문자도 이상이 아니다(`travel.safety.exclude_keywords` — 「민방위 훈련」 한 통으로 일정이 바뀌면 안 된다)
        if "해제" in row["text"] or any(word in row["text"] for word in exclude_words):
            continue
        item = {"kind": row["kind"], "step": row["step"], "text": row["text"],
                "created_at": row["created_at"].isoformat(),
                "regions": row["regions"], "serial": row["serial"],
                "weather": row["kind"] in WEATHER_KINDS}
        # ★`[2026-10-06]` 재해구분이 모르는 값이어도(기타 · 새 이름) 본문에 심각 낱말(공습경보 · 화산 …)이 있으면 이상이다 — 전쟁 · 화산 폭발이 「모르는 구분」으로 빠지지 않게
        if row["kind"] in DISRUPTIVE_KINDS or any(word in row["text"] for word in severe_words):
            messages.append(item)
        elif row["kind"] != "기타":
            unclassified.append(item)                # ★모르는 구분은 보이게 남긴다
    return messages, unclassified


def judge_released(rows: list[dict[str, Any]], *, region: str, district: str | None,
                   window_start: datetime, at: datetime) -> list[dict[str, Any]]:
    """창 안 · 지역 안의 **해제 문자**(본문에 「해제」). 재해구분은 가리지 않는다 — 어느 사건의 해제인지는 부르는 쪽이 가른다(`safety_pause._matching_release`)."""
    out = []
    for row in rows:
        if not (window_start <= row["created_at"] <= at and _covers(row["regions"], region, district)):
            continue
        if "해제" not in row["text"]:
            continue
        out.append({"kind": row["kind"], "step": row["step"], "text": row["text"], "created_at": row["created_at"].isoformat(),
                    "regions": row["regions"], "serial": row["serial"]})
    return out


class DisasterMsgCsv:
    """샘플 CSV 를 읽어 `active()` 로 답한다. 바깥으로 나가지 않는다."""

    name = "disaster_msg_sample"
    mode = "sample"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.misses: Counter[str] = Counter()
        self.rows = self._load()
        stamps = [row["created_at"] for row in self.rows]
        self.coverage = (min(stamps), max(stamps)) if stamps else None

    def _load(self) -> list[dict[str, Any]]:
        text = self.path.read_bytes().decode("utf-8-sig")
        rows = []
        for raw in csv.DictReader(io.StringIO(text)):
            if raw.get("SN") == "일련번호":          # ★2행은 한국어 열 이름이다
                continue
            row = parse_row(raw)
            if row is None:
                self.misses["bad_created_at"] += 1   # ★조용히 버리지 않고 센다
                continue
            rows.append(row)
        if self.misses:
            logger.warning("disaster_msg sample: skipped rows %s", dict(self.misses))
        return rows

    def active(self, *, region: str, at: datetime, district: str | None = None,
               lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any] | None:
        """`at` 이전 `lookback_hours` 안에 `region` 으로 온 문자. 못 읽었으면 `None`."""
        if self.coverage is None:
            return None
        at = at if at.tzinfo else at.replace(tzinfo=KST)
        window_start = at - timedelta(hours=lookback_hours)
        first, last = self.coverage
        covered = first <= at <= last + timedelta(hours=lookback_hours)
        base = {"mode": self.mode, "covered": covered, "region": region,
                "district": district,
                "coverage": {"from": first.isoformat(), "to": last.isoformat()},
                "window": {"from": window_start.isoformat(), "to": at.isoformat()},
                "source": self.name,
                "confirmed_at": datetime.now(KST).isoformat()}
        if not covered:
            return {**base, "for_region": [], "unclassified": []}

        messages, unclassified = judge(self.rows, region=region, district=district,
                                       window_start=window_start, at=at)
        return {**base, "for_region": messages, "unclassified": unclassified}

    def released(self, *, region: str, since: datetime, at: datetime, district: str | None = None) -> list[dict[str, Any]] | None:
        """`since` 부터 `at` 까지의 **해제 문자**. 샘플 기간 밖이면 `None`(모름 — 「해제 없음」이라고 답하지 않는다)."""
        if self.coverage is None:
            return None
        at = at if at.tzinfo else at.replace(tzinfo=KST)
        since = since if since.tzinfo else since.replace(tzinfo=KST)
        first, last = self.coverage
        if not (first <= at <= last + timedelta(hours=DEFAULT_LOOKBACK_HOURS)):
            return None
        return judge_released(self.rows, region=region, district=district, window_start=since, at=at)


#: 재난안전데이터공유플랫폼 긴급재난문자 — 2026-09-14 실키로 실호출 확인:
#:    `{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE"},"numOfRows":…,"pageNo":…,
#:      "totalCount":…,"body":[{SN, CRT_DT, MSG_CN, RCPTN_RGN_NM, EMRG_STEP_NM, DST_SE_NM, …}]}`
#:    건수 0 이면 `body` 가 **null** 이다(결과 코드는 여전히 00).
#:  ★★`crtDt` 는 「그 날짜의 문자」가 아니라 **「그 날짜부터 지금까지」**다 — 2023-09-19 로
#:    걸면 62,159건, 오늘로 걸면 4건, 어제로 걸면 42건(오늘 4 포함)이었다. `rgnNm` 은 지역
#:    거름이다(「경기도 김포시」 488건). **순서는 호출마다 달랐다** — 순서에 기대지 않는다.
#:  ★키에 IP 제한이 없다(발급 화면 「유저아이피 *.*.*.*」) — 서버 경유가 필요 없다.
#:  ★`[미확인]` 하루 한도(같은 플랫폼 다른 API 사용기의 100/일을 보수적으로 쓴다).
API_ENDPOINT = "https://www.safetydata.go.kr/V2/api/DSSP-IF-00247"
API_PAGE_ROWS = 1000


class DisasterMsgApi(TravelSource):
    """실키 판 — 샘플 CSV 판과 **같은 파서·같은 판정**, 같은 `active()` 모양.

    ★창의 **시작 날짜부터**(`crtDt` 는 하한이다, 실측) 지역(`rgnNm`) 문자를 한 번에 받아
      창으로 자른다. 장소가 달라도 인자가 같아 캐시를 나눠 쓴다 — 하루 한도(100
      `[미확인]`)가 낮아서 중요하다.
    ★창의 끝은 일정 시각과 지금 중 이른 쪽 — 아직 안 온 문자는 없다.
    ★모르는 모양은 모름(`None`)이다. 줄 하나라도 못 읽거나, 전체 건수가 받은 것보다 많으면
      (잘림) 목록 전체를 모름으로 둔다 — 못 읽은 것이 바로 그 호우 문자일 수 있다.
    """

    name = "disaster_msg"
    mode = "api"

    def __init__(self, *, service_key: str, cache_ttl_seconds: float | None = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        #: ★이 소스만 캐시를 길게 둔다 — `ResponseCache.put(ttl_seconds=…)`.
        self.cache_ttl_seconds = cache_ttl_seconds

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        header = payload.get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            message = str(header.get("resultMsg", ""))
            # ★`[미확인]` 「자료 없음」 코드를 아직 못 봤다. 없음 표시는 성공(빈 목록)으로 읽는다.
            if code in ("00", "0", "0000") or "NODATA" in message.replace("_", "").upper():
                return None
            return f"{code} {message}".strip()
        return TravelSource._body_error(payload)

    def _rows_since(self, region: str, window_start: datetime) -> list[dict[str, Any]] | None:
        """창 시작 날짜 이후 `region` 으로 온 문자를 **파싱해** 돌려준다. 못 읽으면 `None`(모름) — `active` 와 `released` 가 같이 쓴다."""
        rows: list[dict[str, Any]] = []
        # ★`crtDt` 는 하한이다 — 창 시작 날짜로 **한 번** 부르면 지금까지가 온다(실측).
        payload = self._fetch_json(API_ENDPOINT, {
            "serviceKey": self._key, "returnType": "json", "pageNo": 1,
            "numOfRows": API_PAGE_ROWS, "crtDt": window_start.strftime("%Y%m%d"),
            "rgnNm": REGION_NAMES.get(region, region)})
        if payload is None:
            return None
        body = payload.get("body")
        if body is None:
            body = []                                  # ★건수 0 이면 null 로 온다(실측)
        if not isinstance(body, list):
            self._miss("unexpected_shape", type(body).__name__)
            return None
        total = payload.get("totalCount")
        if isinstance(total, (int, str)) and str(total).isdigit() and int(total) > len(body):
            self._miss("truncated", f"{total} > {len(body)}")
            return None
        for raw in body:
            row = parse_row(raw) if isinstance(raw, dict) else None
            if row is None:
                self._miss("bad_row", repr(raw)[:160])
                return None
            rows.append(row)
        return rows

    def released(self, *, region: str, since: datetime, at: datetime, district: str | None = None) -> list[dict[str, Any]] | None:
        """`since` 부터 `at` 까지 `region` 으로 온 **해제 문자**(재해구분은 가리지 않는다). 못 읽으면 `None`. `[2026-10-06]` 재난 정지를 푸는 알림이 쓴다."""
        now = datetime.now(KST)
        at = at if at.tzinfo else at.replace(tzinfo=KST)
        since = since if since.tzinfo else since.replace(tzinfo=KST)
        rows = self._rows_since(region, since.astimezone(KST))
        if rows is None:
            return None
        return judge_released(rows, region=region, district=district, window_start=since, at=min(at.astimezone(KST), now))

    def active(self, *, region: str, at: datetime, district: str | None = None,
               lookback_hours: int = DEFAULT_LOOKBACK_HOURS) -> dict[str, Any] | None:
        now = datetime.now(KST)
        at = at if at.tzinfo else at.replace(tzinfo=KST)
        until = min(at.astimezone(KST), now)
        window_start = until - timedelta(hours=lookback_hours)
        rows = self._rows_since(region, window_start)
        if rows is None:
            return None
        messages, unclassified = judge(rows, region=region, district=district,
                                       window_start=window_start, at=until)
        return self.stamp({"mode": self.mode, "covered": True, "region": region,
                           "district": district,
                           "window": {"from": window_start.isoformat(), "to": until.isoformat()},
                           "for_region": messages, "unclassified": unclassified},
                          source=self.name)


__all__ = ["API_ENDPOINT", "DEFAULT_SAMPLE_PATH", "DISRUPTIVE_KINDS", "DisasterMsgApi",
           "DisasterMsgCsv", "PLACE_KINDS", "WEATHER_KINDS", "judge", "judge_released", "parse_row"]
