"""알림 발송 일꾼도 유료 대체 모델 호출 상한을 꽂고 시작한다.

★2026-10-19 발견. 상한을 세는 장치는 조립 루트(`app/composition.py`)가 import 될 때 꽂는다.
  `scripts/run_outbox_worker.py` 는 조립 루트를 거치지 않아, 이 일꾼 안의 넘김 장치(번역 등)는
  상한 없이 유료 API 를 불렀다(오라클 worker 로그 「llm_failover has no call-budget gate registered」).
  넘김 장치는 만들 때(`from_settings`) 상한을 읽으므로, 그 **앞에** 꽂혀 있어야 한다.
"""
from __future__ import annotations

import pytest

from app.infrastructure import llm_failover, ollama_chat
from scripts import run_outbox_worker


class _Stop(Exception):
    pass


def test_budget_provider_is_registered_before_failover_is_built(monkeypatch):
    monkeypatch.setattr(llm_failover, "_budget_provider", None)
    seen = {}

    def capture(settings, *args, **kwargs):
        seen["registered"] = llm_failover._budget_provider is not None
        raise _Stop()

    monkeypatch.setattr(ollama_chat, "from_settings", capture)
    monkeypatch.setattr("sys.argv", ["run_outbox_worker", "--once"])
    with pytest.raises(_Stop):
        run_outbox_worker.main()
    assert seen == {"registered": True}
