# -*- coding: utf-8 -*-
"""로컬 언어 모델(Ollama)의 코드 기본값은 **우리 데이터로 가르친 E4B** 다. `[2026-10-14 사용자 지시]`

전에는 학습 없는 `gemma4:12b` 였고 x600 서버 운영 설정만 가르친 모델로 덮어 쓰고 있었다 — 코드 기본값과 운영이 어긋나 있었다.
기본값이 다시 어긋나면 여기서 먼저 걸린다. 개발 PC 에 이 모델이 없을 때의 안내(`.env.example`)가 실제 설정 이름을 쓰는지도 함께 본다.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from app.core.settings import Settings
from app.infrastructure.ollama_chat import from_settings

DEFAULT_MODEL = "tripilot-pointer:e4b-ft"
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_the_settings_default_model_is_the_trained_e4b():
    assert Settings.model_fields["ollama_model"].default == DEFAULT_MODEL


def test_the_context_length_default_goes_with_it():
    assert Settings.model_fields["ollama_num_ctx"].default == 8192


def test_a_settings_object_without_a_model_name_still_gets_the_trained_e4b():
    chat = from_settings(SimpleNamespace(ollama_base_url="http://ollama.test:11434"))
    assert chat.model == DEFAULT_MODEL


def test_an_explicit_model_name_wins_over_the_default():
    chat = from_settings(SimpleNamespace(ollama_base_url="http://ollama.test:11434", ollama_model="gemma4:12b"))
    assert chat.model == "gemma4:12b"


def test_no_ollama_address_still_means_no_chat():
    assert from_settings(SimpleNamespace(ollama_base_url="", ollama_model=DEFAULT_MODEL)) is None


def test_the_dev_template_names_for_swapping_the_model_are_known_settings():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    known = {name.lower() for name in Settings.model_fields}
    for name in ("OLLAMA_MODEL", "OLLAMA_NUM_CTX"):
        assert re.search(rf"^#?ACOP_{name}=", text, flags=re.M), f".env.example 에 ACOP_{name} 안내가 없다"
        assert name.lower() in known
