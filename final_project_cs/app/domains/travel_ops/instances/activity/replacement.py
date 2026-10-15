# -*- coding: utf-8 -*-
"""불가 판정 뒤의 **대체 장소** — 후보 풀을 읽어 줄 세우고, 재검증을 통과한 것만 안내문에 싣는다.

★`team.py` 에서 옮겼다(동작 변경 없음). 순위 계산 자체는 `alternatives.py`(순수 함수)가 한다.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any

from app.core.contracts import TeamTask

from . import failure_codes as fc
from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class

from . import alternative_order
from .alternatives import FALLBACK_DROPS, RADIUS_START_KM, preference_from_survey, rank_alternatives
from .disaster_impact import ImpactRules, assess
from .judge.llm import file_instructions
from .judge.modes import _run, default_runner, kind_mode

_order_log = logging.getLogger("acop.activity.alternative_order")


class ReplacementMixin:
    # ── 대체 장소 ─────────────────────────────────────────────

    @staticmethod
    def _blocked_by_place(decisions: dict[str, Any]) -> bool:
        """불가 사유가 **그 장소**에 있나 — 정기휴무 요일이거나 위급재난. 이미 시작됨·정원 초과는 장소를 바꿔도 안 풀린다.

        ★`[2026-10-06]` LLM 모드의 판정 둘(웹 공지상 휴무 · 운영시간 밖)도 장소 때문이다. 두 칸은 LLM 판정일 때만 생긴다.
        """
        operating = decisions.get("operating") or {}
        return bool(operating.get("weekday_match") is True
                    or (decisions.get("disaster") or {}).get("blocks")
                    or (decisions.get("live_status") or {}).get("closed")
                    or operating.get("hours_verdict") == "outside")

    @staticmethod
    def _survey(task: TeamTask) -> dict[str, Any] | None:
        """설문(`trips.constraints.survey`)이 Case 상태에 실려 오면 읽는다. 없으면 `None`."""
        state = task.context.current_state or {}
        survey = state.get("survey") or (state.get("constraints") or {}).get("survey")
        return survey if isinstance(survey, dict) else None

    @classmethod
    def _preference(cls, task: TeamTask) -> tuple[str | None, list[str]]:
        """선호도 — `current_state["activity_preference"]` 를 먼저, 없으면 설문 `priority` 에서. 둘 다 없으면 `None`.

        ★모르는 값이 들어 있으면 짐작하지 않고 경고를 남긴 채 `None`(폴백 없음)으로 처리한다.
        """
        state = task.context.current_state or {}
        raw = state.get("activity_preference")
        if raw is None:
            return preference_from_survey(cls._survey(task)), []
        if raw in FALLBACK_DROPS:
            return raw, []
        return None, [f"알 수 없는 선호도 값({raw!r})이라 선호도를 반영하지 않았다"]

    def _itinerary_places(self, task: TeamTask, seen: set[str],
                          trip_id: Any = None) -> tuple[set[str], set[str], bool]:
        """이 Case 의 여행 일정에 이미 들어 있는 장소 — (관광공사 contentid 들, 이름들, 읽었나).

        여행은 예약 결과의 `trip_id`(`read.booking` — 코어가 올리면) → Case 상태의 `subject_ref`(`kind: trip`) → 상태의
        `trip_id` 순으로 안다. 여행을 모르거나 일정을 못 읽으면
        세 번째 값이 `False` 다 — 부르는 쪽이 「확인 못 함」을 경고로 남긴다.
        """
        state = task.context.current_state or {}
        ref = state.get("subject_ref") or {}
        trip_id = trip_id or (ref.get("id") if ref.get("kind") == "trip" else None) or state.get("trip_id")
        if not trip_id:
            return set(), set(), False
        view = self._read(task, "read.itinerary", {"trip_id": str(trip_id)}, seen)
        if not isinstance(view, dict):
            return set(), set(), False
        ids: set[str] = set()
        names: set[str] = set()
        for item in view.get("items") or []:
            if item.get("kind") == "mobility":
                continue
            placed = item.get("place") or {}
            attributes = placed.get("attributes") or {}
            content_id = placed.get("source_content_id") or attributes.get("source_content_id")
            if content_id:
                ids.add(str(content_id))
            name = str(placed.get("name") or item.get("title") or "").strip()
            if name:
                names.add(name)
        return ids, names, True

    def _recommend_alternatives(self, task: TeamTask, place: Any, starts_at: Any, seen: set[str],
                                evidence: list, decisions: dict[str, Any], *, trip_id: Any = None,
                                ) -> tuple[dict[str, Any], list, str, list[str]]:
        """원래 장소 기준 대체 후보를 `read.place_candidates` 로 읽어 `rank_alternatives` 로 줄 세운다.

        ★**계산만 한다.** 후보를 못 읽으면 지어내지 않고 `status="unknown"` 과 이유 코드를 낸다.
        ★결과는 `decisions[].alternatives` 로 나간다 — `status`: ranked · unknown · withheld
          (wiki/teams/activity.md 「Team 연결」).
        ★`[2026-10-07]` 위급재난이어도 후보를 찾는다. 재난문자는 **자치구 단위**로 걸러 오므로
          (`disaster_msg.near()`) 다른 구의 후보는 막히지 않을 수 있다. 후보마다 그 위치의 문자를
          `read.disaster_points` 로 한 번에 다시 보고, 위급재난이 걸린 후보는 빼고, 모르는 후보는
          안내문에 싣지 않는다(`_recheck_disaster`). 후보가 전부 걸리면 `withheld` 다.
        """
        disaster_blocked = bool((decisions.get("disaster") or {}).get("blocks"))
        content_id = place.get("source_content_id") if isinstance(place, dict) else None
        if not content_id:
            self._record_failure(task, fc.ALTERNATIVES_NO_CONTENT_ID)
            return ({"status": "unknown", "reason": "no_content_id"}, evidence,
                    "원래 장소의 식별 정보가 없어 대체 장소를 찾지 못했습니다.",
                    ["대체 장소를 찾을 원래 장소 식별자(source_content_id)가 없다"])
        pool = self._read(task, "read.place_candidates", {"content_id": str(content_id)}, seen)
        if pool is None:
            self._record_failure(task, fc.ALTERNATIVES_POOL_UNAVAILABLE)
            return ({"status": "unknown", "reason": "pool_unavailable"}, evidence,
                    "대체 장소 후보를 조회하지 못했습니다.", ["대체 장소 후보 풀을 받지 못했다"])
        candidates = pool.get("candidates") or []
        # ★풀 전체(수천 건)를 근거에 싣지 않는다 — 어디서 몇 건을 언제 읽었는지만.
        evidence = self._evidence(task, source_id="read.place_candidates", claim="대체 후보 풀",
                                  value={"origin": {"contentid": (pool.get("origin") or {}).get("contentid"),
                                                    "title": (pool.get("origin") or {}).get("title")},
                                         "pool_size": len(candidates), "source": pool.get("source"),
                                         "confirmed_at": pool.get("confirmed_at")},
                                  base=evidence)
        preference, warnings = self._preference(task)
        # ★`[2026-10-15 피드백]` 이미 일정에 있는 곳은 대체 후보가 아니다 — `rank_alternatives(exclude_ids=)` 는 있었지만
        #   부르는 쪽이 한 번도 넘기지 않아 같은 여행의 다른 일정 장소가 후보로 나갔다. 같은 곳이 다른 contentid 로
        #   들어 있을 수 있어 이름으로도 가린다(`itinerary_changes.unused_places` 와 같은 기준).
        in_plan_ids, in_plan_names, plan_known = self._itinerary_places(task, seen, trip_id)
        if not plan_known:
            # ★일정을 못 읽었다 — 「겹침 없음」으로 읽지 않고 알린다(조용한 스킵 금지)
            warnings.append("여행 일정을 읽지 못해 후보가 이미 일정에 있는 곳인지 확인하지 못했다")
        if in_plan_names:
            candidates = [c for c in candidates if str(c.get("title") or "").strip() not in in_plan_names]
        ranked = rank_alternatives(pool["origin"], candidates, starts_at, preference=preference,
                                   exclude_ids=in_plan_ids)
        if ranked["reason"] == "origin_no_coordinates":
            # ★근처를 잴 기준이 없다 — 「근처에 없음」으로 읽지 않는다.
            self._record_failure(task, fc.ALTERNATIVES_NO_COORDINATES)
            return ({"status": "unknown", "reason": "origin_no_coordinates"}, evidence,
                    "원래 장소의 좌표가 없어 근처 대체 장소를 찾지 못했습니다.",
                    [*warnings, "대체 장소를 찾을 원래 장소 좌표가 없다"])
        # ★재검증(v11 §5) — 도구를 더 부르지 않고 이미 읽은 값으로만. 휴무 요일·운영시간이 **확인된** 후보만
        #   `revalidated: True` 다. 모름인 후보는 `decisions` 에만 남기고 안내문에는 싣지 않는다.
        for alternative in [*ranked["alternatives"], *ranked["more_alternatives"]]:
            alternative["revalidated"] = alternative["availability"] != "unconfirmed"
        disaster_note = None
        if disaster_blocked:
            evidence, disaster_note = self._recheck_disaster(task, ranked, candidates, starts_at, seen, evidence)
            if disaster_note == "all_blocked":
                self._record_failure(task, fc.ALTERNATIVES_WITHHELD)
                return ({"status": "withheld", "reason": "disaster_blocks"}, evidence,
                        "근처 대체 후보도 모두 재난 문자가 온 지역이라 대체 장소를 안내하지 않았습니다.",
                        warnings)
        if ranked["dropped_fields"]:
            warnings.append(f"유사 조건 일부({', '.join(ranked['dropped_fields'])})를 풀어서 찾은 후보다")
        if ranked["alternatives"] and ranked["radius_km"] > RADIUS_START_KM:
            warnings.append(f"반경을 {ranked['radius_km']:g}km까지 넓혀서 찾은 후보다")
        if ranked["more_dropped_fields"] and ranked["more_alternatives"]:
            warnings.append(f"더보기 후보 일부는 유사 조건({', '.join(ranked['more_dropped_fields'])})을 "
                            "풀어서 찾았다")
        alt = {"status": "ranked", **ranked,
               "revalidation": {"checked": ["time", "weekday_closure", "business_hours", "disaster"],
                                "not_checked": ["capacity"]},
               "source": pool.get("source"), "confirmed_at": pool.get("confirmed_at")}
        passed = [a for a in ranked["alternatives"] if a["revalidated"]]
        more = sum(1 for a in ranked["more_alternatives"] if a["revalidated"])
        if not passed:
            self._record_failure(task, fc.ALTERNATIVES_NONE if not ranked["alternatives"]
                                 else fc.ALTERNATIVES_UNCONFIRMED)
            excluded = ranked.get("disaster_excluded") or 0
            note = (f"근처 후보 {excluded}곳은 재난 문자가 온 지역이라 뺐습니다."
                    if not ranked["alternatives"] and excluded
                    else f"근처(반경 {ranked['max_radius_km']:g}km)에 조건에 맞는 장소가 없습니다."
                    if not ranked["alternatives"]
                    else "대체 장소 후보는 있으나 재난문자를 확인하지 못해 안내하지 않았습니다."
                    if disaster_note == "unknown"
                    else "대체 장소 후보는 있으나 운영 여부를 확인하지 못해 안내하지 않았습니다.")
            if more:
                # ★선호도 없음 — 화면 칸은 정확한 분류만 쓰므로 비지만, 비슷한 곳은 더보기에 있다.
                note += f" 비슷한 분류의 장소 {more}곳은 더보기에 있습니다."
            return alt, evidence, note, warnings

        # ★`[2026-10-12 사용자 결정]` 검증된 후보 안에서 LLM 이 고객 취향에 맞춰 먼저 보여 줄 순서를 정한다(`alternative_order`).
        #   후보를 새로 만들지 않는다 — 꺼져 있거나 · 취향 단서가 없거나 · 실패하면 코드 순서 그대로다.
        order = self._order_alternatives(task, place, alt, candidates, warnings)
        if order is not None:
            alt["order"] = order
            passed = [a for a in alt["alternatives"] if a["revalidated"]]
        # ★장소마다 추천 이유 한 줄(`reason_line` — 잰 값만 쓴다). 「더보기」 후보는 수만 말한다.
        lines = "\n".join(f"- {a['title']}: {a['reason']}" for a in passed)
        why = (order or {}).get("reason") if (order or {}).get("by") == "llm" else None
        return (alt, evidence,
                f"대체 장소 후보:\n{lines}\n"
                + (f"(AI 가 고객님 취향에 맞춰 먼저 보여 드리는 순서예요 — {why})\n" if why else "")
                + (f"더보기에 후보 {more}곳이 더 있습니다.\n" if more else "")
                + "후보는 휴무 요일·운영시간·재난문자만 다시 확인했고 정원은 확인하지 않았습니다.", warnings)

    def _order_alternatives(self, task: TeamTask, place: Any, alt: dict[str, Any], candidates: list[dict[str, Any]],
                            warnings: list[str]) -> dict[str, Any] | None:
        """검증된 후보의 보여 줄 순서 — `kind_modes.alternative_order`(rule · shadow · llm). `[2026-10-12 사용자 결정]`

        ★`rule`(기본) · 판정 LLM 없음 · 후보 1곳 이하 · 취향 단서 없음 → 부르지 않는다(`None`).
        ★`shadow` → 고객 순서는 코드 그대로, LLM 순서는 뒤에서 구해 로그에만 남긴다(`acop.activity.alternative_order`).
        ★`llm` → LLM 순서로 바꾼다. 실패 · 시간 초과 · 예산 초과 · 쓸 수 없는 답이면 코드 순서 + 이유를 `order` 에 남긴다.
        """
        llm = getattr(self, "judge_llm", None)
        mode = kind_mode(alternative_order.KIND)
        if llm is None or mode == "rule":
            return None
        # ★`[2026-10-13 사용자 결정 A안]` 화면에 보일 3곳만 넘긴다 — 어떤 3곳이 보이는지는 코드가 정하고 LLM 은 그 순서만 정한다.
        pool = [a for a in alt["alternatives"] if a.get("revalidated")]
        preference = alternative_order.preference_inputs(self._survey(task), task.input_text)
        if len(pool) < 2 or preference is None:
            return None
        budget = getattr(self, "judge_budget", None)
        try:
            if budget is not None and not budget(alternative_order.KIND):
                return {"by": "code", "skipped": "budget_exhausted"}
        except Exception:  # noqa: BLE001 — 세지 못하면 부르지 않는다(판정 계층과 같다)
            return {"by": "code", "skipped": "budget_unreadable"}
        rows = {str(c.get("contentid")): c for c in candidates}
        classes = {k: str(v.get("lclsSystm3") or v.get("lclsSystm2") or "") for k, v in rows.items()}
        body = alternative_order.payload(place.get("name") if isinstance(place, dict) else None, pool, preference, classes)
        from app.core.settings import get_guardrails

        timeout = float(get_guardrails().get("travel.activity_judge.alternative_order_timeout_seconds"))

        def ask():
            return llm.judge(alternative_order.PROMPT_KEY, body, schema=alternative_order.schema(),
                             schema_name="activity_alternative_order", web_search=False,
                             instructions=file_instructions(alternative_order.KIND), run_id=task.run_id)

        if mode == "shadow":
            code_ids = [str(a.get("contentid")) for a in pool]

            def work() -> None:
                try:
                    applied = alternative_order.apply(pool, _run(ask()).output)
                except Exception as exc:  # noqa: BLE001 — 섀도는 고객 결과와 상관없다. 보이게만 남긴다
                    _order_log.warning(json.dumps({"event": "alternative_order_shadow_error",
                                                   "case_id": str(task.case_id), "error": type(exc).__name__},
                                                  ensure_ascii=False))
                    return
                llm_ids = applied[1]["ids"] if applied else None
                _order_log.info(json.dumps({"event": "alternative_order_shadow", "case_id": str(task.case_id),
                                            "code_first": code_ids[0], "llm_first": llm_ids[0] if llm_ids else None,
                                            "agree": bool(llm_ids) and llm_ids[0] == code_ids[0],
                                            "usable": applied is not None}, ensure_ascii=False))

            (getattr(self, "judge_runner", None) or default_runner()).submit(work)
            return None
        try:
            call = _run(ask(), timeout=timeout)
        except FuturesTimeout:
            self._record_failure(task, fc.LLM_TIMEOUT, tool=alternative_order.KIND)
            warnings.append("대체 후보 순서 LLM 이 시간 안에 답하지 않아 코드 순서로 보여 줬다")
            return {"by": "code", "failed": fc.LLM_TIMEOUT}
        except Exception as exc:  # noqa: BLE001 — 429 · 키 없음 · 프롬프트 미등록 — 종류만 남기고 코드 순서
            self._record_failure(task, fc.LLM_ERROR, tool=alternative_order.KIND, error=type(exc).__name__)
            warnings.append("대체 후보 순서 LLM 을 부르지 못해 코드 순서로 보여 줬다")
            return {"by": "code", "failed": fc.LLM_ERROR, "error": type(exc).__name__}
        applied = alternative_order.apply(pool, getattr(call, "output", None))
        if applied is None:
            warnings.append("대체 후보 순서 LLM 의 답을 쓸 수 없어 코드 순서로 보여 줬다")
            return {"by": "code", "failed": fc.LLM_SCHEMA_INVALID}
        ordered, record = applied
        alt["alternatives"] = [*ordered, *[a for a in alt["alternatives"] if not a.get("revalidated")]]   # 더보기는 그대로
        if record["dropped"]:
            warnings.append(f"대체 후보 순서 LLM 이 목록에 없는 장소 {record['dropped']}곳을 냈다 — 버렸다")
        return {**record, "model": getattr(call, "model", None)}

    def _recheck_disaster(self, task: TeamTask, ranked: dict[str, Any], candidates: list[dict[str, Any]],
                          starts_at: Any, seen: set[str], evidence: list) -> tuple[list, str | None]:
        """원래 장소가 재난으로 막혔을 때 — 후보 위치마다 재난문자를 다시 본다. `[2026-10-07]`

        ★`[2026-10-11]` 막는 기준을 등급(위급재난)에서 수정본 §8 재해 분류표로 바꿨다(D2 · UC-A4 2단계 — 성립 판정과 같은 표).
          지역 위험형 문자가 온 구의 후보는 다 빼고, 야외 위험형은 야외 후보만 뺀다. 후보의 실내외는 관광공사 분류
          (`weather_from_class` — 일정 짜기와 같은 규칙)로 정하고, 모르면 야외처럼 뺀다(모름을 「안 막힘」으로 읽지 않는다).
        막히는 후보는 `ranked` 의 두 목록에서 **뺀다.** 그 위치의 문자를 모르는 후보는
        `revalidated: False` 로 두어 안내문에 싣지 않는다(모름을 「안 막힘」으로 읽지 않는다).
        반환: (근거, 상태) — 상태는 `None`(확인됨) · `"unknown"`(모르는 후보가 있음) · `"all_blocked"`.
        """
        listed = [*ranked["alternatives"], *ranked["more_alternatives"]]
        if not listed:
            return evidence, None
        rows = {str(c.get("contentid")): c for c in candidates}
        points = []
        for alternative in listed:
            row = rows.get(str(alternative.get("contentid"))) or {}
            # ★주소가 있으면 셋째 칸으로 — 도구가 주소의 자치구로 거른다(좌표 상자는 자주 틀린다)
            point = [row.get("mapy"), row.get("mapx")]
            if row.get("addr1"):
                point.append(row["addr1"])
            points.append(point)
        found = self._read(task, "read.disaster_points", {"points": points, "at": starts_at}, seen)
        results = (found or {}).get("points") if isinstance(found, dict) else None
        if not isinstance(results, list) or len(results) != len(listed):
            results = [None] * len(listed)

        blocked: set[int] = set()
        unknown = False
        rules = ImpactRules.load()
        for alternative, result in zip(listed, results):
            if not isinstance(result, dict):
                alternative["disaster"] = "unknown"
                alternative["revalidated"] = False
                unknown = True
                continue
            messages = [*(result.get("for_region") or []), *(result.get("unclassified") or [])]
            row = rows.get(str(alternative.get("contentid"))) or {}
            outdoor = weather_from_class(row.get("lclsSystm1"), row.get("lclsSystm2"))
            # ★야외 위험형에서 실내외를 모르는 후보는 묻지 않고 뺀다 — 후보는 고객이 고른 곳이 아니다
            if assess(messages, True if outdoor is None else outdoor, rules,
                      at=starts_at if isinstance(starts_at, datetime) else None, place_name=row.get("title")).blocks:
                blocked.add(id(alternative))
            else:
                alternative["disaster"] = "clear"
        ranked["alternatives"] = [a for a in ranked["alternatives"] if id(a) not in blocked]
        ranked["more_alternatives"] = [a for a in ranked["more_alternatives"] if id(a) not in blocked]
        ranked["disaster_excluded"] = len(blocked)
        evidence = self._evidence(task, source_id="read.disaster_points", claim="대체 후보 위치의 재난문자",
                                  value={"checked": len(listed), "excluded": len(blocked),
                                         "unknown": sum(1 for r in results if not isinstance(r, dict))},
                                  base=evidence)
        if blocked and not ranked["alternatives"] and not ranked["more_alternatives"]:
            return evidence, "all_blocked"
        return evidence, "unknown" if unknown else None
