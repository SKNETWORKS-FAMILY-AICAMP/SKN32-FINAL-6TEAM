# -*- coding: utf-8 -*-
"""이동 모듈 평가 지표 — 근거 충실도와 **근거 보존율**을 숫자로 낸다. 2026-09-13.

멘토 피드백 ⑦(에이전트 평가 기준을 수치 점수로)에 대한 답의 일부다.
판정 코드는 건드리지 않는다 — `verify_time.py --json` 출력을 읽어 집계할 뿐이다.

    python scripts/mobility_metrics.py                 # 회귀 5묶음을 돌려 집계
    python scripts/mobility_metrics.py --from a.json b.json   # 이미 있는 --json 출력을 집계

★ 근거 보존율이 이 스크립트의 핵심이다.
  코어는 `answer` 와 `evidence` 만 저장한다(아키텍처 v2). 우리 판정 상세는 전부 `decisions[]` 에
  있어 **저장 단계에서 버려진다.** 그래서 "판정이 만든 정보 단위 중 코어에 남는 비율"을 잰다.
    · 접기 전 = 소스 근거(evidence)만 남는다
    · 접기 후 = 판정 상세를 Evidence.value 로 올리므로 전부 남는다
  이 숫자를 0 에서 100 으로 올리는 것이 접기 작업의 값어치다.
"""
import argparse
import collections
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
T = REPO / "tests" / "mobility"
MINI = T / "mini_timetable_v2.jsonl"
RUNS = [("real_legs_v1.json", None), ("bus_legs_v1.json", None), ("alt_legs_v1.json", None),
        ("issue_legs_v1.json", None), ("synthetic_legs_v1.json", MINI)]
GRADES = ("확정", "추정", "근거없음")
# ★ 판정 어휘가 두 곳에서 다르다 — 판정기는 feasible/infeasible, 저장소(mob_leg_verdict CHECK)는 ok/fail.
#   접기(fold_result)가 매핑해야 할 자리다. 여기서는 읽기 좋게 한국어로만 바꾼다.
MARK = {"feasible": "성립", "infeasible": "불가", "rejected_by_limit": "탈락", "unknown": "근거없음"}


def run_all(outdir):
    """회귀 5묶음을 돌려 --json 을 모은다.

    ★ 파이프로 넘기면 자식 파이썬의 stdout 인코딩이 콘솔 로캘(윈도우는 cp949)이 된다.
      한국어 출력이 거기서 죽어 **종료코드 1** 이 나고, MISS 와 구별되지 않는다(2026-09-13 에 겪음).
      → 자식에게 PYTHONIOENCODING=utf-8 을 준다. 읽을 때도 errors='replace' 로 받는다.
    """
    import os
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONPATH=str(REPO / "final_project_cs"))
    paths, t0, bad = [], time.time(), []
    for fn, tt in RUNS:
        out = outdir / (fn.replace(".json", "_result.json"))
        if out.exists():
            out.unlink()
        cmd = [sys.executable, "-m", "app.infrastructure.travel.mobility.verify_time",
               "--cases", str(T / fn), "--json", str(out), "--check-expect"]
        if tt:
            cmd += ["--timetable", str(tt)]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        if not out.exists():
            # 판정이 아예 안 돌았다. MISS 와 다른 종류의 실패다 — 조용히 넘기지 않는다.
            print(f"  ✗ {fn} 실행 실패(종료코드 {r.returncode}) — 판정 결과 파일이 없다")
            print("    " + ((r.stderr or r.stdout or "").strip().splitlines() or ["(출력 없음)"])[-1])
            bad.append(fn)
            continue
        if r.returncode != 0:
            print(f"  ⚠ {fn} 기대 대조 MISS — 지표를 내기 전에 고칠 것")
            for ln in (r.stdout or "").splitlines():
                if "MISS" in ln:
                    print("    " + ln.strip())
        paths.append(out)
    if bad:
        sys.exit(f"실행 실패 {len(bad)}건 — 지표를 내지 않는다. 부분 결과로 낸 숫자는 근거가 아니다.")
    return paths, time.time() - t0


def units_of(c):
    """판정 한 건이 만든 '정보 단위'를 센다. 각각이 사라지면 답이 나빠지는 것들이다."""
    u = collections.OrderedDict()
    u["판정"] = 1
    u["근거등급"] = 1
    u["사유"] = 1 if c.get("reason") else 0
    u["완화조건"] = 1 if c.get("relief") else 0
    u["도착시각"] = 1 if c.get("arrive_min") is not None else 0
    u["여유분"] = 1 if c.get("slack_min") is not None else 0
    u["경고"] = len(c.get("warnings") or [])
    u["대안"] = len(c.get("alternatives") or [])
    u["구간판정"] = len(c.get("legs") or [])
    u["소스근거"] = len(c.get("evidence") or [])
    return u


