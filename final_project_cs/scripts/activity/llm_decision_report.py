"""활동 LLM 운영 판정 기록을 문서(마크다운)로 만든다 — **코드 결과 / LLM 재정의 결과 / 고객에게 나간 결과**. `[2026-10-24 사용자 지시]`

★무엇을 읽나
  - 표 `activity_llm_decisions`(308) — LLM 을 부른 운영 판정 한 건마다 코드 결과 · LLM 원래 답 · 고객에게 나간 결과.
    대체 후보 순서(`alternative_order`)와, 규칙이 「모름」이라 LLM 이 정한 판정(`kind_modes` 가 `llm` 인 종류)이 들어온다.
  - 표 `activity_judge_shadow`(305)의 운영 줄(`origin='live'`) — 섀도 판정(고객 결과는 규칙 그대로, LLM 값은 기록만).
  - 장소 이름은 표에 없다(번호만 싣는다) — 관광공사 목록(`place_catalog`)에서 찾아 붙인다.
★기록이 없으면 「없음」이라고 쓴다 — 빈 표를 만들지 않는다. 전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule` 이면 판정 LLM 이 없어
  아무것도 쌓이지 않는다.
★쓰지 않는 것 — 고객 문장 · 설문 · DB 접속 비밀 값. 문서에는 DB 주소의 호스트 · 이름만 적는다.

사용법
    python scripts/activity/llm_decision_report.py                         최근 7일 → wiki/records/reports/<오늘>_활동LLM_운영판정기록.md
    python scripts/activity/llm_decision_report.py --since 2026-10-21      그날부터 오늘까지
    python scripts/activity/llm_decision_report.py --stdout                파일을 쓰지 않고 화면에
    python scripts/activity/llm_decision_report.py --overwrite             같은 이름 파일이 있으면 _backup 에 옮겨 두고 다시 쓴다
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

KST = ZoneInfo("Asia/Seoul")

KIND_NAMES = {"alternative_order": "대체 후보 순서", "closure": "휴무", "operating_hours": "운영시간",
              "weather_sensitive": "날씨 민감(실내외)", "disaster_effect": "재난 영향", "live_status": "임시휴무 · 폐업"}
OUTCOME_NAMES = {"llm_served": "LLM 결과 사용", "code_fallback": "코드로 돌아감", "skipped": "건너뜀(예산)",
                 "shadow": "섀도(기록만)"}


# ── 그리기 (DB 없이 시험한다) ───────────────────────────────────────
def _pct(n: int, d: int) -> str:
    return f"{n}/{d} = {n / d * 100:.1f}%" if d else "0/0"


def _cell(text: Any) -> str:
    """표 칸 — 줄바꿈 · `|` 를 막는다."""
    if text is None or text == "":
        return "—"
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _when(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(KST).strftime("%m-%d %H:%M")
    return _cell(value)


def _case(value: Any) -> str:
    return f"`{str(value)[:8]}`" if value else "—"


def _order(ids: Any, titles: dict[str, str], pool: list[str] | None = None) -> str:
    """`["126508", "126512"]` → 「1. 경복궁 → 2. 창덕궁」. 코드 후보에 없던 번호는 「(목록 밖)」을 붙인다."""
    if not isinstance(ids, list) or not ids:
        return "—"
    names = []
    for i, raw in enumerate(ids, 1):
        key = str(raw)
        name = titles.get(key) or f"#{key}"
        if pool is not None and key not in pool:
            name += " (목록 밖)"
        names.append(f"{i}. {name}")
    return _cell(" → ".join(names))


def _value(result: Any) -> str:
    if not isinstance(result, dict):
        return "—"
    value = result.get("value")
    basis = result.get("basis")
    return _cell(f"{value} ({basis})" if basis else value)


def render(decisions: list[dict[str, Any]], shadows: list[dict[str, Any]], titles: dict[str, str], *,
           since: date, until: date, generated_at: datetime, source: str,
           missing: list[str] | None = None) -> str:
    """기록 → 마크다운 한 문서. 줄 순서는 받은 그대로(시각 순)다."""
    lines = [f"# 활동 LLM 운영 판정 기록 — {since.isoformat()} ~ {(until - timedelta(days=1)).isoformat()}", "",
             f"생성 {generated_at.astimezone(KST).strftime('%Y-%m-%d %H:%M')} KST · DB `{source}` · "
             "출처 표 `activity_llm_decisions`(308) · `activity_judge_shadow`(305, 운영 줄만)", ""]
    for name in missing or []:
        lines += [f"> ☆표 `{name}` 이 이 DB 에 없다 — 마이그레이션이 적용되지 않았다. 그 표의 기록은 0 으로 셌다.", ""]

    # 요약
    lines += ["## 요약", ""]
    if not decisions and not shadows:
        lines += ["이 기간에 **운영 LLM 판정 기록이 없습니다.** 전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule`(코드 기본값)이면 "
                  "판정 LLM 이 조립되지 않아 아무것도 쌓이지 않습니다.", ""]
        return "\n".join(lines)
    lines += ["| 판정 종류 | 모드 | 건수 | LLM 결과 사용 | 그중 코드 결과와 달라짐 | 코드로 돌아감 | 건너뜀 | 섀도(기록만) |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in decisions:
        groups.setdefault((row["kind"], row["mode"]), []).append(row)
    for (kind, mode), rows in groups.items():
        n = len(rows)
        served = [r for r in rows if r["outcome"] == "llm_served"]
        count = {o: sum(r["outcome"] == o for r in rows) for o in OUTCOME_NAMES}
        lines.append(f"| {KIND_NAMES.get(kind, kind)} | `{mode}` | {n} | {_pct(len(served), n)} | "
                     f"{_pct(sum(bool(r['changed']) for r in served), len(served))} | {_pct(count['code_fallback'], n)} | "
                     f"{_pct(count['skipped'], n)} | {_pct(count['shadow'], n)} |")
    if shadows:
        comparable = [s for s in shadows if s.get("comparable")]
        lines.append(f"| 섀도 판정 5종 | `shadow` | {len(shadows)} | — | — | — | — | {_pct(len(shadows), len(shadows))} |")
        lines += ["", f"섀도 판정 일치율(둘 다 「모름」이 아닌 줄): {_pct(sum(bool(s.get('agree')) for s in comparable), len(comparable))}"]
    lines.append("")

    # 대체 후보 순서
    orders = [r for r in decisions if r["kind"] == "alternative_order"]
    lines += ["## 대체 후보 순서 — 코드 결과 / LLM 재정의 결과", ""]
    if not orders:
        lines += ["기록 없음.", ""]
    else:
        lines += ["「LLM 원래 답」은 검사(목록 밖 장소 버리기 · 이유 문장 검사기) 전 값이고, 「고객에게 나간 순서」는 실제 화면 순서다. "
                  "★ = 고객에게 나간 순서가 코드 순서와 다르다.", "",
                  "| 시각 | Case | 결과 | 코드 순서 | LLM 원래 답 | 고객에게 나간 순서 | 바뀜 | 고객에게 보인 이유 | 검사기 | 실패 | 지연 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in orders:
            pool = [str(x) for x in (r["code_result"] or {}).get("order") or []]
            llm = r.get("llm_result") or {}
            lines.append(" | ".join([
                f"| {_when(r['decided_at'])}", _case(r.get("case_id")), OUTCOME_NAMES.get(r["outcome"], r["outcome"]),
                _order(pool, titles), _order(llm.get("order"), titles, pool),
                _order((r["served_result"] or {}).get("order"), titles), "예 ★" if r["changed"] else "아니요",
                _cell(r.get("reason")), _cell(r.get("reason_guard")),
                _cell(" · ".join(x for x in (r.get("failure_code"), r.get("error")) if x)),
                f"{r['latency_ms'] / 1000:.1f}초 |" if r.get("latency_ms") is not None else "— |"]))
        lines.append("")

    # 다른 판정
    others = [r for r in decisions if r["kind"] != "alternative_order"]
    lines += ["## 다른 판정 — 규칙이 「모름」일 때 LLM 이 정한 값", ""]
    if not others:
        lines += ["기록 없음.", ""]
    else:
        lines += ["| 시각 | Case | 종류 | 결과 | 코드 결과 | LLM 결과 | 고객에게 나간 결과 | 바뀜 | 실패 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in others:
            lines.append(f"| {_when(r['decided_at'])} | {_case(r.get('case_id'))} | {KIND_NAMES.get(r['kind'], r['kind'])} | "
                         f"{OUTCOME_NAMES.get(r['outcome'], r['outcome'])} | {_value(r['code_result'])} | "
                         f"{_value(r.get('llm_result'))} | {_value(r['served_result'])} | "
                         f"{'예 ★' if r['changed'] else '아니요'} | {_cell(r.get('failure_code'))} |")
        lines.append("")

    # 섀도
    lines += ["## 섀도 판정 — 고객 결과는 코드 그대로", ""]
    if not shadows:
        lines += ["기록 없음.", ""]
    else:
        lines += ["| 시각 | Case | 종류 | 코드 결과 | LLM 결과 | 일치 | 실패 |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for s in shadows:
            agree = "비교 불가" if not s.get("comparable") else ("일치" if s.get("agree") else "불일치 ★")
            llm = s.get("llm_value") if s.get("event") == "shadow" else f"({s.get('event')})"
            lines.append(f"| {_when(s['created_at'])} | {_case(s.get('case_id'))} | {KIND_NAMES.get(s['kind'], s['kind'])} | "
                         f"{_cell(s.get('rule_value'))} | {_cell(llm)} | {agree} | {_cell(s.get('llm_failure_code'))} |")
        lines.append("")
    return "\n".join(lines)


# ── DB 읽기 ─────────────────────────────────────────────────────────
def _exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (table,))
    return cur.fetchone()[0] is not None


def _rows(cur) -> list[dict[str, Any]]:
    names = [c.name for c in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def fetch(conn, *, since: datetime, until: datetime, tenant: str | None) -> tuple[list, list, dict[str, str], list[str]]:
    missing: list[str] = []
    decisions: list[dict[str, Any]] = []
    shadows: list[dict[str, Any]] = []
    tenant_sql = " AND tenant_id = %s" if tenant else ""
    args = [since, until, *([tenant] if tenant else [])]
    with conn.cursor() as cur:
        if _exists(cur, "activity_llm_decisions"):
            cur.execute("SELECT decided_at, case_id, kind, mode, outcome, code_result, llm_result, served_result, changed, "
                        "reason, reason_guard, failure_code, error, latency_ms, model FROM activity_llm_decisions "
                        f"WHERE decided_at >= %s AND decided_at < %s{tenant_sql} ORDER BY decided_at", args)
            decisions = _rows(cur)
        else:
            missing.append("activity_llm_decisions")
        if _exists(cur, "activity_judge_shadow"):
            cur.execute("SELECT created_at, case_id, kind, event, rule_value, llm_value, agree, comparable, llm_failure_code "
                        "FROM activity_judge_shadow WHERE origin = 'live' AND created_at >= %s AND created_at < %s"
                        f"{tenant_sql} ORDER BY created_at", args)
            shadows = _rows(cur)
        else:
            missing.append("activity_judge_shadow")
        ids: set[str] = set()
        for r in decisions:
            for part in (r.get("code_result"), r.get("llm_result"), r.get("served_result")):
                order = (part or {}).get("order") if isinstance(part, dict) else None
                ids.update(str(x) for x in order or [])
        titles: dict[str, str] = {}
        if ids:
            cur.execute("SELECT DISTINCT ON (content_id) content_id, title FROM place_catalog WHERE content_id = ANY(%s) "
                        "ORDER BY content_id, fetched_at DESC", (sorted(ids),))
            titles = {str(cid): title for cid, title in cur.fetchall()}
    return decisions, shadows, titles, missing


def _source_label(url: str) -> str:
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    return f"{parsed.hostname or '?'}/{(parsed.path or '').lstrip('/') or '?'}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    today = datetime.now(KST).date()
    parser.add_argument("--since", type=date.fromisoformat, default=today - timedelta(days=7), help="시작 날짜(KST, 포함)")
    parser.add_argument("--until", type=date.fromisoformat, default=today, help="끝 날짜(KST, 포함)")
    parser.add_argument("--tenant", default=None, help="한 테넌트만")
    parser.add_argument("--out", default=os.path.join(ROOT, "wiki", "records", "reports",
                                                      f"{today.isoformat()}_활동LLM_운영판정기록.md"))
    parser.add_argument("--stdout", action="store_true", help="파일을 쓰지 않고 화면에 낸다")
    parser.add_argument("--overwrite", action="store_true", help="같은 파일이 있으면 _backup 에 옮겨 두고 다시 쓴다")
    args = parser.parse_args(argv)
    until = args.until + timedelta(days=1)

    from app.core.settings import get_settings
    from app.infrastructure.db.session import get_connection

    start = datetime.combine(args.since, datetime.min.time(), KST)
    end = datetime.combine(until, datetime.min.time(), KST)
    with get_connection() as conn:
        decisions, shadows, titles, missing = fetch(conn, since=start, until=end, tenant=args.tenant)
    text = render(decisions, shadows, titles, since=args.since, until=until, generated_at=datetime.now(timezone.utc),
                  source=_source_label(get_settings().database_url), missing=missing)
    if args.stdout:
        print(text)
        return 0
    if os.path.exists(args.out):
        if not args.overwrite:
            print(f"이미 있다 — 덮어쓰려면 --overwrite: {args.out}", file=sys.stderr)
            return 2
        backup = os.path.join(os.path.dirname(ROOT), "_backup", f"{today.isoformat()}_llm_decision_report")
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(args.out, os.path.join(backup, f"{datetime.now(KST):%H%M%S}_{os.path.basename(args.out)}"))
    with open(args.out, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(text + "\n")
    print(f"썼다: {args.out} · LLM 판정 {len(decisions)}건 · 섀도 {len(shadows)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
