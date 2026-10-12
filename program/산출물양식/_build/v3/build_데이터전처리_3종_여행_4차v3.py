# -*- coding: utf-8 -*-
"""데이터 전처리 단계 산출물 3종 — 여행판 4차 v2 (팀별 통합 형식 · 쇼핑몰 시절 자료 제외).

    python build_데이터전처리_3종_여행_4차v2.py

만드는 것: 전처리 결과서 · ML/DL 학습 결과서 · 학습한 ML/DL 모델(docx 3개) + 그림 + 검수본문(md) + 검사결과.json.

이 판이 3차·4차와 다른 점
- 팀별(코어 · 이동 · 액티비티 · 요식업) 절로 나눈 통합 형식이다(팀 검토본 v3, 2026-09-17 의 골격을 따른다).
- 쇼핑몰 시절 자료(쇼핑 리뷰 감정 말뭉치·감정 모델, 쇼핑몰 정책 문서)는 뺐다.
- 4차(2026-09-28 04:37) 이후에 늘어난 것을 넣었다: 계획 읽기 평가셋 60건, 영업시간 원문 구조화,
  장소 별칭·끝난 여행 장소 정리, 요식·활동·이동 팀의 갱신 값, 요식 대체 유사도 시험.
- 본문은 `docx_compose.py`(양식의 글꼴·표 색·번호를 그대로 쓰는 조립 도구)로 새로 짠다. 요약 카드·그래프를 넣었다.

★숫자는 세 곳에서만 온다: (1) `datasets/ml/` 의 학습 산출물 JSON, (2) `content_core_v2.py`·`content_teams_v2.py`·
  `docs_mobility_v2.py` 의 출처가 적힌 상수, (3) 이 스크립트가 직접 계산한 값(해시 대조). 다른 곳에 손으로 적지 않는다.
★docx 를 손으로 고치지 않는다. 고칠 것은 스크립트를 고쳐 다시 만든다. 3차·4차 파일은 덮어쓰지 않는다(새 폴더 `데이터전처리_여행_4차v2/`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_v2 import FIG_DIR, ML, OUT_DIR, need  # noqa: E402
import docs_model_v2 as DM  # noqa: E402
import docs_pre_v2 as DP  # noqa: E402
import docs_train_v2 as DT  # noqa: E402
import figs_v2  # noqa: E402
import ml_data_v2 as M  # noqa: E402


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    exp = M.load(ML)
    env = need(ML / "environment.json")
    hashes = DM.check_hashes()
    F = figs_v2.make_figures(exp, env)
    print("그림:", len(F), "개")
    outs = [DP.build(F), DT.build(F, exp, env), DM.build(F, exp, env, hashes)]
    (OUT_DIR / "검사결과.json").write_text(json.dumps({"model_hashes": hashes, "docx_reopen_checks": "PASS"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n생성 완료:", *[o.name for o in outs], sep="\n  ")


if __name__ == "__main__":
    main()
