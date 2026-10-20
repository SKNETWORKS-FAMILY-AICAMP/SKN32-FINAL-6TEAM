"""LLM이 읽은 식사 조건의 원문·대상·검사 누락을 대조한다. 문장의 뜻을 코드로 분류하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ATTRIBUTE_CHECK = {"halal": "dietary", "vegetarian": "dietary", "kids": "kids", "card": "payment"}
CONDITION_CHECKS = frozenset(ATTRIBUTE_CHECK.values())


@dataclass
class RequestAudit:
    enabled: bool
    meal_ids: set[str]
    requests: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)

    def validate(self, item_id: str, check: dict[str, Any]) -> str | None:
        """고객 조건 검사만 원문 목록과 연결한다. 도구 사실의 참/거짓은 agent.validate_check가 검증한다."""
        code = check.get("check")
        if not self.enabled or not isinstance(code, str) or code not in CONDITION_CHECKS:
            return None
        request_id = check.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return "request_invalid_id"
        request = next((r for r in self.requests if r["request_id"] == request_id), None)
        if request is None:
            return "request_unknown_id"
        if request["state"] != "active":
            return "request_not_active"
        if item_id not in request["item_ids"]:
            return "request_other_item"
        if check.get("required") is not request["required"]:
            return "request_requirement_mismatch"
        if check.get("check") != ATTRIBUTE_CHECK[request["attribute"]]:
            return "request_wrong_attribute"
        attributes = set()
        for ev in check.get("evidence") or []:
            path = str(ev.get("path") or "").split(".") if isinstance(ev, dict) else []
            if len(path) >= 2 and path[0] == "attributes":
                attributes.add(path[1])
        if attributes - {request["attribute"]} or (check.get("verdict") != "unknown" and not attributes):
            return "request_wrong_attribute"
        return None

    def source_for(self, check: dict[str, Any]) -> dict[str, Any] | None:
        return next((dict(r) for r in self.requests if r["request_id"] == check.get("request_id")), None)

    def missing(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """속성·식사마다 실제로 답했는지 본다. 같은 dietary라도 할랄과 채식은 별개다."""
        if not self.enabled:
            return []
        gaps = list(self.issues)
        answered = set()
        for item in items:
            item_id = str(item["item_id"])
            for check in item["checks"]:
                failure = check.get("failure")
                if failure and str(failure).startswith("request_"):
                    request_id = check.get("request_id")
                    gaps.append({"item_id": item_id, "check": check["check"],
                                 "request_id": request_id if isinstance(request_id, str) else None, "failure": failure})
                elif not failure and check.get("check") in CONDITION_CHECKS and self.validate(item_id, check) is None:
                    answered.add((item_id, check.get("request_id")))
        for request in self.requests:
            if request["state"] != "active":
                continue
            for item_id in request["item_ids"]:
                if item_id in self.meal_ids and (item_id, request["request_id"]) not in answered:
                    gaps.append({"item_id": item_id, "check": ATTRIBUTE_CHECK[request["attribute"]],
                                 **{k: request[k] for k in ("attribute", "request_id", "quote", "required")},
                                 "failure": "missing_customer_request"})
        return gaps


def audit_requests(plan: dict[str, Any], raw: Any) -> RequestAudit:
    """문장이 있는 새 호출은 목록이 필요하다. 문장이 없는 기존 내부 호출의 응답 모양은 유지한다."""
    current = [item for item in plan.get("items") or [] if isinstance(item, dict)]
    context = [item for item in plan.get("itinerary_context") or [] if isinstance(item, dict)]
    known = {str(item.get("item_id")): item for item in context + current}
    meals = {str(item.get("item_id")) for item in current if item.get("kind") == "dining"}
    notes = plan.get("customer_notes") or ""
    audit = RequestAudit(enabled=bool(notes) or raw is not None, meal_ids=meals)

    def issue(failure: str, entry: dict[str, Any] | None = None) -> None:
        detail = {k: entry[k] for k in ("request_id", "quote", "attribute")
                  if entry and isinstance(entry.get(k), str)}
        if entry and isinstance(entry.get("required"), bool):
            detail["required"] = entry["required"]
        if entry and isinstance(entry.get("item_ids"), list) and all(isinstance(t, str) for t in entry["item_ids"]):
            detail["item_ids"] = entry["item_ids"]
        audit.issues.extend({"item_id": item_id, "check": "_request", "failure": failure, **detail}
                            for item_id in sorted(meals))

    if not audit.enabled:
        return audit
    if not isinstance(notes, str):
        issue("request_source_not_text")
        return audit
    if not isinstance(raw, list):
        issue("request_inventory_missing" if raw is None else "request_inventory_malformed")
        return audit
    seen, invalid = set(), set()
    for entry in raw:
        if not isinstance(entry, dict):
            issue("request_inventory_malformed")
            continue
        rid, quote, attr = entry.get("request_id"), entry.get("quote"), entry.get("attribute")
        targets, required, state = entry.get("item_ids"), entry.get("required"), entry.get("state")
        if not isinstance(rid, str) or not rid.strip():
            issue("request_invalid_id", entry)
            continue
        if rid in seen:
            invalid.add(rid)
            issue("request_duplicate_id", entry)
            continue
        seen.add(rid)
        if not isinstance(quote, str) or not quote.strip() or quote not in notes:
            issue("request_quote_not_in_source", entry)
        elif not isinstance(attr, str) or attr not in ATTRIBUTE_CHECK:
            issue("request_unsupported_attribute", entry)
        elif not isinstance(required, bool):
            issue("request_invalid_requirement", entry)
        elif not isinstance(state, str) or state not in ("active", "excluded", "unclear"):
            issue("request_invalid_state", entry)
        elif not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
            issue("request_invalid_scope", entry)
        elif state == "unclear" or (state == "active" and not targets):
            issue("request_scope_unclear", entry)
        elif any(t not in known for t in targets):
            issue("request_unknown_item", entry)
        elif any(known[t].get("kind") != "dining" for t in targets):
            issue("request_not_a_meal", entry)
        else:
            audit.requests.append({"request_id": rid, "quote": quote, "attribute": attr,
                                   "item_ids": list(dict.fromkeys(targets)), "required": required, "state": state})
    effective: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for request in audit.requests:
        for target in request["item_ids"]:
            effective.setdefault((target, request["attribute"]), []).append(request)
    for requests in effective.values():
        # 같은 적용 대상의 최종 뜻을 한 번만 정리해야 한다. 취소와 활성화가 동시에 남으면 추정하지 않는다.
        if len({(r["state"], r["required"]) for r in requests}) > 1:
            invalid.update(r["request_id"] for r in requests)
            for request in requests:
                issue("request_conflict", request)
    audit.requests = [r for r in audit.requests if r["request_id"] not in invalid]
    return audit
