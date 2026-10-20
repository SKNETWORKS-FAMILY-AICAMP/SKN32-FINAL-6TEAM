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
from app.domains.travel_ops.components.intake.survey_answers import QUESTIONS as SURVEY_QUESTIONS
from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class

from . import alternative_order, place_aliases, place_identity
from .alternatives import FALLBACK_DROPS, RADIUS_START_KM, preference_from_survey, rank_alternatives
from .disaster_impact import ImpactRules, assess
from .judge.llm import file_instructions
from .judge.modes import _run, default_runner, kind_mode

_order_log = logging.getLogger("acop.activity.alternative_order")

#: ★`[2026-10-14]` 여행을 못 찾은 예약에서 다시 묻는 문항 — 여행 설문의 그 문항 그대로다(새 형식을 만들지 않는다).
#:  활동 → 코어 전달 8번 회신(`wiki/records/reports/2026-10-13_활동_전달8_설문전달_회신.md`).
ASK_QUESTION_ID = "priority"
#: 고객 답에서 고른 선택지를 알아보는 말(띄어쓰기 무시) — 설문 선택지 글에 들어 있는 핵심 구절. 둘 다 들어 있으면 고르지 않는다.
REPLY_PHRASES = {"activity": "활동이비슷한", "mobility": "이동이편한"}


def ask_question():
    """다시 물을 설문 문항(`survey_answers.QUESTIONS` 의 `priority`)."""
    return next(q for q in SURVEY_QUESTIONS if q.id == ASK_QUESTION_ID)


