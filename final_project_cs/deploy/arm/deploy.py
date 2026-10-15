"""develop SHA별 ARM64 빌드·상태 검사·실패 복구. 호스트 환경 파일은 별도 보관한다."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = Path(os.environ["DEPLOY_BASE"])
REPO = BASE / "repo"
CONTROL = BASE / "control"
STATE = BASE / "state.json"
PATHS = ["app", "config", "prompts", "scripts", "deploy", "frontend/apps/web", "requirements.txt", "knowledge"]
# 서버 전용 덧씌움(2026-10-12 검색 수정). develop 원본이 바뀌면 멈추고 사람이 본다 — 수정이 develop 에 들어가면 지운다.
OVERLAY = CONTROL / "prepare_search_release.py"


def run(*args, **kwargs):
    print("실행:", *args, flush=True)
    kwargs.setdefault("text", True)
    return subprocess.run(args, check=True, **kwargs)


def git(*args):
    return run("git", "-c", "safe.directory=" + str(REPO), "-C", str(REPO), *args, stdout=subprocess.PIPE).stdout.strip()


def compose(tag, *args):
    return run("docker", "compose", "--env-file", str(CONTROL / ".env"),
               "-f", str(CONTROL / "compose.yml"), *args,
               env={**os.environ, "IMAGE_TAG": tag}, cwd=CONTROL)


def save(state):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(STATE)


def start_app(tag):
    if (CONTROL / "prepare_guardrails.py").is_file():
        # 이미지별 원본에 다시 적용해 새 develop 설정을 오래된 사본으로 덮지 않는다.
        compose(tag, "run", "--rm", "--no-deps", "-v",
                str(CONTROL / "prepare_guardrails.py") + ":/prepare_guardrails.py:ro",
                "api", "python", "/prepare_guardrails.py")
    # HTTP 건강 검사를 끈 worker를 Compose --wait에 넣으면 실제 기동 중에도 오류가 난다.
    compose(tag, "up", "-d", "--wait", "--wait-timeout", "360", "db", "model-adapter", "api", "web")
    compose(tag, "up", "-d", "worker")
    healthy(tag)


def healthy(tag):
    for _ in range(90):
        try:
            for port, path in ((8043, "/health"), (13000, "/")):
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
                    assert response.status == 200
            time.sleep(10)
            raw = subprocess.check_output(["docker", "compose", "--env-file", str(CONTROL / ".env"),
                                           "-f", str(CONTROL / "compose.yml"), "ps", "-q"],
                                          env={**os.environ, "IMAGE_TAG": tag}, text=True)
            ids = raw.split()
            rows = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
            assert len(rows) == 5
            assert all(row["State"]["Running"] and row["RestartCount"] == 0 for row in rows)
            assert all(row["State"].get("Health", {}).get("Status", "healthy") == "healthy" for row in rows)
            return
        except Exception:
            time.sleep(5)
    raise RuntimeError("상태 검사 실패")


def prune_old_releases(state):
    """배포가 성공한 뒤에만 부른다: 오래된 이미지·소스 폴더를 지운다(최근 3개 + 달마다 하나, 규칙은 deploy/image_retention.py).
    정리가 실패해도 배포 결과는 그대로여야 하므로 모든 오류를 삼키고 한 줄만 남긴다."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import image_retention as ir
        current, previous = state["current"], state.get("previous")
        good = {row["sha"]: datetime.fromtimestamp(row["at"], timezone.utc) for row in state.get("history", [])}
        protected = [sha for sha in (current, previous) if sha]
        result = ir.run_retention(ir.Docker(), app_repos=["tripilot-arm-api", "tripilot-arm-web"],
                                  protected_tags=[sha[:12] for sha in protected], good=good, apply=True,
                                  say=lambda line: print(line, flush=True))
        ir.prune_release_dirs(BASE / "releases", set(result["apps"]["keep"]), protected, True,
                              lambda line: print(line, flush=True))
    except Exception as exc:  # 정리는 덤이다 — 배포를 되돌리지 않는다
        print("경고: 이미지 정리 실패 -", type(exc).__name__, flush=True)


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    with (BASE / "deploy.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("배포 또는 질의 검사 실행 중", flush=True)
            return
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        data = BASE / "mobility" / "processed" / "mobility"
        required = ["line_station_order_v1.json", "transfer_walk_v1.json", "bus_route_v1.jsonl",
                    "bus_stops_v1.jsonl", "station_coords.json"]
        missing = [name for name in required if not (data / name).is_file()]
        if not any((data / name).is_file() for name in ("timetable_v1.jsonl.gz", "timetable_v1.jsonl")):
            missing.append("timetable")
        if missing:
            save({**state, "blocked_on": "mobility_data_missing", "missing_files": missing})
            print("필수 이동 자료 대기; 이미지·앱 반복 실행 안 함", flush=True)
            return
        state.pop("blocked_on", None)
        state.pop("missing_files", None)
        git("fetch", "--depth", "1", "origin", "develop")
        sha = git("rev-parse", "FETCH_HEAD")
        if sha == state.get("overlay_blocked_sha"):
            print("덧씌움 충돌로 막힌 SHA — 사람 검토 대기(새 develop 커밋이 오면 다시 시도)", flush=True)
            return
        if sha in (state.get("current"), state.get("failed")):
            print("반영할 새 변경 없음", flush=True)
            return
        if shutil.disk_usage(BASE).free < 10 * 1024**3:
            raise RuntimeError("새 이미지 빌드 여유 공간 10GiB 미만; 기존 자료는 보존")
        release = BASE / "releases" / sha
        release.mkdir(parents=True, exist_ok=True)
        # git archive는 추적된 해당 SHA만 내보낸다. 환경 파일·로컬 수정은 이미지에 넣지 않는다.
        archive = run("git", "-c", "safe.directory=" + str(REPO), "-C", str(REPO), "archive", sha,
                      *["final_project_cs/" + p for p in PATHS], stdout=subprocess.PIPE, text=False).stdout
        subprocess.run(["tar", "-x", "-C", str(release)], input=archive, check=True)
        src = release / "final_project_cs"
        (src / "var").mkdir(exist_ok=True)
        (src / "var" / "notice_phrasebook.json").write_text("[]", encoding="utf-8")
        if OVERLAY.is_file():
            try:
                run("python3", str(OVERLAY), str(src))
            except subprocess.CalledProcessError:
                # 고장이 아니라 사람이 볼 일이다. 같은 SHA 를 5분마다 다시 시도하지 않고 한 번만 실패로 남긴다.
                save({**state, "overlay_blocked_sha": sha, "overlay_blocked_at": time.time()})
                raise
        tag = sha[:12]
        previous = state.get("current")
        save({**state, "building": sha, "started_at": time.time()})
        try:
            for kind in ("api", "web"):
                cmd = ["docker", "buildx", "build", "--builder", "tripilot-arm", "--platform", "linux/arm64",
                       "--load", "--progress", "plain", "-t", f"tripilot-arm-{kind}:{tag}",
                       "-f", str(src / "deploy" / f"Dockerfile.{kind}")]
                if kind == "web":
                    # 공개 프록시와 같은 출처를 사용한다. 방문자 PC의 루프백으로 보내지 않는다.
                    cmd += ["--build-arg", "NEXT_PUBLIC_API_BASE="]
                run(*cmd, str(src))
            compose(tag, "up", "-d", "--wait", "db", "model-adapter")
            compose(tag, "run", "--rm", "--no-deps", "api", "python", "-m", "app.infrastructure.db.migrate")
            compose(tag, "run", "--rm", "--no-deps", "-v", str(CONTROL / "init_test_db.py") + ":/init_test_db.py:ro",
                    "api", "python", "-c", "exec(open('/init_test_db.py').read())")
            start_app(tag)
            images = json.loads(subprocess.check_output(["docker", "image", "inspect",
                                f"tripilot-arm-api:{tag}", f"tripilot-arm-web:{tag}"], text=True))
            save({"current": sha, "previous": previous, "deployed_at": time.time(),
                  "history": [*state.get("history", []), {"sha": sha, "at": time.time()}][-400:],
                  "image_ids": [row["Id"] for row in images],
                  "image_architectures": [row["Architecture"] for row in images],
                  "branch": "develop", "scope": "isolated_internal_serving_test"})
        except Exception:
            state.pop("building", None)
            save({**state, "failed": sha, "failed_at": time.time()})
            if previous:
                start_app(previous[:12])
            raise
        prune_old_releases(json.loads(STATE.read_text()))


if __name__ == "__main__":
    main()
