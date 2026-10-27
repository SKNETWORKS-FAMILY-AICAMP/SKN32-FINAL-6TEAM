"""Publish the checked main revision and update existing EKS apps without replacing configuration."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

APPS = ("tripilot-api", "tripilot-worker", "tripilot-web", "tripilot-admin")
CI_NAMES = ("CI (main)", "CI (web)", "CI (admin)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REVISION = "guguroute.io/source-sha"
# The migration Job runs while the current API keeps serving. A DDL statement that waits for a table
# lock queues every later query on that table behind it, so the wait is bounded well inside the Job
# deadline and the whole transaction rolls back instead of stalling customer requests.
MIGRATION_DEADLINE_SECONDS = 600
MIGRATION_LOCK_TIMEOUT = "5s"
MIGRATION_STATEMENT_TIMEOUT = "5min"
# Kubernetes copies this file into the terminated container status (at most 4 KiB), so the
# deployment can name the migration outcome without reading container logs.
MIGRATION_RESULT_PATH = "/dev/termination-log"
MIGRATION_OUTCOMES = ("committed", "failed_before_commit", "commit_unknown")
DURATION_RE = re.compile(r"^([1-9][0-9]*)(s|min)$")
FAILURE_FILE = "aws-deploy-failure.json"


class DeploymentError(RuntimeError):
    pass


def seconds(value):
    """Return seconds for an explicit PostgreSQL duration such as ``5s`` or ``5min``."""
    match = DURATION_RE.fullmatch(value)
    if not match:
        raise DeploymentError("A positive duration with an explicit unit (s or min) is required")
    return int(match[1]) * (60 if match[2] == "min" else 1)


def command(args, *, capture=True, data=None, timeout=120):
    try:
        p = subprocess.run(args, input=data, text=True, capture_output=capture, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DeploymentError(f"{args[0]} operation timed out; inspect the remote result before retry") from exc
    if p.returncode:
        raise DeploymentError(f"{args[0]} operation failed (exit {p.returncode}); output withheld")
    return p.stdout if capture else ""


def json_command(args, **kwargs):
    return json.loads(command(args, **kwargs))


def output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")


def github(path):
    request = urllib.request.Request(
        os.environ.get("GITHUB_API_URL", "https://api.github.com") + path,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def checked_runs(runs, sha, required=None):
    """Require main; optional path-filtered checks must pass whenever scheduled.

    ``required`` narrows which checks must have finished (image publication may start once CI (main)
    passes). Any check that already finished without success still stops the run.
    """
    wait_for_all = required is None
    required = ("CI (main)",) if required is None else tuple(required)
    latest = {}
    for run in runs:
        if (run.get("head_sha") != sha or run.get("head_branch") != "main"
                or run.get("event") not in ("push", "workflow_dispatch")
                or run.get("name") not in CI_NAMES):
            continue
        name = run["name"]
        if name not in latest or run["id"] > latest[name]["id"]:
            latest[name] = run
    if any(name not in latest for name in required):
        return False
    for run in latest.values():
        if run["status"] != "completed":
            if wait_for_all or run["name"] in required:
                return False
            continue
        if run["conclusion"] != "success":
            raise DeploymentError(f"{run['name']} did not succeed")
    return True


def gate(timeout=2400, interval=10, main_only=False):
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = command(["git", "rev-parse", "HEAD"]).strip()
    if not SHA_RE.fullmatch(sha):
        raise DeploymentError("Invalid revision")
    trigger = os.environ.get("CD_TRIGGER_SHA", "")
    if trigger and trigger != sha:
        output("ready", "false")
        return
    required = ("CI (main)",) if main_only else None
    deadline = time.monotonic() + timeout
    while True:
        head = github(f"/repos/{repo}/branches/main")["commit"]["sha"]
        if head != sha:
            output("ready", "false")
            print("A newer main exists; this run will not deploy.")
            return
        result = github(f"/repos/{repo}/actions/runs?head_sha={sha}&per_page=100")
        if result.get("total_count", 0) > 100:
            raise DeploymentError("Too many check runs; refusing an incomplete gate")
        if checked_runs(result["workflow_runs"], sha, required):
            output("sha", sha)
            output("ready", "true")
            print("CI (main) succeeded for the current main; images may be published." if main_only
                  else "The current main and every scheduled CI check succeeded.")
            return
        if time.monotonic() >= deadline:
            raise DeploymentError("Timed out waiting for CI")
        time.sleep(interval)


def kubectl(namespace, *args, data=None):
    return json_command(["kubectl", "--namespace", namespace, *args], data=data, timeout=60)


def deployment(namespace, name):
    return kubectl(namespace, "get", "deployment", name, "-o", "json")


def immutable_image(image):
    if "@" not in image or not DIGEST_RE.fullmatch(image.rsplit("@", 1)[1]):
        raise DeploymentError("An immutable image digest is required")
    return image


def registry_digest(registry, repo, sha):
    data = json_command(["aws", "ecr", "describe-images", "--repository-name", repo,
                         "--image-ids", f"imageTag=git-{sha}", "--output", "json"])
    digest = data["imageDetails"][0]["imageDigest"]
    if not DIGEST_RE.fullmatch(digest):
        raise DeploymentError("Invalid ECR digest")
    return f"{registry}/{repo}@{digest}"


def asset_manifest(image):
    probe = (
        "from pathlib import Path; import hashlib,json;"
        "p=Path('/srv/datasets'); fs=sorted(x for x in p.rglob('*') if x.is_file());"
        "assert fs, 'Missing runtime data';"
        "h=hashlib.sha256();"
        "[(h.update(str(x.relative_to(p)).encode()),h.update(hashlib.file_digest(x.open('rb'),'sha256').digest())) for x in fs];"
        "print(json.dumps({'files':len(fs),'sha256':h.hexdigest()}))"
    )
    return json_command(["docker", "run", "--rm", "--network", "none", "--entrypoint",
                         "python", image, "-c", probe], timeout=300)


def publish(sha, namespace, registry):
    if not SHA_RE.fullmatch(sha):
        raise DeploymentError("Invalid revision")
    source = immutable_image(deployment(namespace, "tripilot-api")["spec"]["template"]["spec"]["containers"][0]["image"])
    public_url = os.environ["CD_PUBLIC_URL"].rstrip("/")
    settings = json.loads(os.environ["CD_WEB_BUILD_ENV"])
    if settings.get("NEXT_PUBLIC_DATA_MODE") != "live":
        raise DeploymentError("The production web build must use live data")
    # Values are existing public browser configuration, but keep them out of logs.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for value in [registry, source, public_url, *settings.values()]:
            if value:
                print("::add-mask::" + str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))
    root = Path("final_project_cs")
    phrasebook = root / "var/notice_phrasebook.json"
    phrasebook.parent.mkdir(exist_ok=True)
    if not phrasebook.exists():
        phrasebook.write_text("{}", encoding="utf-8")
    command(["docker", "pull", source], capture=False, timeout=300)
    code = f"guguroute-api-code:{sha}"
    command(["docker", "build", "--platform", "linux/amd64", "-f", str(root / "deploy/Dockerfile.api"),
             "-t", code, str(root)], capture=False, timeout=1200)
    api_tag = f"{registry}/tripilot-api:git-{sha}"
    command(["docker", "build", "--platform", "linux/amd64", "-f", str(root / "deploy/aws/Dockerfile.api"),
             "--build-arg", f"SOURCE_IMAGE={code}", "--build-arg", f"ASSET_IMAGE={source}",
             "--build-arg", f"GIT_SHA={sha}", "-t", api_tag, str(root)],
            capture=False, timeout=600)
    if asset_manifest(source) != asset_manifest(api_tag):
        raise DeploymentError("Runtime data differs from the existing AWS image")
    image_tags = {"tripilot-api": api_tag}
    web_tag = f"{registry}/tripilot-web:git-{sha}"
    build = ["docker", "build", "--platform", "linux/amd64", "-f", str(root / "deploy/Dockerfile.web"),
             "--label", f"org.opencontainers.image.revision={sha}", "-t", web_tag]
    for name, value in settings.items():
        if not re.fullmatch(r"NEXT_PUBLIC_[A-Z0-9_]+", name):
            raise DeploymentError("Unexpected public build setting")
        build += ["--build-arg", f"{name}={value}"]
    command([*build, str(root)], capture=False, timeout=1200)
    image_tags["tripilot-web"] = web_tag
    admin_tag = f"{registry}/tripilot-admin:git-{sha}"
    command(["docker", "build", "--platform", "linux/amd64", "-f", str(root / "deploy/Dockerfile.admin"),
             "--build-arg", f"API_IMAGE={api_tag}", "--label", f"org.opencontainers.image.revision={sha}",
             "-t", admin_tag, str(root)], capture=False, timeout=1200)
    image_tags["tripilot-admin"] = admin_tag
    images = {}
    for repo, tag in image_tags.items():
        existing = subprocess.run(
            ["aws", "ecr", "describe-images", "--repository-name", repo,
             "--image-ids", f"imageTag=git-{sha}", "--output", "json"],
            capture_output=True, text=True, timeout=60)
        if existing.returncode:
            if "ImageNotFoundException" not in existing.stderr:
                raise DeploymentError("ECR lookup failed; refusing to overwrite an unknown image")
            command(["docker", "push", tag], capture=False, timeout=600)
        else:
            # Immutable ECR tags are reused only if their revision label is exact.
            pinned = registry_digest(registry, repo, sha)
            command(["docker", "pull", pinned], capture=False, timeout=300)
            label = command(["docker", "image", "inspect", pinned, "--format",
                             '{{ index .Config.Labels "org.opencontainers.image.revision" }}']).strip()
            if label != sha:
                raise DeploymentError("Existing immutable tag has another revision")
        images[repo] = registry_digest(registry, repo, sha)
    images["tripilot-worker"] = images["tripilot-api"]
    Path("aws-images.json").write_text(json.dumps(images), encoding="utf-8")
    print("Published three immutable images; runtime data preserved.")


def patch_for(document, image, sha):
    immutable_image(image)
    spec = copy.deepcopy(document["spec"]["template"])
    containers = spec["spec"]["containers"]
    if len(containers) != 1:
        raise DeploymentError("Expected one application container")
    containers[0]["image"] = image
    env = [x for x in containers[0].get("env", []) if x["name"] != "ACOP_DEPLOYMENT_VERSION"]
    env.append({"name": "ACOP_DEPLOYMENT_VERSION", "value": sha})
    containers[0]["env"] = env
    spec.setdefault("metadata", {}).setdefault("annotations", {})[REVISION] = sha
    return [{"op": "test", "path": "/metadata/resourceVersion", "value": document["metadata"]["resourceVersion"]},
            {"op": "replace", "path": "/spec/template", "value": spec}]


MIGRATION_SCRIPT = """\
import json
from pathlib import Path
import sys

