"""Bounded deployment with native-image checks and exact-image recovery.

Resolved snapshots contain secrets: store in private deployment state, never Git.
This helper executes no database SQL. Host Python uses only the standard library.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import tempfile
import signal
from uuid import uuid4

SERVICES = ("tripilot-api", "tripilot-worker", "tripilot-web")
PROBE = ("import json; from app.infrastructure.db.migrate import safety_manifest; "
         "print(json.dumps(safety_manifest(),sort_keys=True))")


class DeployError(RuntimeError):
    pass


class Docker:
    def run(self, args, timeout=60):
        try:
            result = subprocess.run(["docker", *args], text=True, capture_output=True,
                                    timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise DeployError(f"Docker command timed out after {timeout}s") from exc
        if result.returncode:
            # Docker stderr/config may contain credentials; do not echo it.
            raise DeployError(f"Docker command failed (exit {result.returncode})")
        return result.stdout


def compose(files=()):
    return ["compose", *[arg for file in files for arg in ("-f", str(file))]]


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects previous recovery material from overwrite.
    with open(path, "x", encoding="utf-8", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream, indent=2)


def compose_json(path, config):
    # Resolved environment values may contain literal $. Compose interpolates
    # files again, so escape values once for a faithful second parse.
    def literal(value):
        if isinstance(value, str):
            return value.replace("$", "$$")
        if isinstance(value, list):
            return [literal(v) for v in value]
        if isinstance(value, dict):
            return {k: literal(v) for k, v in value.items()}
        return value
    private_json(path, literal(config))


def inspect_service(docker, command, service, timeout=60):
    ids = docker.run([*command, "ps", "-a", "-q", service], timeout=timeout).split()
    if len(ids) != 1:
        raise DeployError(f"{service}: expected one container, found {len(ids)}")
    return json.loads(docker.run(["inspect", ids[0]], timeout=timeout))[0]


def healthy(info):
    state = info["State"]
    return (state["Status"] == "running"
            and state.get("Health", {}).get("Status", "healthy") == "healthy")


def snapshot(docker, command, directory):
    directory = Path(directory)
    if (directory / "recovery.compose.json").exists() or (directory / "baseline.json").exists():
        raise FileExistsError("Recovery snapshot already exists; use a new state directory")
    config = json.loads(docker.run([*command, "config", "--format", "json"]))
    records = {}
    infos = {service: inspect_service(docker, command, service) for service in SERVICES}
    # The live container may have been started with an immutable ID, while the
    # source Compose still names a tag. Reconstruct its declared image before
    # comparing config hashes; otherwise the next safe deployment rejects itself.
    for service, info in infos.items():
        config["services"][service]["image"] = info["Config"]["Image"]
        # The tag-sync job updates display metadata after rollout, without
        # recreating containers. Recover only that metadata from the live
        # baseline; every other setting must still pass the strict hash check.
        environment = config["services"][service].get("environment") or {}
        live_environment = dict(value.split("=", 1) for value in
                                (info["Config"].get("Env") or []) if "=" in value)
        if "TRIPILOT_TAG" in environment and "TRIPILOT_TAG" in live_environment:
            environment["TRIPILOT_TAG"] = live_environment["TRIPILOT_TAG"]
    with tempfile.TemporaryDirectory(prefix="tripilot-baseline-") as temporary:
        config_path = Path(temporary) / "baseline.compose.json"
        compose_json(config_path, config)
        hashes = {}
        # Compose accepts one service for --hash on deployed versions. Passing
        # several names can silently return only the first service's hash.
        for service in SERVICES:
            rows = [line.split() for line in docker.run(
                [*compose([config_path]), "config", "--hash", service]).splitlines()]
            if len(rows) != 1 or len(rows[0]) != 2 or rows[0][0] != service:
                raise DeployError(f"{service}: invalid Compose configuration hash response")
            hashes[service] = rows[0][1]
    for service in SERVICES:
        info = infos[service]
        if not healthy(info):
            raise DeployError(f"{service}: baseline is not stable")
        labels = info["Config"].get("Labels") or {}
        if labels.get("com.docker.compose.config-hash") != hashes.get(service):
            raise DeployError(f"{service}: Compose configuration drift; reconcile before deployment")
        image = info["Image"]
        docker.run(["image", "inspect", image])
        records[service] = {"image": image, "restarts": info["RestartCount"], "container": info["Id"]}
        config["services"][service]["image"] = image
        config["services"][service].pop("build", None)
    # A separate repository name keeps ordinary app-tag retention from deleting
    # the exact recovery image. Expired tags (and their state directories) are
    # removed by deploy/image_retention.py at the end of each successful deployment.
    token = uuid4().hex
    for service, record in records.items():
        record["recovery_tag"] = "tripilot-recovery:" + token + "-" + service
        docker.run(["tag", record["image"], record["recovery_tag"]])
    compose_json(directory / "recovery.compose.json", config)
    private_json(directory / "baseline.json", records)
    return records


def image_check(docker, command):
    config = json.loads(docker.run([*command, "config", "--format", "json"]))
    manifests, images = {}, {}
    for service in SERVICES:
        image = config["services"][service]["image"]
        images[service] = json.loads(docker.run(["image", "inspect", image]))[0]["Id"]
        if service == "tripilot-web":
            continue
        native = json.loads(docker.run(["run", "--rm", "--network", "none", "--entrypoint",
                                        "python", images[service], "-c", PROBE]))
        if native.get("contract_version") != 2 or len(native.get("historical", [])) != 4:
            raise DeployError(f"{service}: native image lacks migration safety contract")
        runtime = json.loads(docker.run([*command, "run", "--rm", "--no-deps", "--entrypoint",
                                         "python", service, "-c", PROBE]))
        if runtime != native:
            raise DeployError(f"{service}: Compose overrides native migration artifacts")
        manifests[service] = native
    return images, manifests


def prepare_candidate(directory, api_image):
    """Create a reviewable candidate from the private recovery configuration."""
    directory = Path(directory)
    baseline = json.loads((directory / "baseline.json").read_text(encoding="utf-8"))
    if baseline["tripilot-api"]["image"] != baseline["tripilot-worker"]["image"]:
        raise DeployError("API and worker have different base images; prepare separate reviewed candidates")
    # Already escaped for Compose; do not escape literal dollars a second time.
    config = json.loads((directory / "recovery.compose.json").read_text(encoding="utf-8"))
    targets = {"/srv/app/infrastructure/db/migrate.py", "/srv/app/infrastructure/db/migration_plan.py",
               "/srv/app/infrastructure/db/migration_sql.py",
               "/srv/app/infrastructure/db/migrations/migration-plan.json"}
    for service in ("tripilot-api", "tripilot-worker"):
        entry = config["services"][service]
        entry["image"] = api_image
        mounts = entry.get("volumes", [])
        if any(not isinstance(mount, dict) for mount in mounts):
            raise DeployError("Candidate requires a resolved Compose configuration")
        entry["volumes"] = [mount for mount in mounts if mount.get("target") not in targets]
    path = directory / "candidate.plan.json"
    private_json(path, config)
    return path


def wait_stable(docker, command, expected, settle, timeout):
    deadline = time.monotonic() + timeout
    initial = {}
    while True:
        if not healthy(inspect_service(docker, command, "tripilot-db", timeout=30)):
            raise DeployError("tripilot-db: health check failed")
        for service in SERVICES:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeployError("Stability observation timed out")
            info = inspect_service(docker, command, service, timeout=min(30, remaining / 2))
            if not healthy(info) or info["Image"] != expected[service]:
                raise DeployError(f"{service}: health or image mismatch")
            current = (info["Id"], info["RestartCount"])
            if service in initial and current != initial[service]:
                raise DeployError(f"{service}: restarted or recreated during observation")
            initial[service] = current
        if settle <= 0:
            return
        delay = min(2, settle)
        time.sleep(delay)
        settle -= delay


def recover(docker, directory, timeout=300, settle=30):
    directory = Path(directory)
    baseline = json.loads((directory / "baseline.json").read_text(encoding="utf-8"))
    expected = {service: baseline[service]["image"] for service in SERVICES}
    command = compose([directory / "recovery.compose.json"])
    docker.run([*command, "up", "-d", "--no-deps", "--no-build", "--pull", "never",
                "--wait", "--wait-timeout", str(max(1, timeout - 30)), *SERVICES], timeout=timeout)
    wait_stable(docker, command, expected, settle, timeout)


def rollout(docker, command, directory, timeout=300, settle=30):
    # Verify recovery material before the first mutation.
    directory = Path(directory)
    baseline = json.loads((directory / "baseline.json").read_text(encoding="utf-8"))
    if set(baseline) != set(SERVICES) or not (directory / "recovery.compose.json").is_file():
        raise DeployError("Incomplete recovery snapshot")
    images, _ = image_check(docker, command)
    # Resolve all automatic overrides before using an explicit file list.
    resolved = json.loads(docker.run([*command, "config", "--format", "json"]))
    for service in SERVICES:
        resolved["services"][service]["image"] = images[service]
        resolved["services"][service].pop("build", None)
    resolved_path = directory / "candidate.compose.json"
    compose_json(resolved_path, resolved)
    pinned = compose([resolved_path])
    try:
        docker.run([*pinned, "up", "-d", "--no-deps", "--no-build", "--pull", "never",
                    "--wait", "--wait-timeout", str(max(1, timeout - 30)), *SERVICES], timeout=timeout)
        wait_stable(docker, pinned, images, settle, timeout)
    except (DeployError, KeyboardInterrupt) as original:
        try:
            recover(docker, directory, timeout, settle)
        except (DeployError, KeyboardInterrupt) as recovery:
            raise DeployError("Rollout failed; exact-image recovery also failed; manual action required") from recovery
        raise DeployError("Rollout failed; exact-image recovery verified") from original
    return images


def migrate(docker, command, timeout=180):
    """Bound the one-shot job; do not retry an uncertain database result."""
    images, _ = image_check(docker, command)
    resolved = json.loads(docker.run([*command, "config", "--format", "json"]))
    resolved["services"]["tripilot-api"]["image"] = images["tripilot-api"]
    resolved["services"]["tripilot-api"].pop("build", None)
    name = "tripilot-migration-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="tripilot-migration-") as temporary:
        path = Path(temporary) / "migration.compose.json"
        compose_json(path, resolved)
        try:
            docker.run([*compose([path]), "run", "--rm", "--no-deps", "--pull", "never", "--name", name,
                        "tripilot-api", "python", "-m", "app.infrastructure.db.migrate"], timeout=timeout)
        except (DeployError, KeyboardInterrupt) as original:
            # Killing the CLI alone does not stop its Docker-side job.
            try:
                ids = docker.run(["ps", "-a", "-q", "--filter", "name=^/" + name + "$"]).split()
                if ids:
                    docker.run(["rm", "-f", *ids], timeout=30)
            except DeployError as cleanup:
                raise DeployError("Migration failed; job cleanup unconfirmed; no automatic retry") from cleanup
            raise DeployError("Migration failed; job stopped; DB result must be checked before retry") from original


def main():
    def interrupted(signum, frame):
        raise DeployError("Deployment interrupted; recover if rollout has started")
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "prepare", "check", "migrate", "rollout", "recover"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("-f", "--file", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--settle", type=int, default=30)
    parser.add_argument("--api-image")
    args = parser.parse_args()
    if args.timeout < 1 or args.settle < 0:
        parser.error("timeout must be positive and settle nonnegative")
    docker, command = Docker(), compose(args.file)
    try:
        if args.action == "snapshot":
            snapshot(docker, command, args.state_dir)
        elif args.action == "prepare":
            if not args.api_image or not args.api_image.startswith("sha256:"):
                raise DeployError("prepare requires an immutable --api-image sha256 ID")
            prepare_candidate(args.state_dir, args.api_image)
        elif args.action == "check":
            image_check(docker, command)
        elif args.action == "rollout":
            rollout(docker, command, args.state_dir, args.timeout, args.settle)
        elif args.action == "migrate":
            migrate(docker, command, args.timeout)
        else:
            recover(docker, args.state_dir, args.timeout, args.settle)
    except (DeployError, ValueError, KeyError, OSError) as exc:
        print(f"Deployment safety check failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
    print(f"Deployment safety {args.action}: passed")


if __name__ == "__main__":
    main()
