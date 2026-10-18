"""실제 Bash와 로컬 자식으로 작업 실행기의 종료·회수 경계를 검증한다."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / "deploy/worker.sh"
JOBS = ["scripts.replay_operations_diagnostics", "scripts.run_sweepers", "scripts.run_outbox_worker"]
DAILY = "scripts.run_daily_feedback"


def _bash():
    candidates = [os.environ.get("WORKER_TEST_BASH"), shutil.which("bash")]
    if os.name == "nt":
        candidates = [os.environ.get("WORKER_TEST_BASH"), r"C:/Program Files/Git/usr/bin/bash.exe"]
    for name in candidates:
        if name and Path(name).is_file():
            return str(Path(name).resolve())
    pytest.skip("actual local Bash is unavailable; Linux/PID1 verification is not substituted")


def _shell_path(path):
    value = Path(path).resolve().as_posix()
    return f"/{value[0].lower()}{value[2:]}" if os.name == "nt" else value


def _until(condition, label, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError("worker barrier timed out: " + label)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    path.chmod(0o755)


class WorkerProcess:
    def __init__(self, directory, **settings):
        self.root = directory
        self.root.mkdir(parents=True)
        self.bash = _bash()
        self.journal = directory / "journal"
        self.mark = directory / "daily.mark"
        if settings.pop("mark_is_directory", False):
            self.mark.mkdir()
        script = WORKER.read_text(encoding="utf-8")
        old = "DAILY_MARK=/srv/var/ops/daily_feedback.last"
        assert script.count(old) == 1
        # The hardcoded container volume does not exist on this PC. Only its test-copy path changes.
        script = script.replace(old, 'DAILY_MARK="$WORKER_TEST_ROOT/daily.mark"')
        _write(directory / "worker-under-test.sh", script)
        _write(directory / "bin/python", '''#!/bin/sh
job=$2
printf 'START %s %s\n' "$job" "$$" >> "$WORKER_TEST_ROOT/journal"
trap 'printf "SIGNALLED %s %s\\n" "$job" "$$" >> "$WORKER_TEST_ROOT/journal"; exit 97' TERM INT
if [ "$job" = "${WORKER_TEST_BLOCK_JOB:-}" ]; then
  while [ ! -f "$WORKER_TEST_ROOT/release" ]; do /usr/bin/sleep 0.01; done
fi
rc=0
if [ "$job" = "${WORKER_TEST_FAIL_JOB:-}" ]; then
  if [ "${WORKER_TEST_FAIL_ONCE:-0}" != 1 ] || [ ! -f "$WORKER_TEST_ROOT/failed-once" ]; then
    : > "$WORKER_TEST_ROOT/failed-once"
    rc=${WORKER_TEST_FAIL_CODE:-7}
  fi
fi
printf 'END %s %s %s\n' "$job" "$$" "$rc" >> "$WORKER_TEST_ROOT/journal"
if [ "$job" = "${WORKER_TEST_SIGNAL_AT_END:-}" ]; then
  kill -TERM "$(cat "$WORKER_TEST_ROOT/worker.pid")"
fi
exit "$rc"
''')
        _write(directory / "bin/date", '''#!/bin/sh
case "$1" in
  +%F) printf '2026-10-18\n' ;;
  +%H%M) printf '%s\n' "${WORKER_TEST_NOW:-0000}" ;;
  -Iseconds) printf '2026-10-18T10:00:00+09:00\n' ;;
  *) exec /usr/bin/date "$@" ;;
esac
''')
        _write(directory / "bin/sleep", '''#!/bin/sh
printf 'SLEEP %s\n' "$$" >> "$WORKER_TEST_ROOT/journal"
if [ "${WORKER_TEST_SLEEP_FAIL:-0}" != 0 ]; then exit "$WORKER_TEST_SLEEP_FAIL"; fi
if [ "${WORKER_TEST_FAST_FIRST_SLEEP:-0}" = 1 ] && [ ! -f "$WORKER_TEST_ROOT/slept-once" ]; then
  : > "$WORKER_TEST_ROOT/slept-once"
  exec /usr/bin/sleep 0.01
fi
exec /usr/bin/sleep "$@"
''')
        _write(directory / "launch.sh", '''#!/bin/sh
PATH="$WORKER_TEST_ROOT/bin:/usr/bin:/bin"
export PATH
printf '%s\n' "$$" > "$WORKER_TEST_ROOT/worker.pid"
exec /usr/bin/bash --noprofile --norc --posix "$WORKER_TEST_ROOT/worker-under-test.sh"
''')
        env = {**os.environ, "WORKER_TEST_ROOT": _shell_path(directory)}
        env.update({"WORKER_TEST_" + key.upper(): str(value) for key, value in settings.items()})
        self.stdout = (directory / "stdout.log").open("xb")
        self.stderr = (directory / "stderr.log").open("xb")
        self.process = subprocess.Popen([self.bash, "--noprofile", "--norc", "--posix",
            _shell_path(directory / "launch.sh")], env=env, stdout=self.stdout, stderr=self.stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        _until(lambda: (directory / "worker.pid").is_file(), "worker pid")
        self.pid = int((directory / "worker.pid").read_text().strip())

    def events(self):
        return [line.split() for line in self.journal.read_text().splitlines()] if self.journal.exists() else []

    def command(self, *args):
        return subprocess.run([self.bash, "--noprofile", "--norc", "-c",
            'PATH=/usr/bin:/bin; export PATH; kill "$@"', "worker-test", *map(str, args)],
            capture_output=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

    def signal(self, name, pid=None):
        pid = self.pid if pid is None else pid
        assert pid > 1
        known = {self.pid, *self.child_pids()}
        assert pid in known
        assert self.command("-s", name, pid).returncode == 0

    def alive(self, pid):
        return self.command("-0", pid).returncode == 0

    def child_pids(self):
        return {int(row[2]) if row[0] == "START" else int(row[1]) for row in self.events()
                if row[0] in {"START", "SLEEP"}}

    def started(self, job, count=1):
        return sum(row[:2] == ["START", job] for row in self.events()) >= count

    def wait_started(self, job, count=1):
        _until(lambda: self.started(job, count), job)

    def wait_sleep(self, count=1):
        _until(lambda: sum(row[0] == "SLEEP" for row in self.events()) >= count, "idle sleep")
        return int([row for row in self.events() if row[0] == "SLEEP"][-1][1])

    def release(self):
        (self.root / "release").touch()

    def finish(self, expected):
        code = self.process.wait(timeout=6)
        self.stdout.flush()
        self.stderr.flush()
        assert code == expected, (code, self.events(), (self.root / "stderr.log").read_text())
        for pid in self.child_pids():
            _until(lambda: not self.alive(pid), f"child {pid} reaped")
        assert not any(row[0] == "SIGNALLED" for row in self.events())
        return self.events()

    def cleanup(self):
        self.release()
        if self.process.poll() is None:
            self.command("-s", "TERM", self.pid)
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Only this test's owned native parent handle.
                self.process.wait(timeout=3)
        for pid in self.child_pids():
            if self.alive(pid):
                self.command("-s", "TERM", pid)
                _until(lambda: not self.alive(pid), f"test cleanup child {pid}")
        self.stdout.close()
        self.stderr.close()


@pytest.fixture
def worker_factory(tmp_path):
    processes = []
    proof = os.environ.get("WORKER_SHUTDOWN_PROOF_ROOT")
    root = Path(proof) / uuid4().hex if proof else tmp_path

    def create(**kwargs):
        process = WorkerProcess(root / str(len(processes)), **kwargs)
        processes.append(process)
        return process

    yield create
    for process in processes:
        process.cleanup()


@pytest.mark.parametrize("signal_name", ["TERM", "INT"])
@pytest.mark.parametrize("job", [JOBS[0], JOBS[-1]])
def test_signal_drains_current_job_without_starting_the_next(worker_factory, signal_name, job):
    process = worker_factory(block_job=job)
    process.wait_started(job)
    process.signal(signal_name)
    assert process.process.poll() is None
    process.release()
    events = process.finish(0)
    assert [row[1] for row in events if row[0] == "START"] == JOBS[:JOBS.index(job) + 1]
    assert sum(row[:2] == ["END", job] for row in events) == 1
    assert not any(row[0] == "SLEEP" for row in events)


@pytest.mark.parametrize("signal_name", ["TERM", "INT"])
def test_idle_signal_cancels_and_reaps_sleep(worker_factory, signal_name):
    process = worker_factory()
    pid = process.wait_sleep()
    assert process.alive(pid)
    process.signal(signal_name)
    events = process.finish(0)
    assert [row[1] for row in events if row[0] == "START"] == JOBS
    assert not process.alive(pid)


def test_failure_is_logged_and_returned_after_current_job_drains(worker_factory):
    process = worker_factory(block_job=JOBS[0], fail_job=JOBS[0], fail_code=7)
    process.wait_started(JOBS[0])
    process.signal("TERM")
    process.release()
    events = process.finish(7)
    errors = [json.loads(line) for line in (process.root / "stderr.log").read_text().splitlines()
              if line.startswith("{")]
    assert sum(item.get("job") == "diagnostics" and item.get("exit") == 7 for item in errors) == 1
    assert [row[1] for row in events if row[0] == "START"] == [JOBS[0]]


def test_failed_job_keeps_running_the_round_and_retries_on_the_next_round(worker_factory):
    process = worker_factory(fail_job=JOBS[0], fail_once=1, fast_first_sleep=1)
    process.wait_sleep(2)
    process.signal("TERM")
    events = process.finish(0)
    assert [row[1] for row in events if row[0] == "START"] == JOBS * 2
    assert [row[-1] for row in events if row[:2] == ["END", JOBS[0]]] == ["7", "0"]
    assert '"exit":7' in (process.root / "stderr.log").read_text()


@pytest.mark.parametrize("exit_code", [0, 9])
def test_daily_completion_marker_matches_the_drained_job(worker_factory, exit_code):
    process = worker_factory(block_job=DAILY, now="1000", fail_job=DAILY, fail_code=exit_code)
    process.wait_started(DAILY)
    process.signal("TERM")
    process.release()
    events = process.finish(exit_code)
    assert [row[1] for row in events if row[0] == "START"] == [*JOBS, DAILY]
    assert process.mark.exists() is (exit_code == 0)
    if exit_code == 0:
        assert process.mark.read_text().strip() == "2026-10-18"


def test_daily_marker_write_failure_is_not_a_success(worker_factory):
    process = worker_factory(now="1000", mark_is_directory=True)
    # Redirection failures are shell-specific (for example Bash 1, dash 2).
    # Compare exact propagation with an independent command in the same shell.
    reference = subprocess.run([process.bash, "-c", 'printf "%s\\n" "2026-10-18" > "$1"',
        "worker-marker-reference", _shell_path(process.mark)], capture_output=True, timeout=3,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert reference.returncode > 0
    process.wait_sleep()
    process.signal("TERM")
    events = process.finish(reference.returncode)
    errors = [json.loads(line) for line in (process.root / "stderr.log").read_text().splitlines()
              if line.startswith("{")]
    marker_errors = [item for item in errors if item.get("job") == "daily_feedback_mark"]
    assert len(marker_errors) == 1 and marker_errors[0]["exit"] == reference.returncode
    assert [row[1] for row in events if row[0] == "START"] == [*JOBS, DAILY]
    assert process.mark.is_dir()


def test_unexpected_sleep_failure_is_logged_and_propagated(worker_factory):
    process = worker_factory(sleep_fail=23)
    process.finish(23)
    assert '"job":"idle_wait","exit":23' in (process.root / "stderr.log").read_text()


def test_repeated_stop_signals_do_not_interrupt_the_active_job(worker_factory):
    process = worker_factory(block_job=JOBS[0])
    process.wait_started(JOBS[0])
    process.signal("TERM")
    process.signal("INT")
    process.signal("TERM")
    process.release()
    events = process.finish(0)
    assert [row[1] for row in events if row[0] == "START"] == [JOBS[0]]


def test_stop_at_job_completion_does_not_start_another_job(worker_factory):
    process = worker_factory(signal_at_end=JOBS[0])
    events = process.finish(0)
    assert [row[1] for row in events if row[0] == "START"] == [JOBS[0]]
