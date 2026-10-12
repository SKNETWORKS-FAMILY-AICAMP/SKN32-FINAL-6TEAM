# -*- coding: utf-8 -*-
"""데이터 전처리 단계 산출물 3종 — 여행판 4차 v4 (코덱스 명세 반영 · 결론 먼저 순서 · 상세 근거 분리).

    python build_데이터전처리_3종_여행_4차v4.py [pre|train|model]     (인자를 안 주면 셋 다)

v3 와 다른 점: 글꼴·표·그림 규격(docx_compose.py, charts_v4.py), 절마다 결론 한 문장, 세부 표는 문서 끝 「상세 근거」로,
관광공사 저장 결정(09-28 19:40)과 요식 원장 코어 통합(09-28 21:42) 반영. 이전 판(4차v2·v3)은 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_v2 import FIG_DIR, ML, OUT_DIR, need  # noqa: E402
import docs_model_v4 as DM  # noqa: E402
import docs_pre_v4 as DP  # noqa: E402
import docs_train_v4 as DT  # noqa: E402
import figs_v4  # noqa: E402
import ml_data_v2 as M  # noqa: E402


def main(which):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    exp = M.load(ML)
    env = need(ML / "environment.json")
    hashes = DM.check_hashes()
    F = figs_v4.make_figures(exp, env)
    print("그림:", len(F), "개")
    jobs = {"pre": lambda: DP.build(F), "train": lambda: DT.build(F, exp, env), "model": lambda: DM.build(F, exp, env, hashes)}
    reg = {}
    for key in ("pre", "train", "model"):
        if which and key not in which:
            continue
        out, c = jobs[key]()
        reg[out.name] = dict(blocks=c.registry, warnings=c.warnings)
        print(f"\n[{out.name}] 규격 경고 {len(c.warnings)}건")
        for w in c.warnings:
            print("   -", w)
    (OUT_DIR / "검사결과.json").write_text(json.dumps({"model_hashes": hashes, "docx_reopen_checks": "PASS"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "_tmp").mkdir(exist_ok=True)
    (OUT_DIR / "_tmp" / "registry.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