result_path, lock_timeout, statement_timeout = sys.argv[1:4]


def record(document):
    Path(result_path).write_text(json.dumps(document), encoding="utf-8")


import psycopg
from app.infrastructure.db.migrate import apply_all, safety_manifest
from app.infrastructure.db.session import get_connection

safety_manifest()
applied = False
try:
    with get_connection() as conn:
        for name, value in (("lock_timeout", lock_timeout), ("statement_timeout", statement_timeout)):
            accepted = conn.execute("SELECT set_config(%s, %s, false)", (name, value)).fetchone()[0]
            shown = conn.execute("SELECT current_setting(%s)", (name,)).fetchone()[0]
            if shown != accepted or shown in ("0", "", None):
                raise RuntimeError(name + " was not applied")
        apply_all(conn)
        applied = True
except Exception as exc:
    failure = {"migration": "commit_unknown" if applied else "failed_before_commit", "error": type(exc).__name__}
    if isinstance(getattr(exc, "sqlstate", None), str):
        failure["sqlstate"] = exc.sqlstate
    record(failure)
    raise
record({"migration": "committed"})
print(json.dumps({"migration": "committed"}))
"""


def migration_job(baseline, image, sha, run_id):
    pod = copy.deepcopy(baseline["spec"]["template"]["spec"])
    if len(pod["containers"]) != 1:
        raise DeploymentError("Unexpected API sidecar")
    if seconds(MIGRATION_STATEMENT_TIMEOUT) >= MIGRATION_DEADLINE_SECONDS:
        raise DeploymentError("The migration statement bound must end before the Job deadline")
    c = pod["containers"][0]
    c["image"] = immutable_image(image)
    c["command"] = ["python", "-c", MIGRATION_SCRIPT, MIGRATION_RESULT_PATH,
                    MIGRATION_LOCK_TIMEOUT, MIGRATION_STATEMENT_TIMEOUT]
    c.pop("args", None)
    for key in ("readinessProbe", "livenessProbe", "startupProbe", "lifecycle", "ports"):
        c.pop(key, None)
    c["terminationMessagePath"] = MIGRATION_RESULT_PATH
    c["terminationMessagePolicy"] = "File"
    c["resources"] = {"requests": {"cpu": "100m", "memory": "128Mi"},
                      "limits": {"cpu": "500m", "memory": "768Mi"}}
    pod["restartPolicy"] = "Never"
    pod["automountServiceAccountToken"] = False
    name = f"guguroute-cd-migrate-{sha[:12]}-{run_id}"
    return {"apiVersion": "batch/v1", "kind": "Job",
            "metadata": {"name": name, "labels": {"app.kubernetes.io/managed-by": "guguroute-cd"}},
            "spec": {"backoffLimit": 0, "activeDeadlineSeconds": MIGRATION_DEADLINE_SECONDS,
                     "ttlSecondsAfterFinished": 86400,
                     "template": {"metadata": {"labels": {"app.kubernetes.io/managed-by": "guguroute-cd"}},
                                  "spec": pod}}}


def job_outcome(namespace, job_name):
    """Read the migration's own bounded termination record; never container logs."""
    pods = kubectl(namespace, "get", "pods", "-l", f"job-name={job_name}", "-o", "json")["items"]
    statuses = [s for p in pods for s in p.get("status", {}).get("containerStatuses", [])]
    if not statuses:
        return {"migration": "unknown", "reason": "no-pod"}
    terminated = statuses[-1].get("state", {}).get("terminated")
    if not terminated:
        return {"migration": "unknown", "reason": "not-terminated"}
    try:
        message = json.loads(terminated.get("message", ""))
    except ValueError:
        message = {}
    if not isinstance(message, dict):
        message = {}
    outcome = {"migration": message.get("migration") if message.get("migration") in MIGRATION_OUTCOMES else "unknown"}
    if re.fullmatch(r"[0-9A-Z]{5}", str(message.get("sqlstate", ""))):
        outcome["sqlstate"] = message["sqlstate"]
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", str(message.get("error", ""))):
        outcome["error"] = message["error"]
    if isinstance(terminated.get("exitCode"), int):
        outcome["exit_code"] = terminated["exitCode"]
    if re.fullmatch(r"[A-Za-z]{1,40}", str(terminated.get("reason", ""))):
        outcome["reason"] = terminated["reason"]
    return outcome


