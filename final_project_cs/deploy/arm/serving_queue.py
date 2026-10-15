"""Oracle ARM 자체의 6시간 일감 공급·상시 실행. Codex 예약에 의존하지 않는다."""
from contextlib import contextmanager
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
import serving_checks as probe

BASE = Path(os.environ["DEPLOY_BASE"])
ROOT = BASE / "serving-queue"
HORIZON = 6 * 60 * 60
MIN_FREE = 3 * 1024**3
DEFAULT_SECONDS = 480  # 초기 추정. 완료 회차의 실제 시간으로 갱신한다.
MIN_ESTIMATE = 30
MAX_PENDING = 720


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.replace(path)


@contextmanager
def locked():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "state.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = ROOT / "queue.json"
        state = json.loads(path.read_text()) if path.exists() else {"version": 1, "jobs": [], "estimates": {}, "failed_profiles": {}}
        yield state
        atomic(path, state)


def estimate(state, profile):
    return max(MIN_ESTIMATE, min(HORIZON, float(state["estimates"].get(profile, DEFAULT_SECONDS))))


def refill(state, now, sha=None):
    """현재 배포판에서 실행 가능한 시간만 보충하며 실패한 작업은 보존한다."""
    if sha is None:
        path = BASE / "state.json"
        sha = json.loads(path.read_text()).get("current") if path.exists() else None
    failed = state.get("failed_profiles", {})
    allowed = [profile for profile in probe.PROFILES if sha and failed.get(profile) != sha]
    pending = [j for j in state["jobs"] if j["status"] in ("pending", "running")
               and (j["status"] == "running" or j["profile"] in allowed)]
    blocked = [j for j in state["jobs"] if j["status"] == "pending" and j["profile"] not in allowed]
    remaining = sum(max(0, estimate(state, j["profile"]) - (now-j.get("started", now) if j["status"] == "running" else 0)) for j in pending)
    window = int(now // HORIZON)
    count = 0
    while allowed and remaining < HORIZON and len(pending) < MAX_PENDING:
        profile = allowed[len(state["jobs"]) % len(allowed)]
        job = {"id": f"w{window}-{len(state['jobs'])+1:08d}", "window": window, "profile": profile,
               "created": now, "status": "pending", "planned_checks": len(probe.PLANNED)}
        state["jobs"].append(job)
        pending.append(job)
        remaining += estimate(state, profile)
        count += 1
    state.update(last_refill=now, estimated_pending_seconds=remaining,
                 estimate_basis="completed_batch_elapsed_ewma_or_initial_480s_estimate",
                 target_seconds=HORIZON, last_added=count, independent_accuracy=False,
                 ready_pending_jobs=sum(j["status"] == "pending" for j in pending),
                 blocked_pending_jobs=len(blocked), refill_sha=sha,
                 eligible_profiles=allowed)
    return count


def readiness():
    if shutil.disk_usage(BASE).free < MIN_FREE:
        return None, "disk_free_below_3GiB"
    path = BASE / "state.json"
    deployed = json.loads(path.read_text()) if path.exists() else {}
    if not deployed.get("current"):
        return None, deployed.get("blocked_on", "verified_deployment_pending")
    try:
        with urllib.request.urlopen(probe.API + "/health", timeout=5) as response:
            if response.status != 200:
                return None, "api_unhealthy"
    except Exception:
        return None, "api_unavailable"
    return deployed["current"], None


def select_job(state, sha):
    for job in state["jobs"]:
        if job["status"] == "pending" and state["failed_profiles"].get(job["profile"]) != sha:
            return job
    return None


def finish(state, job_id, summary, now):
    job = next(j for j in state["jobs"] if j["id"] == job_id)
    good = summary["passed"] == summary["total"]
    job.update(status="completed" if good else "failed", finished=now, summary=summary)
    if good:
        old = estimate(state, job["profile"])
        state["estimates"][job["profile"]] = max(MIN_ESTIMATE, 0.5*old + 0.5*summary["seconds"])
    else:
        state["failed_profiles"][job["profile"]] = job["sha"]


def recover(state):
    for job in state["jobs"]:
        if job["status"] == "running":
            output = ROOT / "answers" / job["id"] / "summary.json"
            if output.exists():
                finish(state, job["id"], json.loads(output.read_text()), time.time())
            else:
                job.update(status="interrupted", finished=time.time(), reason="worker_exit_without_summary")
                state["failed_profiles"][job["profile"]] = job["sha"]


def step():
    sha, reason = readiness()
    with locked() as state:
        refill(state, time.time(), sha)
        state["observed_at"] = datetime.now(timezone.utc).isoformat()
        state["blocked_on"] = reason
    if reason:
        return False
    # 회차 하나만 잠근다. 다음 회차 전 CD가 실행될 틈을 둔다.
    with (BASE / "deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        sha, reason = readiness()
        if reason:
            return False
        with locked() as state:
            job = select_job(state, sha)
            if not job:
                state["blocked_on"] = "profiles_failed_on_current_sha"
                return False
            job.update(status="running", sha=sha, started=time.time())
            selected = dict(job)
            state["blocked_on"] = None
        output = ROOT / "answers" / selected["id"]
        try:
            summary = probe.run(selected["profile"], output)
        except Exception as exc:
            summary = {"passed": 0, "total": len(probe.PLANNED), "attempted": 0,
                       "seconds": time.time()-selected["started"], "failure": type(exc).__name__}
            atomic(output / "summary.json", summary)
        with locked() as state:
            finish(state, selected["id"], summary, time.time())
    print(json.dumps({"job": selected["id"], "passed": summary["passed"], "total": summary["total"]}), flush=True)
    return True


def worker(once=False):
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("worker_already_running", flush=True)
            return
        with locked() as state:
            recover(state)
        while True:
            worked = step()
            if once:
                return
            if worked:
                # 긴 검사들 때문에 5분 CD 타이머가 계속 잠금을 놓치지 않도록 회차 사이에 요청한다.
                result = subprocess.run(["systemctl", "start", "--no-block", "tripilot-arm-cd.service"], check=False)
                if result.returncode:
                    print("cd_wakeup_failed", flush=True)
            time.sleep(10 if worked else 60)


def main():
    if sys.argv[1:] == ["refill"]:
        with locked() as state:
            added = refill(state, time.time())
            print(json.dumps({"added": added, "estimated_pending_seconds": state["estimated_pending_seconds"],
                              "target_seconds": HORIZON, "estimate_not_actual_runtime": True}), flush=True)
    elif sys.argv[1:] == ["once"]:
        worker(once=True)
    else:
        worker()


if __name__ == "__main__":
    main()
