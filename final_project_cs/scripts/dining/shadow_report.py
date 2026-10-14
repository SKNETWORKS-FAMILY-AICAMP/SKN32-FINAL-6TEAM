# -*- coding: utf-8 -*-
"""요식 판정 에이전트 그림자 기록(`dining.dn_agent_shadow`, 232)을 센다 — 규칙과 같은 비율 · 어긋난 줄 · 실행 실패. `[2026-10-13 · 설계 §10 단계 5]`

    python -m scripts.dining.shadow_report --dsn postgresql://postgres@127.0.0.1:5433/<DB> [--days 7] [--show 20]

★어긋남은 「누가 틀렸나」가 아니다 — 체크별로 모아 사람이 분류한다(설계 §10 단계 5 「어긋남 분류」). 스위치(설계 단계 6)는 이 수치를 보고 팀이 정한다.
"""
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--show", type=int, default=20, help="어긋난 줄을 몇 개 보일까")
    args = parser.parse_args(argv)
    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        since = "created_at >= now() - make_interval(days => %s)"
        cur.execute(f"SELECT count(DISTINCT run_id), count(*) FILTER (WHERE check_code = '_run' AND failure IS NOT NULL), "
                    f"round(avg((detail->>'seconds')::numeric) FILTER (WHERE check_code = '_run'), 1) "
                    f"FROM dining.dn_agent_shadow WHERE {since}", (args.days,))
        runs, failed, seconds = cur.fetchone()
        print(f"최근 {args.days}일 — 실행 {runs}회 · 실행 실패 {failed} · 평균 {seconds}초")
        cur.execute(f"SELECT check_code, count(*) FILTER (WHERE agree), count(*) FILTER (WHERE agree IS NOT NULL), "
                    f"count(*) FILTER (WHERE failure IS NOT NULL), count(*) "
                    f"FROM dining.dn_agent_shadow WHERE {since} AND check_code <> '_run' GROUP BY 1 ORDER BY 1", (args.days,))
        print("체크          같음/비교      검증실패  전체")
        for code, same, compared, invalid, total in cur.fetchall():
            rate = f"{same}/{compared} = {same / compared:.0%}" if compared else "비교 없음(규칙 검사에 없는 체크)"
            print(f"  {code:<12} {rate:<16} {invalid:>6}  {total:>5}")
        cur.execute(f"SELECT created_at::date, intake_id, item_id, check_code, agent_verdict, rule_verdict, detail->>'reason', failure "
                    f"FROM dining.dn_agent_shadow WHERE {since} AND agree IS FALSE ORDER BY created_at DESC LIMIT %s",
                    (args.days, args.show))
        rows = cur.fetchall()
        if rows:
            print("어긋난 줄(최근부터)")
        for day, intake, item, code, agent, rule, reason, failure in rows:
            print(f"  {day} {str(intake)[:8]} {item} {code}: 에이전트 {agent} · 규칙 {rule} — {reason or ''} {failure or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
