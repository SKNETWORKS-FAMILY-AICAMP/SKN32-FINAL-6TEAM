"""옛 판(예: `tripilot-api:keep-2026-10`)을 지금의 DB 구조에 붙여도 뜨는지, 운영을 건드리지 않고 시험한다.

운영 DB·운영 설정 파일(.env)을 **읽지도 쓰지도 않는다.** 시험은 바깥과 연결되지 않는 임시 네트워크 안에서만 돈다.
  1. 최신 이미지의 마이그레이션으로 임시 DB(메모리 위, 비어 있음)에 「지금의 DB 구조」를 만든다.
  2. 옛 이미지의 마이그레이션이 그 구조에서 오류 없이 끝나는지 본다(롤백 때 옛 이미지가 새 표를 견디는지).
  3. 옛 이미지의 API 를 그 DB 에 붙여 띄우고 /health 가 나오는지, 로그에 표·칸 오류가 없는지 본다.
  4. 두 이미지의 설정 이름을 비교한다. 설정은 `extra="forbid"` 라서 옛 이미지가 모르는 새 이름이 운영 `.env` 에 있으면
     옛 이미지는 켜지지 않는다 — `--env-names-file` 로 이름만(값은 읽지 않는다) 대조할 수 있다.
끝나면 임시 컨테이너·네트워크를 항상 지운다. 일꾼(worker)은 띄우지 않는다(알림이 나가면 안 되므로).

사용: python3 restore_check.py --old-image tripilot-api:keep-2026-10 --new-image tripilot-api:local [--mobility-dir DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import time
from uuid import uuid4

SCHEMA_ERRORS = re.compile(r"UndefinedTable|UndefinedColumn|does not exist|ValidationError|Extra inputs|Traceback", re.I)
LIST_FIELDS = ("from app.core.settings import Settings; "
               "print('\\n'.join(sorted(Settings.model_fields)))")


class CheckError(RuntimeError):
    pass


class Docker:
    def run(self, args, timeout=120, check=True):
        try:
            result = subprocess.run(["docker", *args], text=True, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise CheckError(f"docker {args[0]} 시간 초과({timeout}초)") from exc
        if check and result.returncode:
            raise CheckError(f"docker {args[0]} 실패(코드 {result.returncode})")
        return result.returncode, (result.stdout or "") + (result.stderr or "")


def env_args(env):
    return [arg for key, value in env.items() for arg in ("-e", f"{key}={value}")]


def settings_fields(docker, image):
    _, out = docker.run(["run", "--rm", "--network", "none", "--entrypoint", "python", image, "-c", LIST_FIELDS],
                        timeout=120)
    return {line.strip() for line in out.splitlines() if re.fullmatch(r"[a-z0-9_]+", line.strip())}


def env_names(path):
    """환경 파일에서 `ACOP_` 이름만 읽는다. 값은 읽어도 버린다."""
    names = set()
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*(?:export\s+)?(ACOP_[A-Za-z0-9_]+)\s*=", line)
        if match:
            names.add(match.group(1)[len("ACOP_"):].lower())
    return names


def run_check(docker, *, old_image, new_image, db_image="pgvector/pgvector:pg17", mobility_dir=None,
              env_names_files=(), wait_seconds=240, say=print, sleep=time.sleep):
    token = uuid4().hex[:10]
    net, db, api = f"rc-{token}", f"rc-{token}-db", f"rc-{token}-api"
    password = uuid4().hex
    base_env = {
        "ACOP_DATABASE_URL": f"postgresql+psycopg://acop:{password}@{db}:5432/acop_cs",
        "ACOP_OPENAI_API_KEY": "restore-check-dummy", "ACOP_LLM_MODEL": "restore-check",
        "ACOP_EMBEDDING_MODEL": "restore-check", "ACOP_TENANT_ID": "restore-check",
        # 필수 비밀값(Settings 에서 기본값이 없는 것) — 임시 컨테이너 안에서만 쓰는 무작위 값이다. 운영 값과 무관하다.
        "ACOP_SECRET_KEY": uuid4().hex * 2, "ACOP_COMPOSER_JWT_SECRET": uuid4().hex * 2,
        "ACOP_COMPOSER_ISSUER_SECRET": uuid4().hex * 2,
    }
    results = []

    def record(name, ok, detail=""):
        results.append((name, ok, detail))
        say(("통과 " if ok else "실패 ") + name + (f" — {detail}" if detail else ""))
        return ok

    for image in (old_image, new_image, db_image):
        code, _out = docker.run(["image", "inspect", "--format", "{{.Id}}", image], check=False)
        if code:
            raise CheckError(f"이미지가 이 서버에 없다: {image} (정리 규칙으로 이미 지워졌을 수 있다 — `docker images` 로 남은 이름표를 확인한다)")
    try:
        docker.run(["network", "create", "--internal", net])
        docker.run(["run", "-d", "--name", db, "--network", net, "--network-alias", db, "--memory", "768m",
                    "--tmpfs", "/var/lib/postgresql/data:rw,size=1g",
                    "-e", "POSTGRES_USER=acop", "-e", f"POSTGRES_PASSWORD={password}", "-e", "POSTGRES_DB=acop_cs",
                    db_image])
        ready = False
        for _ in range(60):
            code, _out = docker.run(["exec", db, "pg_isready", "-U", "acop", "-d", "acop_cs"], check=False)
            if code == 0:
                ready = True
                break
            sleep(2)
        if not record("임시 DB 준비", ready):
            return results

        def app_run(image, command, name_suffix, extra=()):
            return docker.run(["run", "--rm", "--name", f"rc-{token}-{name_suffix}", "--network", net,
                               "--memory", "1g", *env_args(base_env), *extra, "--entrypoint", "python", image, *command],
                              timeout=300, check=False)

        code, out = app_run(new_image, ["-m", "app.infrastructure.db.migrate"], "mig-new")
        if not record("최신 이미지로 지금의 DB 구조 만들기", code == 0, "" if code == 0 else out.strip()[-200:]):
            return results
        code, out = app_run(old_image, ["-m", "app.infrastructure.db.migrate"], "mig-old")
        record("옛 이미지의 마이그레이션이 새 구조에서 오류 없이 끝남", code == 0, "" if code == 0 else out.strip()[-200:])

        extra = ["-v", f"{mobility_dir}:/data/mobility/processed:ro", "-e", "ACOP_MOBILITY_DATA_DIR=/data/mobility/processed"] \
            if mobility_dir else []
        docker.run(["run", "-d", "--name", api, "--network", net, "--memory", "2g", "--cpus", "1",
                    *env_args(base_env), *extra, old_image])
        healthy = False
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            code, out = docker.run(["exec", api, "curl", "-fsS", "http://127.0.0.1:8043/health"], check=False)
            if code == 0:
                healthy = True
                break
            sleep(5)
        record("옛 이미지 API 가 새 DB 구조에서 /health 응답", healthy, "" if healthy else "시간 안에 응답 없음")
        _code, logs = docker.run(["logs", api], check=False)
        errors = sorted({line.strip()[:160] for line in logs.splitlines() if SCHEMA_ERRORS.search(line)})
        record("기동 로그에 표·칸·설정 오류 없음", not errors, "; ".join(errors[:3]))

        new_fields, old_fields = settings_fields(docker, new_image), settings_fields(docker, old_image)
        only_new = sorted(new_fields - old_fields)
        say(f"설정 이름: 최신에만 있는 것 {len(only_new)}개" + (f" — {', '.join('ACOP_' + n.upper() for n in only_new[:12])}"
                                                           + (" …" if len(only_new) > 12 else "") if only_new else ""))
        for path in env_names_files:
            conflicts = sorted(env_names(path) & set(only_new))
            record(f"설정 파일 {Path(path).name} 의 새 이름이 옛 이미지를 막지 않음", not conflicts,
                   "" if not conflicts else "옛 이미지가 모르는 이름: " + ", ".join("ACOP_" + n.upper() for n in conflicts))
        if not env_names_files and only_new:
            say("주의: 운영 .env 에 위 이름이 하나라도 있으면 옛 이미지는 켜지지 않는다(extra=forbid). --env-names-file 로 대조할 수 있다")
        return results
    finally:
        for name in (api, db):
            docker.run(["rm", "-f", name], check=False)
        docker.run(["network", "rm", net], check=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old-image", required=True)
    parser.add_argument("--new-image", required=True)
    parser.add_argument("--db-image", default="pgvector/pgvector:pg17")
    parser.add_argument("--mobility-dir", help="이동 자료 폴더(읽기 전용으로 붙인다). 없으면 API 가 못 뜰 수 있다")
    parser.add_argument("--env-names-file", action="append", default=[], help="환경 파일(이름만 읽는다)")
    parser.add_argument("--wait-seconds", type=int, default=240)
    args = parser.parse_args(argv)
    try:
        results = run_check(Docker(), old_image=args.old_image, new_image=args.new_image, db_image=args.db_image,
                            mobility_dir=args.mobility_dir, env_names_files=args.env_names_file,
                            wait_seconds=args.wait_seconds)
    except CheckError as exc:
        print(f"복원 시험 실패: {exc}")
        raise SystemExit(2)
    raise SystemExit(0 if results and all(ok for _n, ok, _d in results) else 1)


if __name__ == "__main__":
    main()
