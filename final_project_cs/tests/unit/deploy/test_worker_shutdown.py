"""실제 Bash와 로컬 자식으로 작업 실행기의 종료·회수 경계를 검증한다.

`[2026-10-19]` 배달(바깥함 일꾼)은 되잡기 회차와 따로 도는 반복이다 — 되잡기 회차의 작업 순서(`JOBS`)에서 빠지고
배달 작업(`DELIVERY`)은 따로 센다. 같은 시험을 Bash(POSIX 모드)와 dash(컨테이너의 /bin/sh) 둘에서 돌린다.
"""
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
JOBS = ["scripts.replay_operations_diagnostics", "scripts.run_sweepers"]
DELIVERY = "scripts.run_outbox_worker"
DAILY = "scripts.run_daily_feedback"
SHELLS = {"bash": "/usr/bin/bash --noprofile --norc --posix", "dash": "/usr/bin/dash"}
DASH = Path("C:/Program Files/Git/usr/bin/dash.exe" if os.name == "nt" else "/usr/bin/dash")


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


# Git Bash 에서 프로세스 시작이 느려 다른 시험이 함께 돌면 6초를 넘긴 적이 있다(2026-10-19, 240건 중 3건) — 10초로 둔다.
def _until(condition, label, timeout=10):
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


def _main_starts(events):
    """되잡기 회차가 띄운 작업 순서 — 따로 도는 배달 작업은 뺀다."""
    return [row[1] for row in events if row[0] == "START" and row[1] != DELIVERY]


def _count(events, kind, job=DELIVERY):
    return sum(row[:2] == [kind, job] for row in events)