def describe_outcome(outcome):
    return ", ".join(f"{k}={outcome[k]}" for k in ("migration", "error", "sqlstate", "reason", "exit_code") if k in outcome)


def require_clean_jobs(jobs, outcomes=None):
    for job in jobs:
        if not job.get("status", {}).get("succeeded"):
            name = job.get("metadata", {}).get("name", "unnamed")
            state = "active" if job.get("status", {}).get("active") else "unknown"
            outcome = (outcomes or {}).get(name, {"migration": state})
            raise DeploymentError(f"A previous migration is failed or uncertain ({name}: {describe_outcome(outcome)}); "
                                  "inspect it before another deployment")


def check_database_backup(identifier):
    result = json_command(["aws", "rds", "describe-db-instances",
                           "--db-instance-identifier", identifier, "--output", "json"])
    db = result["DBInstances"][0]
    point = datetime.fromisoformat(db["LatestRestorableTime"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - point).total_seconds()
    if db["BackupRetentionPeriod"] < 7 or age > 1200 or db["DBInstanceStatus"] != "available":
        raise DeploymentError("A recent seven-day RDS recovery point is required")
    return point.isoformat()


def ready(document):
    status = document.get("status", {})
    desired = document["spec"].get("replicas", 1)
    return (status.get("observedGeneration", 0) >= document["metadata"]["generation"]
            and status.get("updatedReplicas", 0) == desired
            and status.get("availableReplicas", 0) == desired
            and status.get("replicas", 0) == desired)


def wait_for_rollout(namespace, name, timeout=420, interval=3):
    """Wait with the approved named GET permission, without listing deployments."""
    deadline = time.monotonic() + timeout
    while not ready(deployment(namespace, name)):
        if time.monotonic() >= deadline:
            raise DeploymentError(f"{name}: rollout timed out")
        time.sleep(interval)


def public_health(url):
    result = {}
    for path in ("/health", "/"):
        request = urllib.request.Request(url.rstrip("/") + path,
                                         headers={"User-Agent": "Guguroute-Deployment/1.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise DeploymentError("Public endpoint failed")
            if path == "/health" and json.load(response).get("status") != "ok":
                raise DeploymentError("Public API health failed")
            result[path] = response.status
    return result


def pause_worker(namespace, allowed_images):
    current = deployment(namespace, "tripilot-worker")
    if current["spec"]["template"]["spec"]["containers"][0]["image"] not in allowed_images:
        raise DeploymentError("Another operator changed the worker; refusing to pause it")
    patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": current["metadata"]["resourceVersion"]},
             {"op": "replace", "path": "/spec/replicas", "value": 0}]
    kubectl(namespace, "patch", "deployment", "tripilot-worker", "--type=json", "-p", json.dumps(patch), "-o", "json")
    selector = ",".join(f"{k}={v}" for k, v in current["spec"]["selector"]["matchLabels"].items())
    command(["kubectl", "-n", namespace, "wait", "--for=delete", "pods", "-l", selector, "--timeout=180s"],
            capture=False, timeout=200)


def verify(namespace, images, sha):
    result = {}
    for name in APPS:
        d = deployment(namespace, name)
        if not ready(d) or d["spec"]["template"]["metadata"].get("annotations", {}).get(REVISION) != sha:
            raise DeploymentError(f"{name}: rollout is not complete")
        selector = ",".join(f"{k}={v}" for k, v in d["spec"]["selector"]["matchLabels"].items())
        pods = kubectl(namespace, "get", "pods", "-l", selector, "-o", "json")["items"]
        live = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
        if len(live) != d["spec"].get("replicas", 1):
            raise DeploymentError(f"{name}: unexpected running pod count")
        for pod in live:
            if pod["metadata"].get("annotations", {}).get(REVISION) != sha:
                raise DeploymentError(f"{name}: another revision is running")
            statuses = pod.get("status", {}).get("containerStatuses", [])
            if len(statuses) != 1:
                raise DeploymentError(f"{name}: container status unavailable")
            status = statuses[0]
            if (not status.get("ready") or status.get("restartCount") != 0
                    or not status.get("imageID", "").endswith(images[name].split("@")[1])):
                raise DeploymentError(f"{name}: image digest, readiness or restarts differ")
        result[name] = {"digest": images[name].split("@")[1], "ready": True}
    return result


def failure_record(sha, stage, exc, timings, migration, recovery):
    """Sanitized failure facts: our own DeploymentError text, otherwise only the exception type."""
    error = f"DeploymentError: {exc}" if isinstance(exc, DeploymentError) else type(exc).__name__
    return {"sha": sha, "stage": stage, "error": error, "recovery": recovery, "migration": migration,
            "timings": timings, "failed_at": datetime.now(timezone.utc).isoformat()}


def deploy(sha, namespace, images, public_url, database, settle=30):
    timings = {}
    clock = {"stage": "preflight", "started": time.monotonic()}
    facts = {"migration": None, "recovery": "not-needed"}

    def enter(stage):
        now = time.monotonic()
        timings[clock["stage"]] = round(now - clock["started"], 3)
        clock.update(stage=stage, started=now)

    try:
        _deploy(sha, namespace, images, public_url, database, settle, enter, timings, facts)
    except BaseException as exc:
        if clock["stage"] not in timings:
            timings[clock["stage"]] = round(time.monotonic() - clock["started"], 3)
        record = failure_record(sha, clock["stage"], facts.get("cause", exc), timings, facts["migration"],
                                facts["recovery"])
        Path(FAILURE_FILE).write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record), file=sys.stderr)
        raise


