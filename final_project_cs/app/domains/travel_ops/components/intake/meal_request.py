"""Keep an explicit menu request when proposing another restaurant.

Only a menu title is a hard request; a dish inside a restaurant name is
similarity evidence, not permission to invent a customer requirement.
"""
from __future__ import annotations

from typing import Any

from app.domains.travel_ops.components.planning.meal_likeness import DISHES, DISH_SPELLINGS


def dish_words(item: dict[str, Any]) -> tuple[str, ...]:
    if item.get("kind") != "dining" or (item.get("parts") or {}).get("lodging_meal"):
        return ()
    title = str(item.get("title") or "").strip()
    if title not in DISHES:
        return ()
    return DISH_SPELLINGS.get(title, (title,))


def matches(item: dict[str, Any], place: dict[str, Any]) -> bool:
    words = dish_words(item)
    if not words:
        return True
    attrs = place.get("attributes") or {}
    texts = [place.get("name"), place.get("category"), attrs.get("category"), attrs.get("cuisine")]
    return any(word in str(text or "") for word in words for text in texts)
