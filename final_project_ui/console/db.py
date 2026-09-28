"""대상 프로젝트의 실행 DB 를 **읽기만** 한다.

★SELECT 만 한다. 이 콘솔은 대상을 쓰지 않는다.

★대상은 **PostgreSQL** 이다. 한때 이 파일이 `sqlite3` 로 짜여 있었고
  플레이스홀더도 `?` 였다 — 실행되면 죽는다. 대상을 안 보고 만든 코드였다.

★`case_events` 에는 `run_id` 컬럼이 **없다.** 실측한 스키마는 이렇다:

    agent_runs   run_id, tenant_id, case_id, graph_revision, status, attempt,
                 started_at, finished_at
    team_tasks   task_id, run_id, team_id, contract_version, payload_json, status, created_at
    llm_calls    call_id, run_id, prompt_id, provider, model, input_tokens,
                 output_tokens, latency_ms, cost_microusd, response_json, created_at
    case_events  event_id, tenant_id, case_id, aggregate_version, event_type,
                 payload_json, actor_type, actor_id, created_at

  그래서 trace 는 `run_id` 로 두 단계를 잇고, **case_events 는 `case_id` 로** 잇는다.

★테이블·컬럼이 다르면 **"읽지 못했다"** 로 보고한다. 빈 목록으로 바꾸지 않는다 —
  빈 목록은 "없다" 로 읽히고, 그건 모르는 것과 다르다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 지금 지원하는 것. 늘릴 때는 **드라이버가 실제로 있는지** 확인하고 늘린다.
SUPPORTED_SCHEMES = ("postgresql://", "postgres://")


@dataclass(frozen=True)
class DbRead:
    """읽기 결과. ★`status` 가 사건을 구분한다 — 하나로 뭉치지 않는다."""

    status: str
    rows: tuple[dict[str, Any], ...] = ()
    detail: str = ""
    state_counts: dict[str, Any] = field(default_factory=dict)
    trace: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "읽음"


def _connect(database_url: str):
    """psycopg 로 연결한다. ★드라이버가 없어도 예외로 죽지 않는다."""
    import psycopg  # 지연 import — 콘솔은 DB 없이도 떠야 한다
    return psycopg.connect(database_url, connect_timeout=3)


def _rows(cur, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    columns = [c.name for c in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def read_runs(database_url: str | None, *, tenant_id: str | None = None,
              limit: int = 20) -> DbRead:
    """최근 실행 목록.

    ★`limit` 를 쓰므로 **몇 개 중 몇 개인지** 함께 낸다.
    """
    if not database_url:
        return DbRead("연결 안 함", detail="database_url 이 프로필에 없음")
    if not database_url.startswith(SUPPORTED_SCHEMES):
        return DbRead("연결 안 함", detail=f"지원하지 않는 URL 형식: {database_url.split('://')[0]}")

    try:
        with _connect(database_url) as conn, conn.cursor() as cur:
            where, params = ("WHERE tenant_id=%s", (tenant_id,)) if tenant_id else ("", ())
            total = _rows(cur, f"SELECT count(*) AS n FROM agent_runs {where}", params)[0]["n"]
            runs = _rows(cur,
                         "SELECT run_id, tenant_id, case_id, graph_revision, status, "
                         f"started_at, finished_at FROM agent_runs {where} "
                         "ORDER BY started_at DESC NULLS LAST LIMIT %s", (*params, limit))
            counts = _state_counts(cur, where, params)
    except ImportError:
        return DbRead("연결 안 함", detail="psycopg 드라이버가 설치돼 있지 않다")
    except Exception as exc:
        # ★연결 실패를 "행이 없다" 로 읽지 않는다
        return DbRead("연결하지 못했다", detail=str(exc)[:200])

    shown = len(runs)
    detail = f"전체 {total}개 중 {shown}개 표시"
    if total > shown:
        detail += f" — {total - shown}개는 화면에 없다"
    return DbRead("읽음", tuple(runs), detail=detail, state_counts=counts)


def _state_counts(cur, where: str, params: tuple) -> dict[str, Any]:
    """상태 분포. ★테이블이 없으면 그 사실을 남긴다 — 0 으로 채우지 않는다."""
    counts: dict[str, Any] = {}
    for table in ("customer_cases", "outbox"):
        try:
            rows = _rows(cur, f"SELECT status, count(*) AS n FROM {table} {where} "
                              "GROUP BY status ORDER BY status", params)
            counts[table] = {str(r["status"]): int(r["n"]) for r in rows}
        except Exception as exc:
            cur.connection.rollback()
            counts[table] = {"__error__": str(exc)[:120]}
    return counts


def read_trace(database_url: str | None, run_id: str) -> DbRead:
    """한 실행을 따라간다.

        agent_runs ──run_id──> team_tasks
                   ──run_id──> llm_calls
                   ──case_id─> case_events

    ★`case_events` 는 `run_id` 가 없다. `agent_runs.case_id` 로 잇는다.
    """
    if not database_url:
        return DbRead("연결 안 함", detail="database_url 이 프로필에 없음")
    if not database_url.startswith(SUPPORTED_SCHEMES):
        return DbRead("연결 안 함", detail="지원하지 않는 URL 형식")

    # ★UUID 형식이 아닌 값은 실제로 실측했다 —
    #   postgres 가 조회 전에 `invalid input syntax for type uuid` 로 거부한다.
    #   그걸 그대로 사용자에게 보여주면 "존재하지 않음" 과 구분이 안 되니 여기서 갈라 준다.
    try:
        from uuid import UUID
        UUID(str(run_id))
    except ValueError:
        return DbRead("그 실행이 없다", detail=f"run_id 형식이 아니다: {run_id!r}")

    stages: list[dict[str, Any]] = []
    try:
        with _connect(database_url) as conn, conn.cursor() as cur:
            run = _rows(cur, "SELECT run_id, tenant_id, case_id, graph_revision, status, "
                             "started_at, finished_at FROM agent_runs WHERE run_id=%s", (run_id,))
            if not run:
                return DbRead("그 실행이 없다", detail=run_id)
            stages.append({"stage": "agent_runs", "rows": run})

            for table, sql, params in (
                ("team_tasks",
                 "SELECT task_id, team_id, contract_version, status, created_at "
                 "FROM team_tasks WHERE run_id=%s ORDER BY created_at", (run_id,)),
                ("llm_calls",
                 "SELECT call_id, prompt_id, provider, model, input_tokens, output_tokens, "
                 "latency_ms, cost_microusd, created_at FROM llm_calls WHERE run_id=%s "
                 "ORDER BY created_at", (run_id,)),
                # ★case_id 로 잇는다 — run_id 컬럼이 없다
                ("case_events",
                 "SELECT event_id, aggregate_version, event_type, actor_type, actor_id, "
                 "created_at FROM case_events WHERE tenant_id=%s AND case_id=%s "
                 "ORDER BY aggregate_version", (run[0]["tenant_id"], run[0]["case_id"])),
            ):
                try:
                    stages.append({"stage": table, "rows": _rows(cur, sql, params)})
                except Exception as exc:
                    cur.connection.rollback()
                    # ★조용히 건너뛰지 않는다. 무엇을 못 읽었는지 남긴다.
                    stages.append({"stage": table, "error": str(exc)[:160]})
    except ImportError:
        return DbRead("연결 안 함", detail="psycopg 드라이버가 설치돼 있지 않다")
    except Exception as exc:
        return DbRead("연결하지 못했다", detail=str(exc)[:200])

    return DbRead("읽음", trace=tuple(stages),
                  detail=f"{len(stages)}단계")


#: 옛 이름. 화면이 아직 이걸 부른다.
read_agent_runs = read_runs
