# -*- coding: utf-8 -*-
"""요청 검증 실패 응답이 **어느 칸이 문제인지** 말한다 — 체크리스트 I1. `[2026-10-03]`

☆결함: 필수 칸이 비었거나 형식이 틀리면 응답이 「request validation failed」 한 줄뿐이었다 — 에이전트(MCP · REST)와 화면이 어느 칸을 고쳐야 하는지 알 수 없었다.

★지키려는 것: ①칸 위치(`loc`)와 오류 종류(`type`)를 준다 ②**보낸 값은 되돌려 보내지 않는다**(키 · 개인정보가 오류 응답에 실려 나가지 않게) ③20개를 넘기지 않는다 ④기존 계약(상태 422 · `error.code == validation_error`)은 그대로다.

재현:

    python -m pytest tests/unit/presentation/test_validation_error_names_the_fields.py -v
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.presentation.errors import install_error_handlers


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    seq: int


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Item]
    secret: str | None = None


def _client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/echo")
    def echo(body: Body):  # pragma: no cover — 검증이 먼저 막는다
        return {"ok": True}

    return TestClient(app)


def test_the_response_names_which_field_is_missing_or_wrong_without_echoing_what_was_sent():
    response = _client().post("/echo", json={"items": [{"title": "경복궁", "seq": 1}, {"seq": "not-a-number"}], "secret": "sk-live-VERY-SECRET"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error" and error["message"] == "request validation failed"          # 기존 계약 그대로
    fields = {(f["loc"], f["type"]) for f in error["fields"]}
    assert ("body.items.1.title", "missing") in fields                                                      # 비어 있는 칸
    assert any(loc == "body.items.1.seq" for loc, _ in fields)                                              # 틀린 칸
    assert "sk-live-VERY-SECRET" not in response.text and "not-a-number" not in response.text               # 보낸 값은 안 돌려 보낸다


def test_an_unexpected_extra_field_is_named_too():
    response = _client().post("/echo", json={"items": [], "surprise": 1})
    assert {"loc": "body.surprise", "type": "extra_forbidden"} in response.json()["error"]["fields"]


def test_at_most_twenty_fields_are_listed():
    response = _client().post("/echo", json={"items": [{} for _ in range(30)]})
    assert len(response.json()["error"]["fields"]) == 20
