"""이벤트 payload 규격 등록 가드 — 2026-08-31 추가.

`validate_payload` 는 규격이 등록되지 않은 이벤트를 거부한다. 그런데 지금은
`EventType` 이 전부 등록돼 있어 이 가드에 **실제 입력으로는 닿지 않는다.**
그래서 가드를 무력화해도(`.get(event_type, ())`) 전체 424개가 전부 통과했다.

가드가 막으려는 것은 "새 이벤트를 만들면서 규격 등록을 잊는 것"이다.
여기서는 그 상황을 만들어 가드가 살아 있는지 센다.
"""

from __future__ import annotations

import pytest

from app.core.contracts import InvalidTransition
from app.domain.case import validate_payload
from app.domain.events import REQUIRED_PAYLOAD_KEYS, EventType


def test_every_event_type_has_a_registered_schema() -> None:
    """규격 없는 이벤트가 새로 생기면 여기서 먼저 걸린다."""
    missing = [event.value for event in EventType if event not in REQUIRED_PAYLOAD_KEYS]
    assert missing == [], f"payload 규격이 등록되지 않은 이벤트: {missing}"


def test_unregistered_event_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """규격이 빠지면 조용히 통과시키지 않고 InvalidTransition 을 던진다."""
    victim = EventType.CREATED
    monkeypatch.delitem(REQUIRED_PAYLOAD_KEYS, victim)
    with pytest.raises(InvalidTransition, match="등록되지 않은"):
        validate_payload(victim, {})


def test_registered_event_still_checks_required_keys() -> None:
    """가드가 살아 있어도 필수 키 검사는 그대로 돈다."""
    required = REQUIRED_PAYLOAD_KEYS[EventType.CREATED]
    if not required:
        pytest.skip("created 이벤트에 필수 키가 없어 이 검사는 해당 없음")
    with pytest.raises(InvalidTransition, match="필수 키"):
        validate_payload(EventType.CREATED, {})
