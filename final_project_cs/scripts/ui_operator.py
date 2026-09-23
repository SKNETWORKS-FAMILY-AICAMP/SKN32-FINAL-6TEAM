# -*- coding: utf-8 -*-
"""운영 화면 로그인 계정 한 줄을 만든다. `[2026-09-23]` D-CS-007

    python -m scripts.ui_operator --id op-kim --scopes action:approve,delegation:write

비밀번호는 **직접 입력한다**(화면에 안 보인다, 두 번). 원문은 어디에도 남기지 않고
PBKDF2-SHA256 해시만 만든다. 출력된 한 줄을 `.env` 의 `ACOP_UI_OPERATORS=` 로 넣고 앱을 다시
띄운다. ★이미 있는 계정은 그대로 두고 같은 id 만 바꾼다 — 한 사람을 넣다가 다른 사람을 지우지 않게.

★`.env` 는 git 이 무시한다. 해시라도 저장소에 올리지 않는다.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys


def main(argv: list[str] | None = None) -> int:
    from app.core.settings import get_guardrails, get_settings
    from app.presentation.ui.auth import hash_password

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", required=True, help="운영자 id — 승인·처리 기록에 이 이름이 남는다")
    parser.add_argument("--scopes", default="action:approve,delegation:read,delegation:write",
                        help="쉼표로. 승인·바깥함 해소=action:approve, 위임 변경=delegation:write")
    args = parser.parse_args(argv)

    allowed = set(get_guardrails().get("security.scopes"))
    scopes = sorted({s.strip() for s in args.scopes.split(",") if s.strip()})
    unknown = [s for s in scopes if s not in allowed]
    if unknown:
        print(f"모르는 scope: {unknown} — 있는 것: {sorted(allowed)}", file=sys.stderr)
        return 2

    first = getpass.getpass(f"{args.id} 의 비밀번호: ")
    if len(first) < 12:
        print("비밀번호는 12자 이상으로 한다.", file=sys.stderr)
        return 2
    if getpass.getpass("한 번 더: ") != first:
        print("두 입력이 다르다 — 아무것도 만들지 않았다.", file=sys.stderr)
        return 2

    current = (get_settings().ui_operators or "").strip()
    rows = [row for row in (json.loads(current) if current else []) if row.get("id") != args.id]
    rows.append({"id": args.id, "password_hash": hash_password(first), "scopes": scopes})
    print("\n아래 한 줄을 .env 에 넣는다(있으면 바꾼다). 그다음 앱을 다시 띄운다.\n")
    print("ACOP_UI_OPERATORS=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    print(f"\n계정 {len(rows)}개 — " + ", ".join(row["id"] for row in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