def _deploy(sha, namespace, images, public_url, database, settle, enter, timings, facts):
    if not SHA_RE.fullmatch(sha):
        raise DeploymentError("Invalid revision")
    repo = os.environ["GITHUB_REPOSITORY"]
    if github(f"/repos/{repo}/branches/main")["commit"]["sha"] != sha:
        raise DeploymentError("Main moved; refusing a stale deployment")
    baselines = {name: deployment(namespace, name) for name in APPS}
    if not all(ready(d) for d in baselines.values()):
        raise DeploymentError("The current application baseline is not ready")
    for image in images.values():
        immutable_image(image)
    private = Path(os.environ.get("RUNNER_TEMP", ".")) / "guguroute-deploy"
    private.mkdir(exist_ok=True)
    path = private / f"baseline-{sha}-{os.environ.get('GITHUB_RUN_ID', 'manual')}.json"
    with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(baselines, stream)
    recovery_point = check_database_backup(database)
    prior = kubectl(namespace, "get", "jobs", "-l", "app.kubernetes.io/managed-by=guguroute-cd", "-o", "json")["items"]
    unfinished = [j["metadata"]["name"] for j in prior
                  if not j.get("status", {}).get("succeeded") and j.get("status", {}).get("failed")]
    require_clean_jobs(prior, {name: readable_outcome(namespace, name) for name in unfinished})
    enter("migration")
    job = migration_job(baselines["tripilot-api"], images["tripilot-api"], sha, os.environ["GITHUB_RUN_ID"])
    created = kubectl(namespace, "create", "-f", "-", "-o", "json", data=json.dumps(job))
    job_name = created["metadata"]["name"]
    deadline = time.monotonic() + MIGRATION_DEADLINE_SECONDS + 120
    while True:
        current = kubectl(namespace, "get", "job", job_name, "-o", "json")
        status = current.get("status", {})
        if status.get("succeeded"):
            facts["migration"] = {"migration": "committed"}
            break
        if status.get("failed") or time.monotonic() >= deadline:
            facts["migration"] = readable_outcome(namespace, job_name)
            raise DeploymentError(f"Migration failed or is uncertain ({describe_outcome(facts['migration'])}); "
                                  "application images were not changed")
        time.sleep(5)
    changed = ["tripilot-worker"]
    try:
        enter("worker-pause")
        # A single small node cannot fit two API pods plus the worker. Keep the
        # existing API serving while releasing only the worker's reserved memory.
        pause_worker(namespace, {baselines["tripilot-worker"]["spec"]["template"]["spec"]["containers"][0]["image"]})
        for name in APPS:
            enter(f"rollout:{name}")
            current = deployment(namespace, name)
            if current["spec"]["template"] != baselines[name]["spec"]["template"]:
                raise DeploymentError(f"{name}: configuration changed during publication")
            if name not in changed:
                changed.append(name)
            patch = patch_for(current, images[name], sha)
            if name == "tripilot-worker":
                patch.append({"op": "replace", "path": "/spec/replicas", "value": baselines[name]["spec"].get("replicas", 1)})
            kubectl(namespace, "patch", "deployment", name, "--type=json",
                    "-p", json.dumps(patch), "-o", "json")
            wait_for_rollout(namespace, name)
        enter("verify")
        result = verify(namespace, images, sha)
        health = public_health(public_url)
        time.sleep(settle)
        result = verify(namespace, images, sha)
        health = public_health(public_url)
        enter("done")
    except BaseException as exc:
        facts["cause"] = exc
        recovery_errors = []
        try:
            pause_worker(namespace, {images["tripilot-worker"], baselines["tripilot-worker"]["spec"]["template"]["spec"]["containers"][0]["image"]})
        except Exception:
            recovery_errors.append("worker-pause")
        for name in reversed(changed):
            try:
                current = deployment(namespace, name)
                current_image = current["spec"]["template"]["spec"]["containers"][0]["image"]
                if (current["spec"]["template"] == baselines[name]["spec"]["template"]
                        and current["spec"].get("replicas", 1) == baselines[name]["spec"].get("replicas", 1)):
                    continue
                if current_image not in {images[name], baselines[name]["spec"]["template"]["spec"]["containers"][0]["image"]}:
                    raise DeploymentError("Another deployment changed the image; manual recovery required")
                patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": current["metadata"]["resourceVersion"]},
                         {"op": "replace", "path": "/spec/template", "value": baselines[name]["spec"]["template"]},
                         {"op": "replace", "path": "/spec/replicas", "value": baselines[name]["spec"].get("replicas", 1)}]
                kubectl(namespace, "patch", "deployment", name, "--type=json", "-p", json.dumps(patch), "-o", "json")
                wait_for_rollout(namespace, name)
            except Exception:
                recovery_errors.append(name)
        if recovery_errors:
            facts["recovery"] = "failed:" + ",".join(recovery_errors)
            raise DeploymentError("Deployment and image recovery failed; operator action required") from None
        facts["recovery"] = "restored"
        raise DeploymentError("Deployment failed; previous application images restored; DB remains forward-only") from None
    document = {"sha": sha, "checked_at": datetime.now(timezone.utc).isoformat(),
                "database_recovery_point": recovery_point, "applications": result,
                "public_http": health, "migration_job": job_name, "timings": timings}
    Path("aws-deploy-result.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    print(json.dumps(document))


def readable_outcome(namespace, job_name):
    try:
        return job_outcome(namespace, job_name)
    except (DeploymentError, KeyError, ValueError):
        return {"migration": "unknown", "reason": "unreadable"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("gate", "publish", "deploy"))
    parser.add_argument("--sha", default="")
    parser.add_argument("--main-only", action="store_true",
                        help="gate: open once CI (main) passed (image publication), never past a failed check")
    args = parser.parse_args()
    try:
        if args.action == "gate":
            gate(main_only=args.main_only)
        elif args.action == "publish":
            publish(args.sha, os.environ["CD_NAMESPACE"], os.environ["CD_ECR_REGISTRY"])
        else:
            deploy(args.sha, os.environ["CD_NAMESPACE"],
                   json.loads(Path("aws-images.json").read_text("utf-8")),
                   os.environ["CD_PUBLIC_URL"], os.environ["CD_RDS_INSTANCE"])
    except (DeploymentError, urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"AWS deployment stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
