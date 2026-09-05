"""배포 중인 프롬프트가 **허용 목록 그대로인가**.

★기존 검증은 허용 목록 **안쪽만** 봤다 — "response.generate 가 active 1개인가".
  목록 **밖**에 active 가 남아 있는지는 아무도 안 봤고, 실제로 사라진 Team 의
  프롬프트 넷이 남아 셋이 active=true 였다(2026-09-06 발견):

      order_shipping.answer.repair · return_exchange.answer ·
      return_exchange.answer.repair

  `team_modules_v1` 이 `legacy/` 로 옮겨졌는데 DB 행은 그대로였다. 지금 코드가
  그 키를 요청하지 않으므로 동작에 해는 없었지만, **"배포 중인 프롬프트가 몇
  개인가" 를 세면 2 가 아니라 5 로 보인다.**

★지우지 않고 `active=false` 로 내렸다. `prompts` 는 "덮어쓰지 않고 공존시킨다"는
  버전 기록이다(`CLAUDE.md` §1). 지우면 그때 무엇을 썼는지가 사라진다.
"""
from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ALLOWED_PROMPT_KEYS


def _active_keys() -> set[str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT prompt_key FROM prompts WHERE active=true")
        return {row[0] for row in cur.fetchall()}


def test_no_active_prompt_outside_the_allowlist():
    stray = sorted(_active_keys() - set(ALLOWED_PROMPT_KEYS))
    assert not stray, (
        f"허용 목록 밖인데 active=true 인 프롬프트가 있다: {stray}. "
        "지우지 말고 active=false 로 내려라 — 기록은 남긴다.")


@pytest.mark.parametrize("key", sorted(ALLOWED_PROMPT_KEYS))
def test_each_allowed_key_has_exactly_one_active_version(key):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM prompts WHERE prompt_key=%s AND active=true", (key,))
        assert cur.fetchone()[0] == 1, f"{key} 의 active 버전이 정확히 1개가 아니다"


def test_deactivating_does_not_erase_history():
    """★내린 프롬프트도 행은 남아 있어야 한다 — 그때 무엇을 썼는지의 기록이다."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM prompts WHERE active=false")
        assert cur.fetchone()[0] > 0
