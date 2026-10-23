"""OpenAI 구조화 응답 — 엄격 스키마로 보내고, 선택 칸의 null 은 지워 돌려준다. `[2026-10-15]`

느슨한 모드(`strict: False`)에서 gpt-4o-mini 가 채팅 해석(`decision_unit`) 스키마를 지키지 않았다 —
12/12 실패: 스키마째 돌려주거나(`{"type": "object", "properties": {...}}`) 사실 칸 값(`nearby_dining`)을 할 일 칸에 넣었다.
gemma(Ollama)는 출력 형식을 강제해서 이 문제가 없다. 서버를 바꾸기 전 로컬 시험은 OpenAI 로 한다(사용자 결정).
"""
import json

from app.infrastructure.llm_failover import OpenAIChat, _drop_optional_nulls, strict_schema

SCHEMA = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["a", "b"]},
    "minutes": {"type": "integer"},
    "query": {"anyOf": [{"type": "object", "properties": {"day": {"type": "string"}}, "required": ["day"]},
                        {"type": "null"}]},
    "reads": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
        "fact": {"type": "string"}, "text": {"type": "string"}}, "required": ["fact"]}}},
    "required": ["action", "reads"]}


def test_every_object_is_closed_and_optional_keys_become_nullable():
    strict = strict_schema(SCHEMA)
    assert strict["additionalProperties"] is False
    assert sorted(strict["required"]) == ["action", "minutes", "query", "reads"]
    assert strict["properties"]["minutes"] == {"anyOf": [{"type": "integer"}, {"type": "null"}]}
    assert strict["properties"]["action"] == {"type": "string", "enum": ["a", "b"]}            # 필수는 그대로
    item = strict["properties"]["reads"]["items"]
    assert item["additionalProperties"] is False and sorted(item["required"]) == ["fact", "text"]
    assert "maxItems" not in strict["properties"]["reads"]                                      # 엄격 모드가 받지 않는 말은 뗀다
    assert SCHEMA["properties"]["minutes"] == {"type": "integer"}                               # 원본은 그대로


def test_nulls_of_optional_keys_are_dropped_so_callers_see_the_old_shape():
    got = {"action": "a", "minutes": None, "query": None,
           "reads": [{"fact": "address", "text": None}]}
    assert _drop_optional_nulls(got, SCHEMA) == {"action": "a", "reads": [{"fact": "address"}]}


class _Client:
    def __init__(self, reply):
        self.reply, self.sent = reply, []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.sent.append(kwargs)

        class _Msg:
            content = json.dumps(self.reply)

        class _Choice:
            message = _Msg()
            finish_reason = "stop"

        class _Resp:
            choices = [_Choice()]
            usage = None

        return _Resp()


def test_structured_sends_a_strict_schema_and_returns_the_old_shape():
    client = _Client({"action": "b", "minutes": None, "query": None, "reads": []})
    chat = OpenAIChat(api_key="sk-test", model="gpt-4o-mini", client=client)
    assert chat.structured("system", "user", SCHEMA) == {"action": "b", "reads": []}
    sent = client.sent[0]["response_format"]["json_schema"]
    assert sent["strict"] is True and sent["schema"]["additionalProperties"] is False
