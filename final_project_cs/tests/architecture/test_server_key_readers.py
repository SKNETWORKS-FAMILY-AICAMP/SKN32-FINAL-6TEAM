# -*- coding: utf-8 -*-
"""서버용 OpenAI 키(`openai_api_key_server`)를 읽는 곳은 **모델 서버 장애 넘김 한 곳**뿐이다. `[2026-10-15 문서 점검]`

사용자 지시(2026-10-07): 「서버키(개인키 말고)로 자동 전환」. 그 키는 개발 중 호출 · 시험 · 측정에 새어 나가면 요금과 노출 위험이 생기므로, 제품 코드 안에서 이 이름을 쓰는 파일이
정해진 둘 — 선언(`core/settings.py`)과 읽는 곳(`infrastructure/llm_failover.py`) — 에서 늘지 않게 지킨다. 키 값을 쓰는 스크립트(`scripts/embed_chunks_openai.py`)는 제품 코드 밖이다.

재현:

    python -m pytest tests/architecture/test_server_key_readers.py -v
"""
from __future__ import annotations

from pathlib import Path

APP = Path("app")
ALLOWED = {
    "app/core/settings.py",                    # 설정 필드 선언(`extra="forbid"` 라 이름이 먼저 선언돼야 한다)
    "app/infrastructure/llm_failover.py",      # 넘김 장치 — 이 키를 읽는 유일한 제품 코드
}


def _files_naming_the_server_key() -> set[str]:
    found = set()
    for path in APP.rglob("*.py"):
        # 백업 사본(`_backup/`) · 옛 판 보존(`legacy/`)은 제품 코드가 아니다 — 덮어쓰기 전 백업 규칙으로 app 안에도 사본이 쌓인다
        if any(part in ("legacy", "__pycache__") or part.startswith("_backup") for part in path.parts):
            continue
        if "openai_api_key_server" in path.read_text(encoding="utf-8", errors="replace"):
            found.add(path.as_posix())
    return found


# invariant: INV-CS-SEC-012
def test_only_the_settings_declaration_and_the_failover_read_the_server_key():
    unexpected = sorted(_files_naming_the_server_key() - ALLOWED)
    assert not unexpected, (
        "서버용 OpenAI 키를 읽는 제품 코드가 늘었다 — 개발 중 호출 · 시험 · 측정으로 새면 요금과 노출 위험이 생긴다. "
        f"넘김 장치(llm_failover.py)를 거치게 하거나, 정말 필요하면 사용자 지시를 받아 이 목록과 불변식 INV-CS-SEC-012 를 같이 고친다: {unexpected}")


def test_the_check_actually_finds_the_known_readers():
    # 검사 자체가 아무것도 못 찾으면 위 시험은 영원히 통과한다 — 알려진 두 곳을 실제로 찾는지 본다
    assert ALLOWED <= _files_naming_the_server_key()
