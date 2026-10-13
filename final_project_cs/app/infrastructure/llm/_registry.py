"""LLM 어댑터가 함께 쓰는 두 가지 — 등록된 프롬프트 읽기 · 호출 감사 기록.

★`[2026-10-06]` `openai.py` 의 `OpenAITeamLLM.complete()` 안에 있던 코드를 그대로 옮겼다(동작 변경 없음).
  활동 판정용 Responses API 어댑터(`openai_responses.py`)도 같은 규칙으로 프롬프트를 읽고
  감사 기록을 남겨야 해서, 두 곳에 같은 코드를 두지 않으려고 뺐다.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID


class AuditWriteError(RuntimeError):
    """The model responded, but its audit record could not be persisted."""


def load_active_prompt(connection_factory: Callable[[], Any], prompt_key: str) -> tuple[UUID, str]:
    """활성 프롬프트 하나를 읽는다. 없거나 둘 이상이면 **외부 호출 전에** 멈춘다."""
    with connection_factory() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT prompt_id, template FROM prompts WHERE prompt_key=%s AND active=true",
                (prompt_key,),
            )
            rows = cur.fetchall()
    if len(rows) == 0:
        raise RuntimeError(f"no active prompt registered for {prompt_key}")
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one active prompt for {prompt_key}")
    prompt_id, template = rows[0]
    return prompt_id, template


def write_audit(connection_factory: Callable[[], Any], record: Callable[..., Any], *,
                prompt_key: str, **fields: Any) -> None:
    """감사 기록을 남긴다. 실패하면 `AuditWriteError` — 응답은 왔지만 기록이 없는 상태를 숨기지 않는다.

    ★`record` 를 인자로 받는다 — 어댑터 모듈이 import 한 `record_llm_call` 을 넘긴다. 시험이
      어댑터 모듈의 이름을 바꿔 끼워 기록을 가로채기 때문이다(`test_llm_call_audit_wiring.py`).
    """
    try:
        with connection_factory() as conn:
            with conn.transaction():
                record(conn, **fields)
    except Exception as exc:
        raise AuditWriteError(f"failed to record LLM call for {prompt_key}") from exc
