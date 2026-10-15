"""오라클 서버 관리자웹앱의 비공개 설정(control/.env.admin)을 고친다. `[2026-10-15]`

관리자웹앱 컨테이너 안에서 돌린다 — 직접 부르지 말고 `admin_env.sh` 로 부른다.

    keys               고객 API 를 부를 열쇠 5개를 이 기계의 비밀값으로 만들어 넣는다(화면에 찍지 않는다)
    operator --id ID   운영자 계정을 넣거나 비밀번호를 바꾼다(비밀번호는 직접 입력, 두 번, 12자 이상)
                       권한은 기본으로 관리자웹앱 화면 전체(CONSOLE_SCOPES) — 좁히려면 --scopes
    scopes --id ID     비밀번호는 그대로 두고 권한만 바꾼다(기본: 화면 전체)
    remove --id ID     운영자 계정을 뺀다
    list               운영자 id 와 열쇠가 있는지만 보여 준다(비밀값은 보이지 않는다)

★값은 홑따옴표로 감싸 쓴다. 비밀번호 해시에 `$` 가 들어 있어 감싸지 않으면 Compose 가 변수로 읽어 지운다.
★다른 사람 계정은 그대로 두고 같은 id 만 바꾼다(scripts/ui_operator.py 와 같은 규칙).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

ENV = Path(os.environ.get("ADMIN_ENV_FILE", "/control/.env.admin"))
# 운영 앱이 고객 API 를 부를 때 쓰는 scope(app/presentation/admin_api.py · ui/routes.py 의 _call_api) —
# `[2026-10-15]` limits:read · limits:write 를 더했다. 관리자웹앱 「웹 제한값」 · 「보관 기간」 화면이 운영 앱의 `/admin/limits` ·
# `/admin/retention` 을 이 열쇠로 부른다(admin_api.existing_settings). 빠져 있어 두 화면이 503 「운영용 제한 설정 키가 설정되지 않았습니다」였다.
OPS_SCOPES = ("action:approve", "delegation:read", "delegation:write", "limits:read", "limits:write")
# 관리자웹앱 화면 전체를 쓰는 운영자 scope(app/presentation/admin_api.py 의 require) —
# 첫 화면(snapshot)이 ops:introspect, 접수 목록이 case:read, 한도 화면이 limits:read/write 를 본다.
CONSOLE_SCOPES = ("action:approve", "case:read", "delegation:read", "delegation:write",
                  "limits:read", "limits:write", "ops:introspect")


def read() -> dict[str, str]:
    rows: dict[str, str] = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] == "'":
                    value = value[1:-1]
                rows[key.strip()] = value
    return rows


def write(rows: dict[str, str]) -> None:
    for key, value in rows.items():
        if "'" in value or "\n" in value:
            raise SystemExit(f"{key} 값에 홑따옴표·줄바꿈이 들어 있어 쓰지 않았다")
    temp = ENV.with_name(ENV.name + ".tmp")
    temp.write_text("".join(f"{key}='{value}'\n" for key, value in rows.items()), encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(ENV)


def operators(rows: dict[str, str]) -> list[dict]:
    raw = rows.get("ACOP_UI_OPERATORS", "").strip()
    return json.loads(raw) if raw else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("keys")
    add = sub.add_parser("operator")
    add.add_argument("--id", required=True)
    add.add_argument("--scopes", default=",".join(CONSOLE_SCOPES))
    grant = sub.add_parser("scopes")
    grant.add_argument("--id", required=True)
    grant.add_argument("--scopes", default=",".join(CONSOLE_SCOPES))
    drop = sub.add_parser("remove")
    drop.add_argument("--id", required=True)
    sub.add_parser("list")
    args = parser.parse_args(argv)
    rows = read()

    if args.command == "list":
        print("운영자:", ", ".join(f"{row['id']}({len(row.get('scopes', []))}권한)" for row in operators(rows)) or "없음")
        keys = json.loads(rows.get("ACOP_OPS_API_KEYS") or "{}")
        print("고객 API 열쇠:", ", ".join(scope for scope in OPS_SCOPES if keys.get(scope)) or "없음")
        return 0

    if args.command == "keys":
        from app.presentation.security import _development_key
        rows["ACOP_OPS_API_KEYS"] = json.dumps({scope: _development_key(scope) for scope in OPS_SCOPES},
                                               separators=(",", ":"))
        write(rows)
        print(f"고객 API 열쇠 {len(OPS_SCOPES)}개를 넣었다(값은 화면에 찍지 않았다)")
        return 0

    current = [row for row in operators(rows) if row.get("id") != args.id]
    if args.command == "remove":
        if len(current) == len(operators(rows)):
            print(f"{args.id} 계정이 없다 — 아무것도 바꾸지 않았다", file=sys.stderr)
            return 2
        rows["ACOP_UI_OPERATORS"] = json.dumps(current, ensure_ascii=False, separators=(",", ":"))
        write(rows)
        print(f"{args.id} 계정을 뺐다. 남은 계정 {len(current)}개")
        return 0

    from app.core.settings import get_guardrails
    allowed = set(get_guardrails().get("security.scopes"))
    scopes = sorted({s.strip() for s in args.scopes.split(",") if s.strip()})
    unknown = [s for s in scopes if s not in allowed]
    if unknown:
        print(f"모르는 scope: {unknown}", file=sys.stderr)
        return 2

    if args.command == "scopes":
        # 비밀번호는 그대로 두고 권한만 바꾼다.
        everyone = operators(rows)
        target = next((row for row in everyone if row.get("id") == args.id), None)
        if target is None:
            print(f"{args.id} 계정이 없다 — 아무것도 바꾸지 않았다", file=sys.stderr)
            return 2
        target["scopes"] = scopes
        rows["ACOP_UI_OPERATORS"] = json.dumps(everyone, ensure_ascii=False, separators=(",", ":"))
        write(rows)
        print(f"{args.id} 권한 {len(scopes)}개 — " + ", ".join(scopes))
        return 0

    from app.presentation.ui.auth import hash_password
    first = getpass.getpass(f"{args.id} 의 비밀번호(12자 이상, 화면에 안 보임): ")
    if len(first) < 12:
        print("비밀번호는 12자 이상이어야 한다 — 아무것도 바꾸지 않았다", file=sys.stderr)
        return 2
    if getpass.getpass("한 번 더: ") != first:
        print("두 입력이 다르다 — 아무것도 바꾸지 않았다", file=sys.stderr)
        return 2
    current.append({"id": args.id, "password_hash": hash_password(first), "scopes": scopes})
    rows["ACOP_UI_OPERATORS"] = json.dumps(current, ensure_ascii=False, separators=(",", ":"))
    write(rows)
    print(f"{args.id} 계정을 넣었다. 계정 {len(current)}개 — " + ", ".join(row["id"] for row in current))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
