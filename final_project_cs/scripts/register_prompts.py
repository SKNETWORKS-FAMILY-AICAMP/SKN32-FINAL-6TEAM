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
    print(f"활성 프롬프트 {len(ALLOWED_PROMPT_KEYS)}개 검증 완료 (등록/재사용 {len(ids)}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
