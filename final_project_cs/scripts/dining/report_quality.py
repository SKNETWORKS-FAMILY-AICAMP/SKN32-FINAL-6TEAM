"""품질 측정 결과를 문서로 뽑는다.

숫자를 손으로 적은 문서는 다음 실행에 바로 거짓말이 된다.
그래서 DB 에서 읽어 그때그때 만든다. 이 파일이 아니라 원장이 사실이다.

    python scripts/dining/report_quality.py            화면에 보인다
    python scripts/dining/report_quality.py --save     파일로도 남긴다

출력: data/dining/_build/품질리포트.md
"""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "data", "dining", "_build")


def connect():
    import psycopg
    dsn = os.environ.get("DINING_DSN")
    if not dsn:
        try:
            sys.path.insert(0, ROOT)
            from app.infrastructure.db.session import database_dsn
            dsn = database_dsn()
        except Exception as exc:                        # noqa: BLE001
            raise SystemExit(f"접속 주소를 찾지 못했다: {exc}") from exc
    return psycopg.connect(dsn)


def main() -> int:
    L: list[str] = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT run_id, rules_version, started_at, 정답건수, 맞음, 틀림, 모름, 정확도
            FROM dining.v_quality_summary WHERE metric = 'reality'
            ORDER BY started_at DESC LIMIT 10""")
        runs = cur.fetchall()
        if not runs:
            raise SystemExit("채점한 적이 없다. run_quality.py 를 먼저 돌려라.")

        cur.execute("SELECT now()")
        now = cur.fetchone()[0]

        L += [f"# 요식 원장 품질 — {now:%Y-%m-%d %H:%M}", "",
              "생성 문서다. 직접 고치지 않는다. 숫자는 원장에서 그때그때 읽는다.", "",
              "## 무엇을 재는가", "",
              "지표 둘을 섞지 않는다. 섞으면 관광공사가 틀린 것이 우리 오류율로 들어온다.", "",
              "| 지표 | 묻는 것 | 우리가 고칠 수 있나 | 어디서 재나 |",
              "|---|---|---|---|",
              "| 원장 정확도 | 지금 원장이 실제 가게와 맞는가 | 예. 확인해서 넣으면 된다 | 이 문서 |",
              "| 파서 정확도 | 원문을 제대로 읽었는가 | 예. 파서를 고치면 된다 | 회귀 시험 |", ""]

        rid, ver, at, n, ok, bad, unk, acc = runs[0]
        L += ["## 지금", "",
              f"- 정확도 **{acc}%**  (맞음 {ok} / 틀림 {bad} / 모름 {unk}, 정답 {n}건)",
              f"- 버전 `{ver}`",
              f"- 잰 시각 {at:%Y-%m-%d %H:%M}", "",
              "모름은 분모에서 뺀다. 판정이 나지 않은 것을 틀림으로 세면",
              "정답을 늘릴수록 점수가 떨어진다.", ""]

        if len(runs) >= 2:
            prev = runs[1]
            cur.execute("SELECT change, name_ko, check_kind, prev, cur "
                        "FROM dining.quality_delta_runs(%s, %s)", (prev[0], rid))
            rows = cur.fetchall()
            counts: dict[str, int] = {}
            for r in rows:
                counts[r[0]] = counts.get(r[0], 0) + 1

            L += ["## 직전 실행과 비교", "",
                  f"`{prev[2]:%m-%d %H:%M}` {prev[7]}% → `{at:%m-%d %H:%M}` {acc}%", "",
                  "| 무엇 | 몇 건 |", "|---|---|"]
            order = ["깨짐", "맞음에서 모름", "고쳐짐", "모름에서 맞음",
                     "모름에서 틀림", "그대로 틀림", "틀림에서 모름",
                     "그대로 모름", "그대로 맞음"]
            for k in order:
                if counts.get(k):
                    mark = " ⚠" if k in ("깨짐", "맞음에서 모름") else ""
                    L.append(f"| {k}{mark} | {counts[k]} |")
            L += ["",
                  "**깨진 것을 먼저 본다.** 셋을 고치고 하나가 깨져도 총량은 늘어서",
                  "숫자만 보면 보이지 않는다.", ""]

            moved = [r for r in rows if r[0] in ("고쳐짐", "깨짐", "맞음에서 모름")]
            if moved:
                L += ["### 바뀐 것", "", "| 무엇 | 상호 | 항목 |", "|---|---|---|"]
                for change, name, kind, _, _ in moved:
                    L.append(f"| {change} | {name} | {kind} |")
                L.append("")

        cur.execute("""
            SELECT p.name_ko, t.check_kind, q.detail
            FROM dining.dn_quality_result q
            JOIN dining.dn_truth t ON t.truth_id = q.truth_id
            JOIN dining.dn_place p ON p.place_uid = t.place_uid
            WHERE q.run_id = %s AND q.verdict <> 'match'
            ORDER BY q.verdict, p.name_ko""", (rid,))
        left = cur.fetchall()
        L += ["## 아직 남은 것", ""]
        if left:
            L += ["| 상호 | 항목 | 왜 |", "|---|---|---|"]
            for name, kind, detail in left:
                L.append(f"| {name} | {kind} | {detail} |")
        else:
            L.append("없다.")
        L.append("")

        cur.execute("""
            SELECT metric, count(*), min(verified_at), max(verified_at),
                   count(DISTINCT entered_by), min(evidence)
            FROM dining.dn_truth WHERE retired_at IS NULL GROUP BY 1""")
        L += ["## 정답셋", "", "| 지표 | 건수 | 확인 시각 | 확인한 사람 |", "|---|---|---|---|"]
        evidences = []
        for metric, cnt, lo, hi, who, ev in cur.fetchall():
            when = f"{lo:%Y-%m-%d}" if lo == hi else f"{lo:%Y-%m-%d} ~ {hi:%Y-%m-%d}"
            L.append(f"| {metric} | {cnt} | {when} | {who}명 |")
            evidences.append(ev)
        L.append("")
        for ev in evidences:
            L += [f"> {ev}", ""]
        L += ["이 전제를 확인할 수 있어야 한다. 「표시 없음」을 「안 봤음」으로 읽으면",
              "숫자가 통째로 달라진다.", ""]

        cur.execute("""
            SELECT source_code, count(*) FROM dining.v_hours_rule_active
            GROUP BY 1 ORDER BY 2 DESC""")
        L += ["## 지금 판정에 쓰이는 출처", "", "| 출처 | 규칙 |", "|---|---|"]
        for src, cnt in cur.fetchall():
            L.append(f"| {src} | {cnt} |")
        cur.execute("""
            SELECT count(*) FROM dining.dn_hours_rule WHERE retired_at IS NOT NULL""")
        L += ["", f"물러난 규칙 {cur.fetchone()[0]}건. 지우지 않으므로 무엇이 어떻게",
              "틀렸었는지 그대로 조회할 수 있다.", ""]

        cur.execute("""
            SELECT count(*) FROM dining.dn_place p
            WHERE NOT EXISTS (SELECT 1 FROM dining.dn_truth t
                               WHERE t.place_uid = p.place_uid AND t.retired_at IS NULL)""")
        gap = cur.fetchone()[0]
        L += ["## 한계", "",
              f"- 정답이 없는 곳이 {gap}곳이다. 정답셋은 200곳 중 일부만 덮는다.",
              "- 이 문서의 숫자는 원장이 실제와 얼마나 맞는가이며 파서 실력이 아니다.",
              "- 원장이 좋아져도 파서는 그대로다. 파서는 회귀 시험으로 따로 본다.", "",
              "## 다시 뽑는 법", "", "```bash",
              "python scripts/dining/run_quality.py      # 채점하고 기록",
              "python scripts/dining/run_quality.py --delta   # 최근 두 실행 비교",
              "python scripts/dining/report_quality.py --save # 이 문서",
              "```", ""]

    text = "\n".join(L)
    print(text)
    if "--save" in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "품질리포트.md")
        open(path, "w", encoding="utf-8").write(text)
        print(f"\n저장: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
