"""상시로 돌아야 하는 것들의 **단일 목록**.

★한 곳에만 적는다. 등록(`install_services`)·실행(`tick`)·점검(`healthcheck`)이
  같은 표를 읽어야 「걸어 둔 것」과 「보는 것」이 어긋나지 않는다. 지금까지는
  세 가지가 각자 다른 문서에 흩어져 있어서 **무엇이 안 돌고 있었는지 아무도
  몰랐다**(`wiki/operations/always-on.md` §「지금 상태」).

★주기는 **안전이 아니라 복구 지연**을 정한다. 안전은 임계값이 정한다 —
  `config/guardrails.yaml` 의 `reliability.*_stuck_after_seconds`.

★여기 적힌 `max_silence_seconds` 는 **「이만큼 소식이 없으면 죽은 것으로 본다」**
  이다. 주기의 몇 배로 잡는다 — 한 회차가 느린 것과 죽은 것을 가르기 위해서다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 실행 기록이 쌓이는 곳. `var/` 는 `.gitignore` 에 있다 — 운영 기록이지 소스가 아니다.
OPS_DIR = REPO_ROOT / "var" / "ops"
HEARTBEAT_DIR = OPS_DIR / "heartbeat"
LOG_DIR = OPS_DIR / "logs"

#: PostgreSQL 을 Windows 서비스로 등록할 때 쓸 이름.
#: ★저장소 이름이 아니라 **클러스터** 이름을 넣는다 — 이 클러스터는 A-COP 만의 것이
#:   아니다. 같은 데이터 디렉터리에 옆 프로젝트 DB 가 함께 있다
#:   (`wiki/operations/local-setup.md` §「알아야 할 것」).
PG_SERVICE_NAME = "pgv-postgresql-5433"


@dataclass(frozen=True)
class Job:
    """상시 실행 단위 하나."""

    name: str
    title: str
    #: tick    — 스케줄러가 주기적으로 한 회차씩 부른다(`scripts.ops.tick`)
    #: resident — 한 번 떠서 계속 도는 프로세스
    #: service  — Windows 서비스로 등록한다(스케줄러가 아니다)
    kind: str
    #: `python -m ...` 뒤에 붙는 인자. kind=service 면 비어 있다.
    argv: list[str] = field(default_factory=list)
    #: 몇 분마다 부르나(kind=tick). daily_at 이 있으면 None.
    every_minutes: int | None = None
    #: 하루 한 번 도는 것의 시각 "HH:MM"(로컬 시간).
    daily_at: str | None = None
    #: 작업 스케줄러에 들어갈 이름. kind=service 면 서비스 이름.
    task_name: str = ""
    #: 이만큼 소식이 없으면 죽은 것으로 본다(초). None 이면 점검이 시각을 안 본다.
    max_silence_seconds: int | None = None
    #: 왜 상시로 돌아야 하나 — 문서와 미리보기 출력에 그대로 실린다.
    why: str = ""
    #: 죽으면 무엇으로 아는가.
    dead_signal: str = ""


JOBS: dict[str, Job] = {
    "postgres": Job(
        name="postgres",
        title="PostgreSQL 16.14 (127.0.0.1:5433)",
        kind="service",
        task_name=PG_SERVICE_NAME,
        max_silence_seconds=None,
        why="나머지 전부가 이것 위에 선다. 지금은 셸이 띄운 자식이라 그 셸이 사라지면 "
            "종료 기록도 없이 함께 꺼진다(wiki/records/manuals/운영_로컬DB_기동과_비정상종료.md §4-①).",
        dead_signal="5433 이 안 열린다. 점검의 `db` 줄이 FAIL 이 된다. "
                    "★죽는 순간은 지금 아무 데도 안 남는다 — 서비스로 올려야 정상 종료 경로가 생긴다.",
    ),
    "sweepers": Job(
        name="sweepers",
        title="되잡기 작업 (멈춘 Case · 여행 감시 · 일정 안내)",
        kind="tick",
        argv=["-m", "scripts.run_sweepers", "--once"],
        every_minutes=1,
        task_name="A-COP cs sweepers",
        max_silence_seconds=600,
        why="접수·분류·실행을 나눈 대가다. 안 돌면 `classifying`·`routing` 에 남은 Case 가 "
            "영원히 그대로 있고, 일정 안내(v11 §6-B)가 때를 놓친다.",
        dead_signal="`customer_cases` 에 임계값(분류 300초·실행 600초)을 넘긴 Case 가 쌓인다. "
                    "점검의 `stuck_cases` 줄이 센다.",
    ),
    "outbox": Job(
        name="outbox",
        title="바깥함 일꾼 (통지 배달)",
        kind="tick",
        argv=["-m", "scripts.run_outbox_worker", "--once", "--drain"],
        every_minutes=1,
        task_name="A-COP cs outbox",
        max_silence_seconds=600,
        why="통지는 바깥함(`outbox`)에 쌓이기만 한다. 일꾼이 안 돌면 고객에게 아무것도 안 나간다 — "
            "그런데 시스템 어디에도 오류가 안 뜬다.",
        dead_signal="`outbox` 의 `pending` 이 오래 남는다. 점검의 `outbox_pending` 줄이 가장 오래된 건의 나이를 잰다.",
    ),
    "daily_feedback": Job(
        name="daily_feedback",
        title="일일 피드백 집계 (VOC 급증 탐지)",
        kind="tick",
        argv=["-m", "scripts.run_daily_feedback"],  # --date 는 tick 이 그날 날짜로 채운다
        daily_at="09:10",  # guardrails `feedback_analytics.batch_time_utc: 00:10` = KST 09:10
        task_name="A-COP cs daily-feedback",
        max_silence_seconds=60 * 60 * 30,  # 하루 + 여유 6시간
        why="`config/guardrails.yaml` 의 `feedback_analytics.batch_time_utc: 00:10` 이 정한 배치다. "
            "안 돌면 급증을 아무도 못 본다.",
        dead_signal="`feedback_analytics_reports` 에 어제 날짜 행이 없다. "
                    "★점검은 이것을 **아직 안 본다**(아래 「점검이 못 하는 것」).",
    ),
    "app": Job(
        name="app",
        title="앱 (uvicorn · 에이전트 API · 여행계획서 링크 · 운영 화면)",
        kind="resident",
        # ★포트는 공개 주소(`ACOP_PUBLIC_BASE_URL`)와 **같아야** 한다. 8043 으로 띄웠더니
        #   통지에 실린 계획서 링크가 죽은 주소를 가리켰다(2026-09-22).
        argv=["-m", "uvicorn", "app.presentation.api.app:app", "--port", "8042"],
        task_name="A-COP cs app",
        max_silence_seconds=None,
        why="접점이 둘인데(에이전트 API · 여행계획서 링크) 둘 다 이 프로세스다. "
            "★**상태의 정본이 링크**라서(v11 §9-C) 앱이 꺼지면 고객이 맞는 것을 볼 데가 없다.",
        dead_signal="`/health` 가 안 열린다. 점검의 `app` 줄이 FAIL 이 된다. "
                    "★작업 스케줄러는 죽은 프로세스를 **다시 띄워 주지 않는다** — 길 ②가 푸는 문제다.",
    ),
}

#: `--only` 를 안 주면 이것들만 다룬다. `postgres` 는 **공유 클러스터**라
#: 일부러 뺀다 — 전체 적용에 묻어 들어가면 옆 프로젝트가 같이 바뀐다.
DEFAULT_JOBS = ("sweepers", "outbox", "daily_feedback", "app")


def select(only: str | list[str] | None) -> list[Job]:
    """`--only a,b` 와 `--only a --only b` 를 **둘 다** Job 목록으로. 모르는 이름은 죽는다.

    ★`[2026-09-22]` 쉼표만 받던 때 `--only a --only b --only c` 가 **조용히 마지막 하나**로
      줄었다(argparse 기본 동작). 등록했다는 말은 맞았지만 셋 중 둘이 안 걸렸다.
    """
    if not only:
        return [JOBS[name] for name in DEFAULT_JOBS]
    raws: list[str] = []
    for chunk in ([only] if isinstance(only, str) else list(only)):
        raws += str(chunk).split(",")
    picked, seen = [], set()
    for raw in raws:
        name = raw.strip()
        if not name:
            continue
        if name not in JOBS:
            raise SystemExit(f"★모르는 작업 이름: {name!r} — 있는 것: {', '.join(JOBS)}")
        if name in seen:            # 같은 이름을 두 번 줘도 두 번 걸지 않는다
            continue
        seen.add(name)
        picked.append(JOBS[name])
    return picked


def schedule_text(job: Job) -> str:
    if job.kind == "service":
        return "서비스 (기계가 켜지면 자동)"
    if job.daily_at:
        return f"하루 한 번 {job.daily_at}"
    if job.every_minutes:
        return f"{job.every_minutes}분마다"
    return "상주 (한 번 떠서 계속)"
