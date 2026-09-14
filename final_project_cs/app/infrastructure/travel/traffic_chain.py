# -*- coding: utf-8 -*-
"""교통 돌발 소스 **합치기** — ITS + UTIC.

★대체(1차가 못 주면 다음)가 아니라 **합친다.** 둘이 보는 것이 다르다:
    ITS   도시고속도로·국도 중심, 공사가 대부분(실측 서울 122건 중 공사 116)
    UTIC  경찰청 — 시내 사고·행사·집회까지(실측 전국 182건)
  한쪽만 보면 다른 쪽의 사건을 놓친다.

판정(결정 15):
    둘 다 답함        → 합친 목록
    하나만 답함       → 답한 쪽 목록 + `partial_from` 에 못 답한 쪽 이름 (**숨기지 않는다**)
    둘 다 못 답함     → `None` — 점검이 치명으로 판정한다

★같은 사고가 두 소스에 다 오면 두 줄이 된다(식별자가 서로 다르다). 판정(이상 있음)은
  같고 문구에 두 번 나올 수 있다 — `source` 를 줄마다 붙여 어디서 왔는지 보이게 한다.
"""
from __future__ import annotations

from collections import Counter
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CombinedTraffic:
    name = "traffic_combined"

    def __init__(self, sources: list[Any]) -> None:
        if not sources:
            raise ValueError("CombinedTraffic 에 소스가 하나도 없다")
        self.sources = list(sources)
        self.misses: Counter[str] = Counter()

    def near(self, **kwargs: Any) -> dict[str, Any] | None:
        answered: list[str] = []
        failed: list[str] = []
        for_place: list[dict[str, Any]] = []
        advisories: list[dict[str, Any]] = []
        confirmed: list[str] = []
        for source in self.sources:
            name = getattr(source, "name", type(source).__name__)
            value = source.near(**kwargs)
            if value is None:
                failed.append(name)
                continue
            answered.append(name)
            origin = value.get("source") or name
            for_place += [{**item, "source": origin} for item in value.get("for_place") or []]
            advisories += [{**item, "source": origin} for item in value.get("advisories") or []]
            if value.get("confirmed_at"):
                confirmed.append(value["confirmed_at"])
        if not answered:
            self.misses["all_failed"] += 1
            logger.error("traffic sources all failed: %s", failed)
            return None
        if failed:
            self.misses["partial"] += 1
        return {"for_place": for_place, "advisories": advisories,
                "source": "+".join(answered), "sources": answered, "partial_from": failed,
                # ★가장 **오래된** 확인 시각을 준다 — 합친 값이 그보다 새롭다고 말하지 않는다.
                "confirmed_at": min(confirmed) if confirmed else None,
                "kind": "traffic_events"}


__all__ = ["CombinedTraffic"]
