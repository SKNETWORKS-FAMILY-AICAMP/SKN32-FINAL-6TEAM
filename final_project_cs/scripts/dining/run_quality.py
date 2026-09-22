"""정답셋에 대고 지금 원장을 채점한다.

한 번 돌 때마다 dn_quality_run 한 줄과 건별 결과가 쌓인다.
버전이 다른 두 실행을 비교하면 무엇이 고쳐지고 무엇이 깨졌는지 나온다.

    python scripts/dining/run_quality.py            채점하고 기록한다
    python scripts/dining/run_quality.py --dry      기록하지 않고 결과만 본다
    python scripts/dining/run_quality.py --delta 이전버전 현재버전

무엇을 재는가 (metric='reality')
    「지금 원장이 실제 가게와 맞는가」를 잰다.

    관광공사 원문만 들어 있는 곳은 원문이 실제와 같았는지가 곧 답이다.
    사람이나 기계가 확인해 넣은 값이 있으면 실제에 맞춰진 것으로 본다.
    규칙이 없으면 모름이며 틀림이 아니다. 분모에서 빠진다.

    파서가 원문을 제대로 읽었는가(metric='parse')는 다른 지표다.
    그쪽은 회귀 시험 34개가 맡는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

#: 사람이나 기계가 실제를 보고 넣은 출처. 이것이 있으면 실제에 맞춰진 것으로 본다.
CONFIRMED = ("operator_check", "auto_map_check", "customer_report")


def connect():
    import psycopg
    dsn = os.environ.get("DINING_DSN")
    if not dsn:
        try:
            sys.path.insert(0, ROOT)
            from app.infrastructure.db.session import database_dsn
            dsn = database_dsn()
        except Exception as exc:                       # noqa: BLE001
            raise SystemExit(f"접속 주소를 찾지 못했다: {exc}") from exc
    return psycopg.connect(dsn)


def current_version(cur) -> str:
    cur.execute("""
        SELECT rules_version, count(*) FROM dining.v_hours_rule_active
        GROUP BY 1 ORDER BY 2 DESC LIMIT 1""")
    got = cur.fetchone()
    if not got:
        raise SystemExit("영업 규칙이 없다. 적재를 먼저 해라.")
    return got[0]


def judge(cur, truth_id, place_uid, kind, expected) -> tuple[str, dict, str]:
    """한 건을 채점한다. 판정이 나오지 않으면 unknown 이며 틀림이 아니다."""
    if kind == "record_status":
        cur.execute("SELECT record_status FROM dining.dn_place WHERE place_uid = %s",
                    (place_uid,))
        now = cur.fetchone()[0]
        want = expected.get("record_status")
        return ("match" if now == want else "mismatch",
                {"record_status": now}, f"기대 {want}, 지금 {now}")

    # 영업시간. 어느 출처가 지금 판정을 만들고 있는가로 가른다.
    cur.execute("""
        SELECT array_agg(DISTINCT source_code) FROM dining.v_hours_rule_active
        WHERE place_uid = %s""", (place_uid,))
    sources = cur.fetchone()[0]
    if not sources:
        # 규칙이 없으면 실제와 맞는지 따질 수가 없다.
        return "unknown", {"sources": None}, "영업 규칙이 없다"

    confirmed = [s for s in sources if s in CONFIRMED]
    if confirmed:
        return "match", {"sources": sources}, f"확인된 출처로 갱신됨: {', '.join(confirmed)}"

    same = expected.get("원문이_실제와_같다")
    if same is None:
        return "unknown", {"sources": sources}, "정답에 비교할 값이 없다"
    return ("match" if same else "mismatch",
            {"sources": sources},
            "원문 그대로이며 실제와 같았다" if same else "원문 그대로인데 실제와 달랐다")


def run(dry: bool) -> int:
    with connect() as conn, conn.cursor() as cur:
        version = current_version(cur)
        cur.execute("""
            SELECT truth_id, place_uid, check_kind, expected
            FROM dining.dn_truth
            WHERE retired_at IS NULL AND metric = 'reality'""")
        truths = cur.fetchall()
        if not truths:
            raise SystemExit("정답이 없다. make_truth_sql.py 를 먼저 돌려라.")

        results = []
        for truth_id, place_uid, kind, expected in truths:
            verdict, actual, detail = judge(cur, truth_id, place_uid, kind, expected)
            results.append((truth_id, json.dumps(actual, ensure_ascii=False),
                            verdict, detail))

        tally = {"match": 0, "mismatch": 0, "unknown": 0}
        for _, _, v, _ in results:
            tally[v] += 1
        judged = tally["match"] + tally["mismatch"]

        print(f"버전 {version}")
        print(f"정답 {len(results)}건")
        print(f"  맞음 {tally['match']}   틀림 {tally['mismatch']}   모름 {tally['unknown']}")
        if judged:
            print(f"  정확도 {100.0 * tally['match'] / judged:.1f}%  (모름은 분모에서 뺀다)")

        if dry:
            print("\n--dry 이므로 기록하지 않았다.")
            return 0

        cur.execute("""
            INSERT INTO dining.dn_quality_run (rules_version, metric, tool, note)
            VALUES (%s, 'reality', 'run_quality.py', %s) RETURNING run_id""",
            (version, f"정답 {len(results)}건"))
        run_id = cur.fetchone()[0]
        cur.executemany("""
            INSERT INTO dining.dn_quality_result (run_id, truth_id, actual, verdict, detail)
            VALUES (%s, %s, %s::jsonb, %s, %s)""",
            [(run_id, t, a, v, d) for t, a, v, d in results])
        conn.commit()
        print(f"\n기록했다. run_id {run_id}")

        # 틀린 것을 보여준다. 총량만 보면 무엇을 고쳐야 할지 알 수 없다.
        cur.execute("""
            SELECT p.name_ko, q.detail
            FROM dining.dn_quality_result q
            JOIN dining.dn_truth t ON t.truth_id = q.truth_id
            JOIN dining.dn_place p ON p.place_uid = t.place_uid
            WHERE q.run_id = %s AND q.verdict = 'mismatch'
            ORDER BY p.name_ko LIMIT 20""", (run_id,))
        rows = cur.fetchall()
        if rows:
            print("\n아직 실제와 다른 곳")
            for name, detail in rows:
                print(f"  {name:22s} {detail}")
    return 0


def delta(prev: str, cur_v: str) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT change, name_ko, check_kind, prev, cur
            FROM dining.quality_delta(%s, %s, 'reality')""", (prev, cur_v))
        rows = cur.fetchall()
    if not rows:
        print("비교할 실행이 없다. 두 버전 모두 채점한 적이 있어야 한다.")
        return 1
    # 깨진 것을 맨 위에 둔다. 총량으로는 고친 것과 상쇄되어 보이지 않는다.
    order = {"깨짐": 0, "맞음에서 모름": 1, "고쳐짐": 2, "모름에서 맞음": 3,
             "모름에서 틀림": 4, "그대로 틀림": 5, "틀림에서 모름": 6,
             "그대로 모름": 7, "한쪽만 봄": 8, "그대로 맞음": 9}
    quiet = ("그대로 맞음", "그대로 모름")
    rows.sort(key=lambda r: (order.get(r[0], 99), r[1]))
    seen = None
    for change, name, kind, a, b in rows:
        if change in quiet:
            continue
        if change != seen:
            print(f"\n[{change}]")
            seen = change
        print(f"  {name:22s} {kind:14s} {a} → {b}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    print("\n" + "  ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="정답셋에 대고 원장을 채점한다.")
    ap.add_argument("--dry", action="store_true", help="기록하지 않고 결과만 본다")
    ap.add_argument("--delta", nargs=2, metavar=("이전", "현재"),
                    help="두 버전을 비교한다")
    args = ap.parse_args()
    if args.delta:
        return delta(*args.delta)
    return run(args.dry)


if __name__ == "__main__":
    raise SystemExit(main())