def reply_choice(text: str | None) -> str | None:
    """고객 문장에서 고른 선택지 — 선택지 핵심 구절이 **하나만** 들어 있을 때만. 없거나 둘 다면 `None`(짐작하지 않는다)."""
    flat = "".join(str(text or "").split())
    found = [value for value, phrase in REPLY_PHRASES.items() if phrase in flat]
    return found[0] if len(found) == 1 else None


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

    def _survey(self, task: TeamTask, booking: dict[str, Any] | None, seen: set[str], evidence: list, *,
                reserve: int = 0, plan_out: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, dict[str, Any], list, list[str]]:
        """여행 설문(`trips.constraints.survey`)과 어디서 읽었나 — `(설문, 출처, 근거, 경고)`. 못 찾으면 설문이 `None`.

        찾는 순서(`[2026-10-14]` 활동 → 코어 전달 8번 회신):
          1. Case 상태에 실려 온 설문(`survey` · `constraints.survey`) — 지금은 코어가 싣지 않지만 받는 자리는 둔다.
          2. 예약이 속한 여행(`read.booking` 의 `trip` — 공용 도구가 찾는다) → `read.itinerary` 로 그 여행의 설문.
             여행을 기간으로 추정했거나(`trip_period`) 예약 자체를 추정으로 골랐으면(`nearest`) 추정이라고 남긴다.
        ★`reserve` — 뒤에 꼭 불러야 하는 도구 수. 도구 호출 상한이 모자라면 설문을 읽지 않고 경고만 남긴다(판정을 멈추지 않는다).
        ★`plan_out` — 일정을 이미 읽었으면 그 결과(`view`)를 담아 돌려준다. 같은 도구를 한 번 더 부르지 않으려는 것이다
          (`_itinerary_places` — 이미 일정에 있는 곳은 대체 후보가 아니다).
        ★근거에는 설문 칸 이름만 싣는다 — 고객이 직접 쓴 답(자유 글)을 근거 · 로그에 복사하지 않는다.
        """
        state = task.context.current_state or {}
        survey = state.get("survey") or (state.get("constraints") or {}).get("survey")
        if isinstance(survey, dict):
            return survey, {"from": "case_state"}, evidence, []
        trip = (booking or {}).get("trip") or {}
        trip_id = trip.get("trip_id")
        if not trip_id:
            return None, {"from": None, "why": trip.get("why_unknown") or "no_trip"}, evidence, []
        if len(seen) + 1 + reserve > self.manifest.max_steps:
            return (None, {"from": None, "why": "tool_budget", "trip_id": trip_id}, evidence,
                    ["도구 호출 상한이 가까워 예약이 속한 여행의 설문을 읽지 않았다"])
        try:
            view = self._read(task, "read.itinerary", {"trip_id": trip_id}, seen)
        except Exception as exc:  # noqa: BLE001 — 실패 코드는 `_read` 가 남겼다. 설문 없이 판정은 계속한다(경고로 드러낸다)
            return (None, {"from": None, "why": "itinerary_unreadable", "trip_id": trip_id}, evidence,
                    [f"예약이 속한 여행의 설문을 읽지 못했다({type(exc).__name__})"])
        if plan_out is not None:
            plan_out["view"] = view
        guessed = trip.get("matched_by") == "trip_period" or (booking or {}).get("matched_by") == "nearest"
        info = {"from": "trip", "trip_id": trip_id, "matched_by": trip.get("matched_by"), "guessed": guessed}
        survey = (((view or {}).get("trip") or {}).get("constraints") or {}).get("survey")
        if not isinstance(survey, dict) or not survey:
            return None, {**info, "from": None, "why": "trip_without_survey"}, evidence, []
        evidence = self._evidence(task, source_id="read.itinerary", claim="예약이 속한 여행의 설문",
                                  value={"trip_id": trip_id, "matched_by": trip.get("matched_by"), "guessed": guessed,
                                         "survey_fields": sorted(survey)}, base=evidence)
        return survey, info, evidence, (["예약이 속한 여행을 추정으로 찾아 그 여행의 설문을 썼다"] if guessed else [])

    def _itinerary_places(self, task: TeamTask, booking: dict[str, Any] | None, seen: set[str],
                          view: Any, *, reserve: int = 0) -> tuple[set[str], set[str], list[Any], list[str]]:
        """이 예약이 속한 여행 일정에 **이미 들어 있는 장소** — `(관광공사 contentid 들, 이름들, 같은 곳 판정용 `Spot` 들, 경고)`. `[2026-10-15 피드백]`

        ★전에는 `rank_alternatives(exclude_ids=)` 가 있는데 부르는 쪽이 넘기지 않아 같은 여행의 다른 일정 장소가 대체 후보로 나갔다.
          같은 곳이 다른 contentid 로 있을 수 있어 이름도 함께 본다(`itinerary_changes.unused_places` 와 같은 기준).
        ★일정을 못 읽으면 「겹침 없음」으로 읽지 않고 경고로 남긴다(조용한 스킵 금지). `view` 는 `_survey` 가 읽은 결과(없으면 여기서 읽는다).
        """
        ref = (task.context.current_state or {}).get("subject_ref") or {}
        trip_id = ((booking or {}).get("trip") or {}).get("trip_id") or (ref.get("id") if ref.get("kind") == "trip" else None)
        if view is None and trip_id and len(seen) + 1 + reserve <= self.manifest.max_steps:
            try:
                view = self._read(task, "read.itinerary", {"trip_id": str(trip_id)}, seen)
            except Exception:  # noqa: BLE001 — 실패 코드는 `_read` 가 남겼다. 경고로 드러낸다
                view = None
        if not isinstance(view, dict):
            return set(), set(), [], ["여행 일정을 읽지 못해 후보가 이미 일정에 있는 곳인지 확인하지 못했다"]
        ids: set[str] = set()
        names: set[str] = set()
        spots: list[Any] = []
        for item in view.get("items") or []:
            if item.get("kind") == "mobility":
                continue
            placed = item.get("place") or {}
            content_id = placed.get("source_content_id") or (placed.get("attributes") or {}).get("source_content_id")
            if content_id:
                ids.add(str(content_id))
            name = str(placed.get("name") or item.get("title") or "").strip()
            if name:
                names.add(name)
            spot = place_identity.spot_of({**placed, "name": name}) if name else None
            if spot is not None:
                spots.append(spot)
        return ids, names, spots, []

    @staticmethod
    def _preference(task: TeamTask, survey: dict[str, Any] | None) -> tuple[str | None, list[str], str | None]:
        """선호도 — `(값, 경고, 출처)`. 순서: `current_state["activity_preference"]` → 이번 문의의 고객 답(다시 물은 문항에 고른 말)
        → 설문 `priority`. 모두 없으면 `None`.

        ★모르는 값이 들어 있으면 짐작하지 않고 경고를 남긴 채 `None`(폴백 없음)으로 처리한다.
        ★`[2026-10-14]` 고객 답은 **이번 문의에만** 쓴다(사용자 결정) — 저장하지 않는다. 재개면 `customer_input`, 새 문의면 그 문장.
        """
        state = task.context.current_state or {}
        raw = state.get("activity_preference")
        if raw is not None:
            if raw in FALLBACK_DROPS:
                return raw, [], "case_state"
            return None, [f"알 수 없는 선호도 값({raw!r})이라 선호도를 반영하지 않았다"], None
        reply = state.get("customer_input")
        chosen = reply_choice(reply if isinstance(reply, str) else task.input_text)
        if chosen is not None:
            return chosen, [], "customer_reply"
        found = preference_from_survey(survey)
        return found, [], ("survey" if found else None)

    def _ask_preference(self, task: TeamTask, seen: set[str], evidence: list) -> tuple[dict[str, Any], str, list]:
        """설문을 못 찾았을 때 다시 묻는 질문 한 줄 — 같은 고객의 지난 답이 있으면 함께 알려 준다. `(기록, 문장, 근거)`.

        ★안내를 막지 않는다 — 대체 후보는 코드 순서로 먼저 보내고, 이 문장은 답변 끝에 붙는다. 답은 다음 문장으로 온다.
        """
        question = ask_question()
        options = [{"id": o.id, "label": o.label} for o in question.options]
        last = None
        if len(seen) + 1 <= self.manifest.max_steps:
            try:
                last = self._read(task, "read.last_survey_answer", {"question_id": ASK_QUESTION_ID}, seen)
            except Exception:  # noqa: BLE001 — 실패 코드는 `_read` 가 남겼다. 지난 답 없이 묻는다
                last = None
        if last:
            evidence = self._evidence(task, source_id="read.last_survey_answer", claim="같은 고객의 지난 설문 답",
                                      value={"question_id": ASK_QUESTION_ID, "option_id": last.get("option_id")},
                                      base=evidence)
        choices = " 또는 ".join(f"「{o['label']}」" for o in options)
        line = (f"취향을 알려 주시면 후보 순서를 다시 정해 드려요 — {question.title} {choices}로 답해 주세요."
                + (f" 지난번에는 「{last['label']}」을 고르셨어요." if last and last.get("label") else ""))
        return {"question_id": ASK_QUESTION_ID, "title": question.title, "options": options, "last": last}, line, evidence

    def _recommend_alternatives(self, task: TeamTask, place: Any, starts_at: Any, seen: set[str],
                                evidence: list, decisions: dict[str, Any], booking: dict[str, Any] | None = None,
                                ) -> tuple[dict[str, Any], list, str, list[str]]:
        """원래 장소 기준 대체 후보를 `read.place_candidates` 로 읽어 `rank_alternatives` 로 줄 세운다.

        ★**계산만 한다.** 후보를 못 읽으면 지어내지 않고 `status="unknown"` 과 이유 코드를 낸다.
        ★결과는 `decisions[].alternatives` 로 나간다 — `status`: ranked · unknown · withheld
          (wiki/teams/activity.md 「Team 연결」).
        ★`[2026-10-07]` 위급재난이어도 후보를 찾는다. 재난문자는 **자치구 단위**로 걸러 오므로
          (`disaster_msg.near()`) 다른 구의 후보는 막히지 않을 수 있다. 후보마다 그 위치의 문자를
          `read.disaster_points` 로 한 번에 다시 보고, 위급재난이 걸린 후보는 빼고, 모르는 후보는
          안내문에 싣지 않는다(`_recheck_disaster`). 후보가 전부 걸리면 `withheld` 다.
        ★`[2026-10-14]` 취향(설문)은 예약이 속한 여행에서 읽는다(`_survey`). 못 찾았고 검증된 후보가 두 곳 이상이면 답변 끝에
          설문 문항 하나를 다시 묻는다(`_ask_preference`) — 활동 → 코어 전달 8번 회신. 어디서 정했는지는 `alt["preference"]`.
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
        plan: dict[str, Any] = {}
        survey, survey_info, evidence, warnings = self._survey(task, booking, seen, evidence,
                                                               reserve=1 if disaster_blocked else 0, plan_out=plan)
        preference, more_warnings, source = self._preference(task, survey)
        warnings = [*warnings, *more_warnings]
        in_plan_ids, in_plan_names, in_plan_spots, plan_warnings = self._itinerary_places(
            task, booking, seen, plan.get("view"), reserve=1 if disaster_blocked else 0)
        warnings += plan_warnings
        if in_plan_names:
            candidates = [c for c in candidates if str(c.get("title") or "").strip() not in in_plan_names]
        # ★`[2026-10-19]` 이름이 달라도 같은 곳(「N서울타워」 = 「남산서울타워」)은 규칙 · 확인된 별칭만 뺀다(`place_identity`, LLM 은 쓰지 않는다)
        candidates = self._drop_same_places(task, candidates, in_plan_spots, warnings,
                                            aliases=place_aliases.merged(pool.get("aliases")))
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
               "source": pool.get("source"), "confirmed_at": pool.get("confirmed_at"),
               "preference": {"value": preference, "from": source, "survey": survey_info}}
        passed = [a for a in ranked["alternatives"] if a["revalidated"]]
        more = sum(1 for a in ranked["more_alternatives"] if a["revalidated"])
        ask_line = ""
        if preference is None and survey is None and len(passed) + more >= 2:
            # ★순서가 취향에 따라 갈릴 만큼 후보가 있을 때만 묻는다. 안내는 막지 않는다(답변 끝 한 줄)
            alt["preference"]["asked"], ask_line, evidence = self._ask_preference(task, seen, evidence)
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
            if ask_line:
                note += "\n" + ask_line
            return alt, evidence, note, warnings

        # ★`[2026-10-12 사용자 결정]` 검증된 후보 안에서 LLM 이 고객 취향에 맞춰 먼저 보여 줄 순서를 정한다(`alternative_order`).
        #   후보를 새로 만들지 않는다 — 꺼져 있거나 · 취향 단서가 없거나 · 실패하면 코드 순서 그대로다.
        order = self._order_alternatives(task, place, alt, candidates, warnings, survey)
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
                + "후보는 휴무 요일·운영시간·재난문자만 다시 확인했고 정원은 확인하지 않았습니다."
                + (f"\n{ask_line}" if ask_line else ""), warnings)

    def _drop_same_places(self, task: TeamTask, candidates: list[dict[str, Any]], spots: list[Any],
                          warnings: list[str], *, aliases: place_aliases.AliasTable = place_aliases.EMPTY) -> list[dict[str, Any]]:
        """일정에 이름만 다르게 이미 들어 있는 같은 장소를 대체 후보에서 뺀다 — `place_identity`. `[2026-10-19 사용자 결정]`

        ★규칙이 `same` 이라 한 후보(같은 contentid · 같은 이름 · **확인된 별칭**)만 뺀다. 같을 수도 있는 후보(`ambiguous` — 300m 안 · 이름이 닮음)는
          빼지 않고 개수만 경고로 남긴다. LLM 에게 묻는 방식은 쓰지 않는다(지웠다) — 자주 나오는 애매한 쌍은 `place_aliases.csv` 에 별칭으로 더한다.
        """
        if not spots or not candidates:
            return candidates
        kept, removed, maybe = place_identity.split(spots, candidates, aliases)
        if removed:
            warnings.append(f"일정에 이미 들어 있는 같은 장소 {removed}곳을 대체 후보에서 뺐다")
        if maybe:
            warnings.append(f"일정에 있는 곳과 같은 장소일 수 있는 후보 {maybe}곳을 확인하지 못해 그대로 두었다")
        return kept

    def _order_alternatives(self, task: TeamTask, place: Any, alt: dict[str, Any], candidates: list[dict[str, Any]],
                            warnings: list[str], survey: dict[str, Any] | None = None) -> dict[str, Any] | None:
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
        # ★`[2026-10-19]` 감시 Case 의 제목(시스템 문구)은 고객 문장이 아니다 — `customer_words` 가 고객이 쓴 말만 고른다
        preference = alternative_order.preference_inputs(
            survey, alternative_order.customer_words(task.input_text, task.context.current_state))
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
