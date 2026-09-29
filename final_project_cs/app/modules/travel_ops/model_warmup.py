# -*- coding: utf-8 -*-
"""모델 예열 — 화면이 여행·채팅 칸을 열 때 원격 모델을 미리 깨운다. `[2026-09-29]` 사용자 지시(ui 세션 · Codex 합의)

★왜. 모델이 식어 있으면(5분 안 쓰이면 내려간다 — Ollama 기본) 첫 채팅이 34.8·33.5초 걸렸다. 깨어 있으면 2.0·2.1초
  (ui 세션 실측). 붙잡아 두는 시간(`keep_alive`)을 늘리는 대신 **쓰기 직전에 깨운다** — 모델 서버 GPU 는 다른 작업과 나눠 쓴다.
★남용 방어: ①이미 올라가 있으면 아무것도 안 한다 ②`dedupe_seconds` 안에 이미 시작했으면 다시 안 부른다(프로세스 안)
  ③실제로 부를 때만 `web_guard.count("warmup")` 로 센다(키·주소·서비스 하루 한도 — 켜져 있을 때).
★실패를 숨기지 않는다 — 마지막 시도의 결과(성공·실패 이유)를 응답에 싣는다. 모델 서버가 GPU 메모리 부족으로 못 올리는
  상태(2026-09-29 실측)도 화면이 알 수 있게.
"""
from __future__ import annotations

import threading
import time as _time
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_lock = threading.Lock()
_state: dict[str, Any] = {"started": 0.0, "last": None}


def reset() -> None:
    with _lock:
        _state.update(started=0.0, last=None)


def _run(chat: Any) -> None:
    started = _time.monotonic()
    try:
        chat.warm()
        last = {"ok": True, "seconds": round(_time.monotonic() - started, 1)}
    except Exception as exc:              # noqa: BLE001 — 예열 실패는 이유를 남겨 다음 응답에 싣는다
        last = {"ok": False, "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                "seconds": round(_time.monotonic() - started, 1)}
    last["at"] = datetime.now(KST).isoformat(timespec="seconds")
    with _lock:
        _state["last"] = last


def warmup(chat: Any, *, count: Callable[[], None], defer: Callable[[Callable[[], None]], None],
           dedupe_seconds: float) -> dict[str, Any]:
    """`{status: warm | warming | unavailable, model, last_attempt}`. `count` 는 실제로 부를 때만 부른다(막히면 예외)."""
    if chat is None or not hasattr(chat, "warm"):
        return {"status": "unavailable", "model": None, "reason": "모델이 연결돼 있지 않다", "last_attempt": None}
    with _lock:
        last = _state["last"]
    model = getattr(chat, "model", None)
    try:
        if chat.loaded():
            return {"status": "warm", "model": model, "last_attempt": last}
    except Exception as exc:              # noqa: BLE001 — 상태를 못 물어도 예열은 해 본다(이유는 싣는다)
        last = {**(last or {}), "status_error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    now = _time.monotonic()
    with _lock:                           # 확인과 자리 잡기를 한 번에 — 동시에 온 둘이 모두 부르지 않게
        before = _state["started"]
        if now - before < dedupe_seconds:
            return {"status": "warming", "model": model, "last_attempt": last, "deduped": True}
        _state["started"] = now
    try:
        count()                           # 남용 방어 — 막히면 여기서 예외(부르는 쪽이 429/503 으로)
    except Exception:
        with _lock:
            _state["started"] = before    # 막힌 요청은 자리를 돌려준다
        raise
    defer(lambda: _run(chat))
    return {"status": "warming", "model": model, "last_attempt": last}


__all__ = ["reset", "warmup"]
