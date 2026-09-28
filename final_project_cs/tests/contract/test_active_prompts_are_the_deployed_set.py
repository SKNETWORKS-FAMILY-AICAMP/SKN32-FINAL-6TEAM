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


def test_deactivating_does_not_erase_history(tmp_path):
    """★내린 프롬프트도 행은 남아 있어야 한다 — 그때 무엇을 썼는지의 기록이다.

    ★`[2026-09-24]` 전에는 「DB 에 active=false 행이 하나라도 있나」를 셌다. 그건 **이 개발 DB 의
      이력**을 본 것이지 코드가 지키는지를 본 게 아니라서, 빈 DB(CI)에서는 반드시 실패했다.
      이제 **시험 안에서** 한 판을 올리고 새 판으로 바꾼 뒤, 옛 판이 지워지지 않고 `active=false`
      로 남는지 본다. ★전부 **롤백되는 트랜잭션** 안에서 한다 — 배포 중인 프롬프트를 바꾸지 않는다.
    """
    import psycopg
    from uuid import uuid4

    from app.tools.read_tools import register_prompt_files

    key, tag = "response.generate", uuid4().hex[:8]
    folder = tmp_path / "response"
    folder.mkdir()
    with get_connection() as conn:
        with conn.transaction():
            (folder / f"generate.vold{tag}.md").write_text(f"옛 판 {tag}", encoding="utf-8")
            (old_id,), _ = register_prompt_files(conn, str(tmp_path), model_family="test")
            (folder / f"generate.vold{tag}.md").unlink()
            (folder / f"generate.vnew{tag}.md").write_text(f"새 판 {tag}", encoding="utf-8")
            (new_id,), _ = register_prompt_files(conn, str(tmp_path), model_family="test")

            with conn.cursor() as cur:
                cur.execute("SELECT prompt_id, active FROM prompts WHERE prompt_id = ANY(%s)",
                            ([old_id, new_id],))
                rows = dict(cur.fetchall())
                cur.execute("SELECT count(*) FROM prompts WHERE prompt_key=%s AND active", (key,))
                active_count = cur.fetchone()[0]
            # 배포 중인 프롬프트를 원래대로 돌린다 — 이 블록의 모든 쓰기를 되돌린다
            raise psycopg.Rollback()

    assert old_id != new_id
    assert rows == {old_id: False, new_id: True}, "옛 판이 지워졌거나 여전히 active 다"
    assert active_count == 1, "새 판으로 바꾼 뒤 active 가 정확히 하나여야 한다"
