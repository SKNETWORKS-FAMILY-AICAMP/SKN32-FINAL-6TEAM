# -*- coding: utf-8 -*-
"""행정안전부 긴급재난문자 — **샘플 CSV 판**(실키 발급 대기 중, 2026-09-14).

★지금은 공공데이터포털(15134001)에 활용신청만 했고 키가 아직 안 나왔다. 그래서
  사용자가 받아 둔 샘플 CSV(`datasets/travel/행정안전부_긴급재난문자_sample.csv`)로
  **파서와 판정 규칙**을 먼저 돌린다. 키가 나오면 같은 `active()` 모양으로 API 판을
  붙이고 이 파일은 시험용으로 남긴다.

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
PLACE_KINDS = frozenset({"교통통제", "화재", "산불", "지진", "지진해일", "붕괴",
                         "정전", "가스", "폭발", "테러"})
DISRUPTIVE_KINDS = WEATHER_KINDS | PLACE_KINDS

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
            try:
                created = datetime.strptime(raw["CRT_DT"].strip(),
                                            "%Y/%m/%d %H:%M:%S").replace(tzinfo=KST)
            except (KeyError, ValueError, AttributeError):
                self.misses["bad_created_at"] += 1   # ★조용히 버리지 않고 센다
                continue
            rows.append({
                "created_at": created,
                "kind": (raw.get("DST_SE_NM") or "").strip(),
                "step": (raw.get("EMRG_STEP_NM") or "").strip(),
                "regions": _regions(raw.get("RCPTN_RGN_NM", "")),
                "text": (raw.get("MSG_CN") or "").replace("\r\n", " ").strip(),
                "serial": raw.get("SN"),
            })
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

        in_region = [row for row in self.rows
                     if window_start <= row["created_at"] <= at
                     and _covers(row["regions"], region, district)]
        messages, unclassified = [], []
        for row in in_region:
            if "해제" in row["text"]:               # ★해제 문자는 이상이 아니다
                continue
            item = {"kind": row["kind"], "step": row["step"], "text": row["text"],
                    "created_at": row["created_at"].isoformat(),
                    "regions": row["regions"], "serial": row["serial"],
                    "weather": row["kind"] in WEATHER_KINDS}
            if row["kind"] in DISRUPTIVE_KINDS:
                messages.append(item)
            elif row["kind"] != "기타":
                unclassified.append(item)            # ★모르는 구분은 보이게 남긴다
        return {**base, "for_region": messages, "unclassified": unclassified}


__all__ = ["DEFAULT_SAMPLE_PATH", "DISRUPTIVE_KINDS", "DisasterMsgCsv", "PLACE_KINDS",
           "WEATHER_KINDS"]