class WorkerProcess:
    def __init__(self, directory, shell, **settings):
        self.root = directory
        self.root.mkdir(parents=True)
        self.shell = shell
        self.bash = _bash()
        self.journal = directory / "journal"
        self.mark = directory / "daily.mark"
        if settings.pop("mark_is_directory", False):
            self.mark.mkdir()
        delivery_sleep = settings.pop("delivery_sleep", None)
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
if [ "$job" = "${WORKER_TEST_STOP_PARENT_JOB:-}" ] && [ ! -f "$WORKER_TEST_ROOT/stopped-parent" ]; then
  : > "$WORKER_TEST_ROOT/stopped-parent"
  printf 'STOP_PARENT %s\n' "$PPID" >> "$WORKER_TEST_ROOT/journal"
  kill -TERM "$PPID"
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
        # The idle wait between rounds is `sleep 60`; the delivery loop's wait is any other length.
        # ☆Git Bash(MSYS) loses a signal that arrives while a process is in the middle of `exec` (a Linux process keeps it
        #   pending across exec). The worker stops a sleep right after starting it, so this stand-in does not exec:
        #   it runs the real sleep as its own child and ends it on TERM.
        _write(directory / "bin/sleep", '''#!/bin/sh
nap_pid=
trap '[ -z "$nap_pid" ] || kill -TERM "$nap_pid" 2>/dev/null; exit 143' TERM
printf 'SLEEP %s %s %s\n' "$$" "$1" "$PPID" >> "$WORKER_TEST_ROOT/journal"
if [ "$1" = 60 ] && [ "${WORKER_TEST_SLEEP_FAIL:-0}" != 0 ]; then exit "$WORKER_TEST_SLEEP_FAIL"; fi
if [ "$1" != 60 ] && [ "${WORKER_TEST_DELIVERY_SLEEP_FAIL:-0}" != 0 ] && [ ! -f "$WORKER_TEST_ROOT/delivery-slept-badly" ]; then
  : > "$WORKER_TEST_ROOT/delivery-slept-badly"
  exit "$WORKER_TEST_DELIVERY_SLEEP_FAIL"
fi
if [ "$1" = 60 ] && [ "${WORKER_TEST_FAST_FIRST_SLEEP:-0}" = 1 ] && [ ! -f "$WORKER_TEST_ROOT/slept-once" ]; then
  : > "$WORKER_TEST_ROOT/slept-once"
  set -- 0.01
fi
/usr/bin/sleep "$@" &
nap_pid=$!
wait "$nap_pid"
''')
        _write(directory / "launch.sh", f'''#!/bin/sh
PATH="$WORKER_TEST_ROOT/bin:/usr/bin:/bin"
export PATH
printf '%s\\n' "$$" > "$WORKER_TEST_ROOT/worker.pid"
exec {SHELLS[shell]} "$WORKER_TEST_ROOT/worker-under-test.sh"
''')
        env = {**os.environ, "WORKER_TEST_ROOT": _shell_path(directory)}
        env.pop("WORKER_DELIVERY_SLEEP", None)
        if delivery_sleep is not None:
            env["WORKER_DELIVERY_SLEEP"] = str(delivery_sleep)
        env.update({"WORKER_TEST_" + key.upper(): str(value) for key, value in settings.items()})
        self.stdout = (directory / "stdout.log").open("xb")
        self.stderr = (directory / "stderr.log").open("xb")
        self.process = subprocess.Popen([self.bash, "--noprofile", "--norc", "--posix",
            _shell_path(directory / "launch.sh")], env=env, stdout=self.stdout, stderr=self.stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        # ★`[2026-10-23]` `printf … > worker.pid` makes the file before it writes the number: wait for the whole line, not the file.
        #   Read in between, it was '' and `int` failed (main CI 39901758724 — passed on the same tree's PR run).
        def written():
            pid = directory / "worker.pid"
            text = pid.read_text() if pid.is_file() else ""
            return text.strip() if text.endswith("\n") else ""
        self.pid = int(_until(written, "worker pid"))

    def events(self):
        return [line.split() for line in self.journal.read_text().splitlines()] if self.journal.exists() else []

    def note(self, text):
        """시험이 보낸 신호의 시점을 기록에 남긴다(그 뒤에 시작한 작업을 셀 수 있게)."""
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")

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
        self.note(f"SIGNAL {name}")
        assert self.command("-s", name, pid).returncode == 0

    def alive(self, pid):
        return self.command("-0", pid).returncode == 0

    def child_pids(self):
        return {int(row[2]) if row[0] == "START" else int(row[1]) for row in self.events()
                if row[0] in {"START", "SLEEP"}}

    def started(self, job, count=1):
        return _count(self.events(), "START", job) >= count

    def wait_started(self, job, count=1):
        _until(lambda: self.started(job, count), job)

    def wait_sleep(self, count=1):
        """되잡기 회차 사이의 60초 대기를 기다린다(배달 반복의 대기는 세지 않는다)."""
        def idle():
            return [row for row in self.events() if row[0] == "SLEEP" and row[2] == "60"]
        _until(lambda: len(idle()) >= count, "idle sleep")
        return int(idle()[-1][1])

    def release(self):
        (self.root / "release").touch()

    def finish(self, expected):
        code = self.process.wait(timeout=10)
        self.stdout.flush()
        self.stderr.flush()
        assert code == expected, (code, self.events(), (self.root / "stderr.log").read_text())
        for pid in self.child_pids():
            _until(lambda: not self.alive(pid), f"child {pid} reaped")
        events = self.events()
        assert not any(row[0] == "SIGNALLED" for row in events)
        # 시작한 배달은 모두 끝까지 갔다(신호로 끊기지 않았다).
        assert _count(events, "START") == _count(events, "END")
        return events

    def errors(self):
        return [json.loads(line) for line in (self.root / "stderr.log").read_text().splitlines()
                if line.startswith("{")]

    def cleanup(self):
        self.release()
        if self.process.poll() is None:
            self.command("-s", "TERM", self.pid)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()  # Only this test's owned native parent handle.
                self.process.wait(timeout=3)
        for pid in self.child_pids():
            if self.alive(pid):
                self.command("-s", "TERM", pid)
                _until(lambda: not self.alive(pid), f"test cleanup child {pid}")
        self.stdout.close()
        self.stderr.close()


def _after_signal(events):
    """시험이 첫 신호를 보낸 뒤의 기록."""
    marks = [i for i, row in enumerate(events) if row[0] == "SIGNAL"]
    return events[marks[0] + 1:] if marks else []


@pytest.fixture(params=sorted(SHELLS))
def worker_factory(tmp_path, request):
    shell = request.param
    if shell == "dash" and not DASH.is_file():
        pytest.skip("dash is unavailable on this machine")
    processes = []
    proof = os.environ.get("WORKER_SHUTDOWN_PROOF_ROOT")
    root = Path(proof) / uuid4().hex if proof else tmp_path

    def create(**kwargs):
        process = WorkerProcess(root / str(len(processes)), shell, **kwargs)
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
    assert _main_starts(events) == JOBS[:JOBS.index(job) + 1]
    assert sum(row[:2] == ["END", job] for row in events) == 1
    assert not any(row[0] == "SLEEP" and row[2] == "60" for row in events)
    assert _count(_after_signal(events), "START") <= 1


@pytest.mark.parametrize("signal_name", ["TERM", "INT"])
def test_signal_during_delivery_drains_it_and_stops_the_round(worker_factory, signal_name):
    process = worker_factory(block_job=DELIVERY)
    process.wait_started(DELIVERY)
    process.wait_sleep()
    process.signal(signal_name)
    time.sleep(.2)
    assert process.process.poll() is None  # 진행 중인 발송이 끝날 때까지 기다린다
    process.release()
    events = process.finish(0)
    assert _main_starts(events) == JOBS
    assert _count(events, "START") == 1 and _count(events, "END") == 1


@pytest.mark.parametrize("signal_name", ["TERM", "INT"])
def test_idle_signal_cancels_and_reaps_sleep(worker_factory, signal_name):
    process = worker_factory()
    pid = process.wait_sleep()
    assert process.alive(pid)
    process.signal(signal_name)
    events = process.finish(0)
    assert _main_starts(events) == JOBS
    assert _count(events, "START") >= 1
    assert not process.alive(pid)


def test_delivery_keeps_running_while_a_long_round_job_runs(worker_factory):
    # 대안 계산(되잡기)이 오래 걸려도 배달은 기다리지 않는다.
    process = worker_factory(block_job=JOBS[-1], delivery_sleep="0.05")
    process.wait_started(JOBS[-1])
    process.wait_started(DELIVERY, 3)
    assert _count(process.events(), "END", JOBS[-1]) == 0
    process.signal("TERM")
    process.release()
    events = process.finish(0)
    assert _main_starts(events) == JOBS
    assert _count(_after_signal(events), "START") <= 1  # 신호 뒤 새 발송은 띄우지 않는다(이미 띄우던 하나만)


def test_delivery_failure_is_logged_and_retried_without_changing_the_exit(worker_factory):
    process = worker_factory(fail_job=DELIVERY, fail_once=1, delivery_sleep="0.05")
    process.wait_started(DELIVERY, 2)
    process.signal("TERM")
    events = process.finish(0)
    codes = [row[-1] for row in events if row[:2] == ["END", DELIVERY]]
    assert codes[0] == "7" and "0" in codes[1:]
    assert sum(item.get("job") == "outbox" and item.get("exit") == 7 for item in process.errors()) == 1


def _delivery_loop_ended(process, marker):
    """배달 반복(서브셸)이 실제로 끝날 때까지 기다린다 — 기록에 남은 그 서브셸 번호로 본다."""
    row = _until(lambda: next((r for r in process.events() if r[0] == marker[0] and (len(marker) < 2 or r[2] != "60")), None), marker[0])
    loop = int(row[1] if marker[0] == "STOP_PARENT" else row[3])
    _until(lambda: not process.alive(loop), "delivery loop ended")


def test_stopped_delivery_loop_is_logged_and_restarted_on_the_next_round(worker_factory):
    # 배달 반복만 혼자 멈추면(여기서는 반복에 직접 TERM) 다음 회차가 기록하고 다시 띄운다.
    process = worker_factory(stop_parent_job=DELIVERY, block_job=JOBS[-1], fast_first_sleep=1, delivery_sleep="0.05")
    process.wait_started(JOBS[-1])
    _delivery_loop_ended(process, ("STOP_PARENT",))
    starts = _count(process.events(), "START")
    process.release()
    process.wait_sleep(2)
    process.wait_started(DELIVERY, starts + 1)
    process.signal("TERM")
    events = process.finish(0)
    assert _main_starts(events) == JOBS * 2
    assert [item.get("exit") for item in process.errors() if item.get("job") == "delivery_loop"] == [0]


def test_delivery_wait_failure_ends_the_loop_and_the_next_round_restarts_it(worker_factory):
    process = worker_factory(delivery_sleep_fail=29, block_job=JOBS[-1], fast_first_sleep=1)
    process.wait_started(JOBS[-1])
    _delivery_loop_ended(process, ("SLEEP", "delivery"))
    starts = _count(process.events(), "START")
    process.release()
    process.wait_sleep(2)
    process.wait_started(DELIVERY, starts + 1)
    process.signal("TERM")
    events = process.finish(0)
    errors = process.errors()
    assert sum(item.get("job") == "delivery_wait" and item.get("exit") == 29 for item in errors) == 1
    assert [item.get("exit") for item in errors if item.get("job") == "delivery_loop"] == [29]
    assert _main_starts(events) == JOBS * 2


def test_failure_is_logged_and_returned_after_current_job_drains(worker_factory):
    process = worker_factory(block_job=JOBS[0], fail_job=JOBS[0], fail_code=7)
    process.wait_started(JOBS[0])
    process.signal("TERM")
    process.release()
    events = process.finish(7)
    assert sum(item.get("job") == "diagnostics" and item.get("exit") == 7 for item in process.errors()) == 1
    assert _main_starts(events) == [JOBS[0]]


def test_failed_job_keeps_running_the_round_and_retries_on_the_next_round(worker_factory):
    process = worker_factory(fail_job=JOBS[0], fail_once=1, fast_first_sleep=1)
    process.wait_sleep(2)
    process.signal("TERM")
    events = process.finish(0)
    assert _main_starts(events) == JOBS * 2
    assert [row[-1] for row in events if row[:2] == ["END", JOBS[0]]] == ["7", "0"]
    assert '"exit":7' in (process.root / "stderr.log").read_text()


@pytest.mark.parametrize("exit_code", [0, 9])
def test_daily_completion_marker_matches_the_drained_job(worker_factory, exit_code):
    process = worker_factory(block_job=DAILY, now="1000", fail_job=DAILY, fail_code=exit_code)
    process.wait_started(DAILY)
    process.signal("TERM")
    process.release()
    events = process.finish(exit_code)
    assert _main_starts(events) == [*JOBS, DAILY]
    assert process.mark.exists() is (exit_code == 0)
    if exit_code == 0:
        assert process.mark.read_text().strip() == "2026-10-18"


def test_daily_marker_write_failure_is_not_a_success(worker_factory):
    process = worker_factory(now="1000", mark_is_directory=True)
    # Redirection failures are shell-specific (for example Bash 1, dash 2).
    # Compare exact propagation with an independent command in the same shell.
    command = 'printf "%s\n" "2026-10-18" > "$1"'
    launcher = [str(DASH)] if process.shell == "dash" else [process.bash, "--noprofile", "--norc", "--posix"]
    reference = subprocess.run([*launcher, "-c", command, "worker-marker-reference", _shell_path(process.mark)],
        capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert reference.returncode > 0
    process.wait_sleep()
    process.signal("TERM")
    events = process.finish(reference.returncode)
    marker_errors = [item for item in process.errors() if item.get("job") == "daily_feedback_mark"]
    assert len(marker_errors) == 1 and marker_errors[0]["exit"] == reference.returncode
    assert _main_starts(events) == [*JOBS, DAILY]
    assert process.mark.is_dir()


def test_unexpected_sleep_failure_is_logged_and_propagated(worker_factory):
    process = worker_factory(sleep_fail=23)
    events = process.finish(23)
    assert '"job":"idle_wait","exit":23' in (process.root / "stderr.log").read_text()
    assert _main_starts(events) == JOBS


def test_repeated_stop_signals_do_not_interrupt_the_active_job(worker_factory):
    process = worker_factory(block_job=JOBS[0])
    process.wait_started(JOBS[0])
    process.signal("TERM")
    process.signal("INT")
    process.signal("TERM")
    process.release()
    events = process.finish(0)
    assert _main_starts(events) == [JOBS[0]]


def test_stop_at_job_completion_does_not_start_another_job(worker_factory):
    process = worker_factory(signal_at_end=JOBS[0])
    events = process.finish(0)
    assert _main_starts(events) == [JOBS[0]]