def main():
    ap = argparse.ArgumentParser(description="이동 모듈 평가 지표")
    ap.add_argument("--from", dest="src", nargs="*", help="verify_time --json 출력 경로들")
    ap.add_argument("--out", default=str(REPO / "mobility_metrics.md"))
    a = ap.parse_args()

    if a.src:
        paths, secs = [Path(x) for x in a.src], None
    else:
        paths, secs = run_all(REPO / ".metrics")

    cases = []
    for p in paths:
        cases += json.loads(Path(p).read_text(encoding="utf-8"))
    if not cases:
        sys.exit("판정 결과가 0건이다 — 씨앗을 못 읽은 것이다. 통과가 아니라 실패다.")

    tot = collections.Counter()
    for c in cases:
        for k, v in units_of(c).items():
            tot[k] += v
    units = sum(tot.values())
    src_ev = tot["소스근거"]

    ev_grade = collections.Counter()
    for c in cases:
        for e in c.get("evidence") or []:
            ev_grade[e.get("grade", "?")] += 1
    v_grade = collections.Counter(c.get("grade", "?") for c in cases)
    verdicts = collections.Counter(c.get("verdict", "?") for c in cases)
    warn_codes = collections.Counter()
    for c in cases:
        for w in c.get("warnings") or []:
            warn_codes[w["code"] if isinstance(w, dict) else "(문자열)"] += 1
        for al in c.get("alternatives") or []:
            for w in al.get("warnings") or []:
                warn_codes[w["code"] if isinstance(w, dict) else "(문자열)"] += 1

    n = len(cases)
    L = []
    L.append("# 이동 모듈 평가 지표\n")
    # ★ 초를 적지 않는다(2026-09-14 · 굳은 결정). 같은 기기·같은 명령이 103.3 · 57.0 · 161.7초로 나왔다.
    #   이 파일은 실행마다 덮어써지므로, 문서에 인용된 초는 다음 실행에 바로 틀려진다.
    #   응답 시간을 축으로 쓰려면 측정 조건과 함께 따로 적는다 — 생성물 머리글에는 두지 않는다.
    L.append(f"자동 생성 — `scripts/mobility_metrics.py` · 케이스 {n}건\n")
    L.append("## 1. 근거 보존율 — 코어에 남는가\n")
    L.append("| | 단위 | 보존율 |")
    L.append("|---|---|---|")
    L.append(f"| 판정이 만든 정보 단위 | {units:,} | — |")
    L.append(f"| **접기 전** — `evidence`(소스 근거)만 남는다 | {src_ev:,} | **{src_ev/units*100:.1f}%** |")
    L.append(f"| **접기 후** — 판정 상세를 `Evidence.value` 로 올린다 | {units:,} | **100.0%** |")
    L.append(f"\n버려지던 것 **{units - src_ev:,}단위** — 판정·등급·사유·완화조건·도착시각·경고·대안·구간판정.\n")
    L.append("## 2. 근거 충실도\n")
    L.append(f"- 판정 1건당 소스 근거 **{src_ev/n:.2f}건**")
    tot_ev = sum(ev_grade.values()) or 1
    L.append("- 근거 등급 분포 — " + " · ".join(
        f"{g} {ev_grade.get(g,0)}건({ev_grade.get(g,0)/tot_ev*100:.1f}%)" for g in GRADES))
    L.append("- 판정 등급 분포 — " + " · ".join(
        f"{g} {v_grade.get(g,0)}건({v_grade.get(g,0)/n*100:.1f}%)" for g in GRADES))
    L.append("")
    L.append("## 3. 판정 분포\n")
    L.append(" · ".join(f"{MARK.get(k, k)} {v}건" for k, v in verdicts.most_common()))
    unknown = verdicts.get("unknown", 0)
    L.append(f"\n- **모르는 것을 모른다고 낸 비율 {unknown/n*100:.1f}%** — 다른 팀이 낼 수 없는 축이다.")
    L.append("  단순 LLM 호출은 이 값을 0 으로 만든다(모른다고 하지 않는다).\n")
    L.append("## 4. 경고 코드별 발생\n")
    L.append("| 코드 | 건수 |")
    L.append("|---|---|")
    for c_, v in warn_codes.most_common():
        L.append(f"| `{c_}` | {v} |")
    L.append("\n## 세는 방법\n")
    L.append("- **정보 단위** = 판정 1 + 근거등급 1 + 사유 + 완화조건 + 도착시각 + 여유분 + 경고 n + 대안 n + 구간판정 n + 소스근거 n")
    L.append("- **접기 전 보존율** = 소스근거 ÷ 정보 단위. 코어가 `evidence` 만 저장하고 `decisions` 를 버리기 때문이다")
    L.append("- 이 파일은 회귀를 돌려 만든다. **숫자마다 재현 명령이 있다** — `python scripts/mobility_metrics.py`")

    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:24]))
    print(f"\n보고서 → {a.out}")


if __name__ == "__main__":
    main()
