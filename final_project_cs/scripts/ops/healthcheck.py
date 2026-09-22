"""상시 실행이 **살아 있나** — 한 번에 본다.

    python -m scripts.ops.healthcheck
    python -m scripts.ops.healthcheck --json
    python -m scripts.ops.healthcheck --strict      경고도 실패로 센다

읽기만 한다. 아무것도 고치지 않고 아무것도 띄우지 않는다.

★**못 하는 확인은 「못 한다」고 적는다**(`판정 = 못확인`). 「확인했는데 괜찮다」와
  「확인 못 했다」를 같은 칸에 넣으면 안 돌고 있는 것을 돌고 있다고 읽는다 —
  이 프로젝트가 그것 때문에 한 번 데었다(`CLAUDE.md` 전역 §1).

판정 네 가지

    OK      확인했고 정상이다
    경고    확인했고 수상하다 — 사람이 본다
    실패    확인했고 고장이다 — exit 1
    못확인  **확인 자체를 못 했다.** 정상이라는 뜻이 아니다
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.jobs import HEARTBEAT_DIR, JOBS, PG_SERVICE_NAME  # noqa: E402

OK, WARN, FAIL, UNKNOWN = "OK", "경고", "실패", "못확인"

#: 바깥함에 이만큼 넘게 남은 `pending` 이 있으면 배달 일꾼을 의심한다(분).
#: ★출처: **우리가 고른 값**이다. 일꾼 주기가 1분이니 10분이면 열 번을 놓친 것이다.
DEFAULT_PENDING_MINUTES = 10

RESULTS: list[dict] = []


def record(name: str, verdict: str, detail: str, *, cannot: str = "") -> None:
    RESULTS.append({"항목": name, "판정": verdict, "내용": detail, "못하는것": cannot})


def ago(when: datetime | None) -> str:
    if when is None:
        return "(없음)"
    if when.tzinfo is None:
        when = when.astimezone()
    seconds = (datetime.now(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()
    if seconds < 90:
        return f"{seconds:.0f}초 전"
    if seconds < 5400:
        return f"{seconds / 60:.0f}분 전"
    if seconds < 172800:
        return f"{seconds / 3600:.1f}시간 전"
    return f"{seconds / 86400:.1f}일 전"


def age_seconds(when: datetime) -> float:
    if when.tzinfo is None:
        when = when.astimezone()
    return (datetime.now(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()


# ── DB ──────────────────────────────────────────────────────────────

def check_database(pending_minutes: int) -> None:
    try:
        import psycopg

        from app.core.settings import get_guardrails, get_settings
    except Exception as exc:  # noqa: BLE001
        record("db", FAIL, f"설정·드라이버를 못 읽었다 — {type(exc).__name__}: {exc}")
        record("stuck_cases", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        record("outbox_pending", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        record("notice", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        return

    settings = get_settings()
    tenant = settings.tenant_id
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    guardrails = get_guardrails()
    classify_after = guardrails.get("reliability.classification_stuck_after_seconds")
    routing_after = guardrails.get("reliability.routing_stuck_after_seconds")

    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
    except Exception as exc:  # noqa: BLE001
        record("db", FAIL, f"연결 안 됨 — {type(exc).__name__}: {exc}")
        record("stuck_cases", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        record("outbox_pending", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        record("notice", UNKNOWN, "DB 를 못 봐서 셀 수 없다")
        return

    with conn, conn.cursor() as cur:
        cur.execute("select version(), pg_postmaster_start_time()")
        version, started = cur.fetchone()
        record("db", OK, f"{version.split(',')[0]} · 기동 {ago(started)} "
                         f"({started.astimezone().isoformat(timespec='seconds')})")

        # ── 되잡기가 일을 하고 있나 ──
        # ★heartbeat 가 아니라 **결과**를 본다. 작업이 걸려 있어도 매번 죽고 있으면
        #   여기가 쌓인다. 둘을 함께 봐야 「돌았다」와 「됐다」가 갈린다.
        cur.execute(
            "select status::text, count(*), min(updated_at) from customer_cases "
            "where tenant_id=%s and ((status='classifying' and updated_at < now() - make_interval(secs=>%s)) "
            "or (status='routing' and updated_at < now() - make_interval(secs=>%s))) "
            "group by status", (tenant, classify_after, routing_after))
        rows = cur.fetchall()
        # ★되잡기는 **설정 테넌트 하나만** 훑는다(`get_settings().tenant_id`). 다른 테넌트에
        #   멈춘 Case 는 아무도 안 본다 — 세어서 같이 알린다.
        cur.execute(
            "select count(*) from customer_cases where tenant_id<>%s "
            "and ((status='classifying' and updated_at < now() - make_interval(secs=>%s)) "
            "or (status='routing' and updated_at < now() - make_interval(secs=>%s)))",
            (tenant, classify_after, routing_after))
        (others,) = cur.fetchone()
        tail = (f" · ★다른 테넌트에 {others}건 더 있다 — 되잡기는 {tenant!r} 만 훑는다"
                if others else "")
        if not rows:
            record("stuck_cases", WARN if others else OK,
                   f"임계값(분류 {classify_after}초 · 실행 {routing_after}초)을 넘긴 Case "
                   f"{tenant!r} 에 0건{tail}")
        else:
            worst = min(r[2] for r in rows)
            total = sum(r[1] for r in rows)
            breakdown = " · ".join(f"{r[0]} {r[1]}건" for r in rows)
            record("stuck_cases", WARN,
                   f"임계값을 넘긴 Case **{total}건** ({breakdown}) · 가장 오래된 것 {ago(worst)} "
                   f"— 되잡기가 안 돌거나 `errored` 로 매번 실패하고 있다{tail}")

        # ── 바깥함 ──
        # ★**테넌트로 좁히지 않는다.** 배달 일꾼은 `--tenant` 없이 돌면 전체를 집는다.
        #   설정 테넌트(`demo`)만 보면 다른 테넌트에 밀린 통지를 못 본다 —
        #   2026-09-22 에 실제로 그랬다(`demo` 는 0건인데 시나리오 테넌트에 8건이 8시간 잤다).
        cur.execute("select status, count(*) from outbox group by status")
        by_status = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute("select count(*), min(available_at) from outbox "
                    "where status='pending' and available_at<=now()")
        due, oldest = cur.fetchone()
        cur.execute("select count(*) from outbox where tenant_id=%s and status='pending' "
                    "and available_at<=now()", (tenant,))
        (due_here,) = cur.fetchone()
        summary = (" · ".join(f"{k} {v}" for k, v in sorted(by_status.items())) or "행 없음") \
            + f" (전체 테넌트 · 설정 테넌트 {tenant!r} 의 pending {due_here}건)"
        if due and oldest and age_seconds(oldest) > pending_minutes * 60:
            record("outbox_pending", WARN,
                   f"보낼 때가 됐는데 안 나간 것 **{due}건** · 가장 오래된 것 {ago(oldest)} "
                   f"(기준 {pending_minutes}분) — 배달 일꾼을 의심한다 · 전체: {summary}")
        else:
            record("outbox_pending", OK,
                   f"때가 된 pending {due}건" + (f" · 가장 오래된 것 {ago(oldest)}" if oldest else "")
                   + f" · 전체: {summary}")
        bad = {k: v for k, v in by_status.items() if k in ("unknown", "dead_letter")}
        if bad:
            record("outbox_bad", WARN,
                   " · ".join(f"{k} {v}건" for k, v in sorted(bad.items()))
                   + " — 사람이 판정해야 한다(wiki/operations/unknown-state.md)")
        else:
            record("outbox_bad", OK, "unknown · dead_letter 0건")

        # ── 안내가 최근 나갔나 ── (위와 같은 이유로 전체 테넌트를 본다)
        cur.execute("select status, count(*), max(available_at) from outbox "
                    "where topic='trip.notice' group by status")
        notice = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        if not notice:
            record("notice", UNKNOWN, "`trip.notice` 행이 0건이다 — 안 나간 것인지 보낼 것이 "
                                      "없었던 것인지 **구분 못 한다**",
                   cannot="여행·일정이 없으면 안내도 없다. 이 항목만으로 고장을 판정하지 않는다")
        else:
            delivered = notice.get("delivered")
            line = " · ".join(f"{k} {v[0]}건" for k, v in sorted(notice.items()))
            if delivered:
                record("notice", OK,
                       f"{line} · 배달된 것 중 가장 최근 행의 `available_at` {ago(delivered[1])}",
                       cannot="★**배달 시각은 못 잰다** — `outbox` 에 배달 시각 칸이 없다"
                              "(`available_at` 은 「보낼 수 있게 된 시각」이다). 위 값은 그 근사치다")
            else:
                record("notice", WARN, f"{line} — **배달된 안내가 0건**이다",
                       cannot="배달 시각 칸이 없다(위와 같다)")

        # ── 되잡기의 DB 쪽 흔적 ──
        cur.execute("select max(created_at) from case_events where tenant_id=%s and actor_id='sweeper'",
                    (tenant,))
        (last_sweep,) = cur.fetchone()
        record("sweeper_흔적", UNKNOWN if last_sweep is None else OK,
               f"되잡기가 마지막으로 Case 를 건드린 때: {ago(last_sweep)}",
               cannot="★이것은 **실행 여부의 증거가 아니다.** 되잡을 것이 없으면 아무 "
                      "흔적도 안 남는다 — 「오래됐다」가 「안 돌았다」를 뜻하지 않는다. "
                      "실행 여부는 아래 heartbeat 가 답한다")


# ── 상시 실행 흔적(heartbeat) ────────────────────────────────────────

def check_heartbeats() -> None:
    for job in JOBS.values():
        if job.kind == "service":
            continue
        path = HEARTBEAT_DIR / f"{job.name}.json"
        if not path.is_file():
            record(f"{job.name}_실행", UNKNOWN,
                   f"기록이 없다 ({path.relative_to(REPO_ROOT)}) — `scripts.ops.tick` 으로 "
                   f"한 번도 돈 적이 없다",
                   cannot="사람이 손으로 `python -m scripts.run_…` 을 돌린 것은 여기 안 남는다. "
                          "「안 돌았다」가 아니라 「이 경로로는 안 돌았다」다")
            continue
        try:
            beat = json.loads(path.read_text(encoding="utf-8"))
            stamp = datetime.fromisoformat(beat.get("finished_at") or beat["started_at"])
        except Exception as exc:  # noqa: BLE001
            record(f"{job.name}_실행", FAIL, f"기록을 못 읽었다 — {type(exc).__name__}: {exc}")
            continue
        seconds, code = age_seconds(stamp), beat.get("exit_code")
        state = beat.get("state")
        limit = job.max_silence_seconds
        if state == "running":
            record(f"{job.name}_실행", OK, f"상주로 떠 있다고 기록돼 있다 (시작 {ago(stamp)})",
                   cannot="★이 줄은 **기록**이지 확인이 아니다 — 그 뒤에 죽었으면 여기는 그대로다. "
                          "살아 있는지는 `app` 줄(HTTP)이 본다")
            continue
        if limit is not None and seconds > limit:
            record(f"{job.name}_실행", FAIL,
                   f"마지막 회차가 {ago(stamp)} — 기준 {limit // 60}분을 넘겼다. 안 돌고 있다")
        elif code not in (0, None):
            record(f"{job.name}_실행", WARN,
                   f"마지막 회차 {ago(stamp)} · **exit={code}** — 돌긴 했는데 실패했다. "
                   f"var/ops/logs/{job.name}-<날짜>.log 를 본다")
        else:
            record(f"{job.name}_실행", OK, f"마지막 회차 {ago(stamp)} · exit={code}")


# ── DB 가 서비스인가 · 앱이 응답하나 ────────────────────────────────

def check_db_is_service() -> None:
    import subprocess

    try:
        result = subprocess.run(["sc", "query", PG_SERVICE_NAME], capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        record("db_수명", UNKNOWN, "`sc` 가 없다 — 이 기계가 Windows 가 아닌가")
        return
    if result.returncode == 0:
        record("db_수명", OK, f"서비스 {PG_SERVICE_NAME!r} 로 등록돼 있다 — 콘솔·세션과 끊겨 있다")
    else:
        record("db_수명", WARN,
               f"서비스 {PG_SERVICE_NAME!r} 가 없다 — DB 가 **누군가의 셸/콘솔의 자식**으로 떠 있다. "
               f"그 셸이 사라지면 종료 기록도 없이 함께 꺼진다",
               cannot="다른 이름으로 등록된 PostgreSQL 서비스가 있으면 이 검사는 못 본다 — "
                      "이름은 `scripts/ops/jobs.py` 의 PG_SERVICE_NAME 하나만 본다")


def check_app() -> None:
    try:
        from app.core.settings import get_settings

        base = get_settings().public_base_url.rstrip("/")
    except Exception as exc:  # noqa: BLE001
        record("app", UNKNOWN, f"주소를 못 읽었다 — {type(exc).__name__}: {exc}")
        return
    url = f"{base}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 — 루프백이다
            body = response.read(200).decode("utf-8", "replace")
            record("app", OK if response.status == 200 else WARN,
                   f"{url} → {response.status} {body.strip()[:80]}")
    except urllib.error.URLError as exc:
        # ★이 주소는 **고객에게 나가는 여행계획서 링크의 주소**다(`ACOP_PUBLIC_BASE_URL`).
        #   앱이 다른 포트에 떠 있으면 앱은 살아 있는데 링크는 죽는다 — 실제로 그랬다
        #   (2026-09-22: 앱은 8043, 설정은 8042).
        record("app", FAIL, f"{url} 안 열린다 — {exc.reason} · 이 주소가 "
                            f"**고객 링크에 박히는 주소**다(ACOP_PUBLIC_BASE_URL). "
                            f"앱이 다른 포트에 떠 있어도 링크는 깨진다")
    except Exception as exc:  # noqa: BLE001
        record("app", FAIL, f"{url} 확인 실패 — {type(exc).__name__}: {exc}")


# ── 이 점검이 아예 못 보는 것 ───────────────────────────────────────

CANNOT_AT_ALL = [
    "**알림을 고객이 읽었는지** — 디스코드·텔레그램·메일 어느 것도 읽음을 안 준다"
    "(v11 §6-A). 잴 수 있는 것은 계획서 링크 열람이고 그건 DoD-25 가 본다",
    "**일일 피드백 배치가 돌았는지** — heartbeat 는 보지만 "
    "`feedback_analytics_reports` 에 어제 행이 있는지는 **아직 안 센다**",
    "**DB 가 언제 죽었는지** — 서비스가 아니면 종료 기록이 안 남는다"
    "(`wiki/records/manuals/운영_로컬DB_기동과_비정상종료.md` §4). 지금 안 떠 있다는 것만 안다",
    "**바깥 소스(기상·교통·관광)가 지금 답하는지** — 부르면 한도를 쓴다. "
    "감시 한 회차의 `fatal` 수로 간접으로만 본다",
    "**다른 기계에서 도는 것** — 이 점검은 이 기계와 설정된 DB 만 본다",
]


def main() -> int:
    # ★윈도 콘솔 기본 인코딩(cp949)으로는 이 표의 글자가 안 나간다 — 출력만 UTF-8 로 돌린다.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="상시 실행이 살아 있나(읽기만 한다)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="경고도 실패로 센다")
    parser.add_argument("--pending-minutes", type=int, default=DEFAULT_PENDING_MINUTES)
    args = parser.parse_args()

    check_database(args.pending_minutes)
    check_db_is_service()
    check_heartbeats()
    check_app()

    counts = {v: sum(1 for r in RESULTS if r["판정"] == v) for v in (OK, WARN, FAIL, UNKNOWN)}
    if args.json:
        print(json.dumps({"checks": RESULTS, "counts": counts,
                          "cannot_at_all": CANNOT_AT_ALL}, ensure_ascii=False, indent=2))
    else:
        width = max(len(r["항목"]) for r in RESULTS)
        print("=" * 100)
        print(f"A-COP 상시 실행 점검 — {datetime.now().astimezone().isoformat(timespec='seconds')}")
        print("=" * 100)
        for r in RESULTS:
            print(f"[{r['판정']:<4}] {r['항목'].ljust(width)}  {r['내용']}")
            if r["못하는것"]:
                print(f"{' ' * (width + 9)}└ 못 하는 것: {r['못하는것']}")
        print("=" * 100)
        total = len(RESULTS)
        print(f"OK {counts[OK]}/{total} · 경고 {counts[WARN]}/{total} · "
              f"실패 {counts[FAIL]}/{total} · 못확인 {counts[UNKNOWN]}/{total}")
        print()
        print("★이 점검이 **아예 못 보는 것**")
        for line in CANNOT_AT_ALL:
            print(f"  - {line}")
    bad = counts[FAIL] + (counts[WARN] if args.strict else 0)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
