"""Register the deployable prompt set and verify its active state."""
from __future__ import annotations

import sys

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ALLOWED_PROMPT_KEYS, register_prompt_files


def main() -> int:
    settings = get_settings()
    with get_connection() as conn:
        ids, skipped = register_prompt_files(
            conn, prompt_root="prompts", model_family=settings.llm_model
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prompt_key, count(*) FROM prompts "
                "WHERE prompt_key = ANY(%s) AND active=true GROUP BY prompt_key",
                (list(ALLOWED_PROMPT_KEYS),),
            )
            active = dict(cur.fetchall())
            # ★허용 목록 **밖**에 active 프롬프트가 남아 있는지도 본다.
            #   전에는 안쪽만 검사해서, 사라진 Team 의 프롬프트가 active=true 로
            #   남아 있어도 아무도 몰랐다 — 실제로 넷이 남아 있었고 셋이 active
            #   였다(2026-09-06 발견, `order_shipping.*`·`return_exchange.*`).
            #   "배포 중인 프롬프트가 몇 개인가" 를 세면 2 가 아니라 5 로 보인다.
            cur.execute(
                "SELECT prompt_key, count(*) FROM prompts "
                "WHERE NOT (prompt_key = ANY(%s)) AND active=true GROUP BY prompt_key",
                (list(ALLOWED_PROMPT_KEYS),),
            )
            stray = dict(cur.fetchall())

    for prompt_id in ids:
        print(f"등록: {prompt_id}")
    for path in skipped:
        print(f"건너뜀: {path}")
    missing_or_invalid = sorted(
        key for key in ALLOWED_PROMPT_KEYS if active.get(key) != 1
    )
    if missing_or_invalid:
        print("활성 프롬프트 검증 실패: " + ", ".join(missing_or_invalid), file=sys.stderr)
        return 1
    if skipped:
        print("허용 목록 밖 파일이 있어 실패 처리합니다.", file=sys.stderr)
        return 2
    if stray:
        # ★지우라고 하지 않는다. `prompts` 는 "덮어쓰지 않고 공존시킨다" 는
        #   버전 기록이다(`CLAUDE.md` §1). 내려야 할 것은 active 플래그다.
        print("허용 목록 밖인데 active=true 인 프롬프트가 있습니다: "
              + ", ".join(f"{k}({n})" for k, n in sorted(stray.items())),
              file=sys.stderr)
        print("   → 지우지 말고 active=false 로 내리세요. 기록은 남깁니다.",
              file=sys.stderr)
        return 3
    print(f"활성 프롬프트 {len(ALLOWED_PROMPT_KEYS)}개 검증 완료 (등록/재사용 {len(ids)}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
