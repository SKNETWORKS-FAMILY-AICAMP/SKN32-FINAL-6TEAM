"""유료 넘김 경로로 나가는 system · schema 에 고객 글(문장 · 일정 이름 · 전화번호)이 없다 — rm9 Codex 남은 지적 1 확인(2026-10-26 묶음 L).

★`FailoverChat` 은 유료 경로의 `user` 만 `masked_outbound` 로 가린다(rm9 7e5c77cb5 · 시험 9입구). system · schema 는 가리지 않으므로,
  채팅 해석(`decision_unit.decide`)이 넘기는 system 이 **고정 문장**이고 유료용 스키마(`api_schema`)가 **문장 · 이름 없는** 모양인지 여기서 본다.
  고객 글이 다른 두 요청에서 system · api_schema 가 바이트까지 같으면 고객 글이 실릴 자리가 없다.
"""
import json
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.conversation import decision_unit
from app.domains.travel_ops.components.conversation.decision_unit import decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)


def _plan(names):
    base = datetime(2030, 1, 2, tzinfo=KST)
    out = []
    for n, name in enumerate(names, start=1):
        place = {"place_id": uuid4(), "name": name, "kind": "activity", "latitude": 37.57, "longitude": 126.98, "attributes": {}}
        out.append(Item(item_id=uuid4(), seq=n, kind="activity", title=name, place_id=place["place_id"], place=place,
                        starts_at=base + timedelta(hours=9 + 2 * n), ends_at=base + timedelta(hours=10 + 2 * n)))
    return out


class _Recorder:
    """`FailoverChat.structured_validated` 과 같은 받는 칸(api_schema)을 가진 대역 — 유료 경로로 갈 system · schema 를 적는다."""

    def __init__(self):
        self.calls = []

    def structured_validated(self, system, user, schema, *, validator, num_predict=160, api_schema=None):
        self.calls.append({"system": system, "user": user, "schema": schema, "api_schema": api_schema})
        return {"action": "other", "target_item": "none", "target_change": "none", "fact": "none", "minutes": 0,
                "choices": [], "reads": [], "social": "", "general_requests": []}


def _sent(names, message):
    chat = _Recorder()
    decide(chat, stops=stops_of(_plan(names)), changes=[], history=[], selected_item_id=None, message=message, now=NOW)
    return chat.calls[-1]


def test_the_paid_route_system_and_schema_carry_no_customer_text():
    secret_place, secret_phone = "비밀정원카페연남점", "010-9876-5432"
    first = _sent(["북촌한옥마을", secret_place], f"{secret_place} 예약자 {secret_phone} 로 바꿔줘")
    second = _sent(["경복궁", "다른곳"], "경복궁 한 시간 늦춰줘")
    assert first["api_schema"] is not None, "유료용 문장 없는 스키마가 넘겨지지 않았다"
    for call in (first,):
        system, paid_schema = call["system"], json.dumps(call["api_schema"], ensure_ascii=False)
        for text in (secret_place, secret_phone, "9876", "예약자"):
            assert text not in system and text not in paid_schema, text
    assert first["system"] == second["system"]                      # 고정 문장 — 요청마다 달라지지 않는다
    assert json.dumps(first["api_schema"], sort_keys=True) == json.dumps(second["api_schema"], sort_keys=True)
    # 대조: 로컬 생성 문법(schema)은 문장 인용을 실을 수 있다 — 그래서 유료로는 api_schema 를 보낸다
    assert first["schema"] != first["api_schema"]


def test_the_system_is_the_registered_constant():
    from app.domains.travel_ops.components.conversation.edit_intent import SYSTEM as EDIT_SYSTEM

    assert _sent(["북촌한옥마을"], "북촌 알려줘")["system"] == decision_unit.SYSTEM + EDIT_SYSTEM
