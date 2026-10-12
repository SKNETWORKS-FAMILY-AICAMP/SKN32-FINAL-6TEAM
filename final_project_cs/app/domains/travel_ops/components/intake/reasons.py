# -*- coding: utf-8 -*-
"""후보 이유 문장을 **모델이 확인된 값으로** 쓴다 — 결과 저장 · 실패하면 틀 문장. `[2026-10-07 사용자 결정 — uiux 전달]` 마이그레이션 057

사용자: 「이유 문장만 모델이 확인된 값으로 쓴다 — 보이는 후보 2~3개만, 결과 저장, 실패하면 지금의 틀 문장」. 대안을 **고르는 일**은 규칙(분류 나무 · 영업시간 · 거리 · 여유)이 한다 — 모델은 고른 뒤 **말만** 한다.

★모델은 **사실 목록만** 받는다(`facts_for`: 후보 이름 · 고른 기준 · 거리 · 영업 · 여유 분 · 일정에 담은 장소). 그 밖의 이름 · 숫자 · 분위기 · 평가를 쓴 문장은 `guard` 가 버려 틀 문장(`candidates._reason`)으로 돌아간다 —
  「근거 없는 문장 금지」(루트 CLAUDE.md)를 모델 문장에도 지킨다. 틀 문장이 이미 사실만 쓰므로 모델은 **같은 사실을 더 자연스럽게 말하는 것**뿐이다.
★같은 사실이면 같은 문장 — 열쇠(`facts_sha`) = 프롬프트 버전 + 사실의 해시, 저장은 `candidate_reasons`. 요청 자리에서 매번 부르지 않는다.
★시간 상한(`budget_seconds`) 안에 못 쓴 후보는 틀 문장으로 나가고, 모델 호출은 **뒤에서 끝나 저장된다**(다음 요청부터 모델 문장). 후보마다 `reason_by` = `model` · `template`.
★모델이 없거나(`chat` None) 설정이 꺼져 있으면(`travel.candidate_reason.enabled`) 아무것도 안 한다 — 전부 틀 문장.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from app.core.settings import get_guardrails

log = logging.getLogger(__name__)

SYSTEM = (
    "여행 일정 앱의 대체 장소 카드에 붙는 이유 한 문장을 쓴다. 아래 사실에 적힌 내용만 쓴다. "
    "사실에 없는 이름 · 숫자 · 분위기 · 평가 · 추측은 쓰지 않는다(좋다 · 예쁘다 · 인기 · 유명 · 추천 같은 말 금지). "
    "존댓말(~예요 · ~해요)로 한 문장, 80자 안쪽. 거리 · 영업시간 · 여유 분은 사실에 있으면 그대로 쓴다. 영업시간을 확인하지 못했다면 그렇게 말한다.")
SCHEMA = {"type": "object", "properties": {"sentence": {"type": "string"}}, "required": ["sentence"]}
#: 근거 없이 붙기 쉬운 평가 · 분위기 말
FORBIDDEN = ("추천", "좋은", "예쁜", "아름다운", "멋진", "인기", "유명", "최고", "분위기", "힐링", "감성", "핫플", "강추", "필수", "꼭 ")
#: 장소 이름에 흔한 끝말 — 이런 낱말이 문장에 있으면 **사실에 있는 이름**이어야 한다(모델이 이름을 지어내는 것을 막는다)
_PLACE_WORD = re.compile(r"(궁|시장|공원|마을|박물관|미술관|전시관|호텔|타워|광장|센터|숲|대교|스튜디오|카페|식당)")
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="candidate-reason")


def _cfg(key: str) -> Any:
    return get_guardrails().get(f"travel.candidate_reason.{key}")


def facts_for(candidate: dict[str, Any], original: str | None) -> dict[str, Any]:
    """모델에게 줄 사실 — **확인된 값만**. 모르는 값은 적지 않는다(영업시간만 「확인하지 못함」이라고 말한다)."""
    from .candidates import EXPERIENCE_GROUPS, _SAME_KIND_WORDS

    place = candidate["place"]
    facts: dict[str, Any] = {"후보 장소": place["name"]}
    if original:
        facts["원래 장소"] = original
    basis = candidate.get("basis")
    if basis == "same_kind" and candidate.get("class_grade") == "estimated":
        facts["고른 기준"] = f"원래 장소와 {_SAME_KIND_WORDS.get(candidate.get('similarity'), '비슷한 종류')}로 짐작되는 곳(분류를 추정함)"
    elif basis == "same_kind":
        facts["고른 기준"] = f"원래 장소와 {_SAME_KIND_WORDS.get(candidate.get('similarity'), '비슷한 종류')}(관광공사 분류)"
    elif basis == "similar_experience":
        label = EXPERIENCE_GROUPS.get(candidate.get("experience") or "", {}).get("label")
        facts["고른 기준"] = f"같은 종류는 가까이에 없어 {label or '비슷한 경험'}을 하는 곳 중 가까운 곳"
    elif basis == "taste":
        from .taste import reason_head

        facts["고른 기준"] = reason_head(candidate.get("taste") or {})
    elif basis == "meal_inferred":
        facts["고른 기준"] = "식사 시간이고 그 시간대에 식사 일정이 따로 없어 식당도 후보"
    elif basis == "lodging":
        facts["고른 기준"] = "숙소 후보"
    elif basis == "lodging_meal":
        facts["고른 기준"] = "이 숙소 안에서 식사하는 경우(숙소 안 식당이 있는지는 확인하지 못함)"
    anchor = candidate.get("reference") or original
    if candidate.get("distance_m") is not None and anchor:
        facts["거리"] = f"{anchor}에서 {candidate['distance_m']}m"
    hours = next((r for r in candidate.get("rows") or [] if r.get("row") == "hours"), None)
    if hours and hours.get("result") == "ok" and hours.get("text"):
        facts["영업"] = str(hours["text"])
    elif hours and hours.get("result") == "unknown":
        facts["영업"] = "영업시간은 확인하지 못함"
    after = (candidate.get("slack") or {}).get("after")
    if isinstance(after, (int, float)) and after >= 0:
        facts["여유"] = f"다음 일정까지 {int(after)}분"
    return facts


def key_of(facts: dict[str, Any]) -> str:
    raw = json.dumps({"v": str(_cfg("prompt_version")), "f": facts}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def guard(sentence: Any, facts: dict[str, Any]) -> str | None:
    """모델 문장을 검사한다 — 통과하면 정리한 문장, 아니면 None(틀 문장을 쓴다). 사실에 없는 숫자 · 이름 · 평가를 막는다."""
    if not isinstance(sentence, str):
        return None
    text = " ".join(sentence.split())
    if not text or len(text) > int(_cfg("max_chars")):
        return None
    if any(word in text for word in FORBIDDEN):
        return None
    pool = " ".join(str(v) for v in facts.values())
    if set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", pool)):
        return None                                                     # 사실에 없는 숫자
    for quoted in re.findall(r"[「『“\"'](.+?)[」』”\"']", text):
        if quoted not in pool:
            return None                                                 # 따옴표로 묶은 이름이 사실에 없다
    for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
        found = _PLACE_WORD.search(token)
        if found and token[:found.end()] not in pool:
            return None                                                 # 장소 이름처럼 생긴 낱말(끝말까지)이 사실에 없다 — 「경복궁에서」는 「경복궁」이 사실에 있으면 통과
    if not text.endswith(("요", "요.", "다", "다.")):
        return None
    return text


# ── 저장 ────────────────────────────────────────────────────────
def _stored(conn, tenant_id: str, sha: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT sentence FROM candidate_reasons WHERE tenant_id=%s AND facts_sha=%s", (tenant_id, sha))
        row = cur.fetchone()
    return row[0] if row else None


def _store(tenant_id: str, sha: str, sentence: str, model: str) -> None:
    from app.infrastructure.db.session import get_connection

    try:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO candidate_reasons (tenant_id, facts_sha, sentence, model) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (tenant_id, sha, sentence, model))
    except Exception:                                     # noqa: BLE001 — 저장 실패는 문장을 못 쓰는 이유가 아니다(다음에 다시 쓴다)
        log.warning("candidate reason store failed", exc_info=True)


def _write(chat: Any, tenant_id: str, facts: dict[str, Any], sha: str) -> str | None:
    """모델에게 한 번 쓰게 하고 검사를 넘으면 저장한다. 어떤 실패도 None(틀 문장) — 예외를 밖으로 내지 않는다."""
    try:
        got = chat.structured(SYSTEM, json.dumps(facts, ensure_ascii=False), SCHEMA, num_predict=120)
    except Exception:                                     # noqa: BLE001 — 모델 서버가 죽었거나 느려도 후보는 나간다
        log.info("candidate reason model call failed", exc_info=True)
        return None
    text = guard((got or {}).get("sentence"), facts)
    if text is None:
        return None
    _store(tenant_id, sha, text, str(getattr(chat, "model", "unknown")))
    return text


# ── 후보에 적용 ─────────────────────────────────────────────────
def polish(conn, tenant_id: str, candidates: list[dict[str, Any]], original: str | None, chat: Any) -> dict[str, int]:
    """화면에 먼저 보이는 후보 `visible` 개의 이유를 모델 문장으로 바꾼다(제자리). 후보마다 `reason_by` 를 단다. 센 값을 돌려준다."""
    out = {"model": 0, "cached": 0, "template": 0, "pending": 0}
    for c in candidates:
        c["reason_by"] = "template"
    if chat is None or not _cfg("enabled") or not candidates:
        out["template"] = len(candidates)
        return out
    jobs = []
    for c in candidates[: int(_cfg("visible"))]:
        facts = facts_for(c, original)
        if len(facts) <= 1:
            continue                                      # 쓸 사실이 이름뿐이면 틀 문장(없음)을 그대로 둔다
        sha = key_of(facts)
        stored = _stored(conn, tenant_id, sha)
        if stored is not None:
            c["reason"], c["reason_by"] = stored, "model"
            out["cached"] += 1
            continue
        jobs.append((c, _pool.submit(_write, chat, tenant_id, facts, sha)))
    if jobs:
        done, late = wait([f for _c, f in jobs], timeout=float(_cfg("budget_seconds")))
        for c, future in jobs:
            if future in late:
                out["pending"] += 1                       # 시간 안에 못 썼다 — 틀 문장으로 나가고, 쓰는 일은 뒤에서 끝나 저장된다
                continue
            text = future.result()
            if text is not None:
                c["reason"], c["reason_by"] = text, "model"
                out["model"] += 1
    out["template"] = sum(1 for c in candidates if c["reason_by"] == "template")
    return out


__all__ = ["FORBIDDEN", "SCHEMA", "SYSTEM", "facts_for", "guard", "key_of", "polish"]
