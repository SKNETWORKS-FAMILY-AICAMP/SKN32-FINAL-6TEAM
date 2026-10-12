# -*- coding: utf-8 -*-
"""4차 v5 — 제출 문서의 그림 세 개. 양식이 그림을 요구하는 자리(전처리 2.3, 학습 2.3, 모델 2.3)에만 둔다."""
from __future__ import annotations

import charts_v4 as CH
import content_core_v2 as K
import content_teams_v2 as T
from common_v2 import FIG_DIR


def make_figures(exp, env):
    F = {}
    D, A = T.DINING, T.ACTIVITY
    t = env["train"]
    F["pre_lanes"] = CH.lanes(FIG_DIR / "그림1_분야별_전처리흐름.png", [
        ("코어\n메시지 분류", [f"상담 사건제목\n{K.CLS['travel_rows']:,}행", "정규화·마스킹\n중복·길이 제거", f"기준 모델 라벨\n{K.CLS['labeled']:,}건", "층화 분할\n8:1:1"]),
        ("코어\n계획 읽기", ["글·사진·파일\n접수", "받아쓰기\n완전성 검사", "규칙 읽기\n남은 줄 인용", "날짜·장소 확인\n값·근거 저장"]),
        ("이동", ["시간표·환승\n공공데이터", "시각·역명\n정규화", "소스 간 대조\n역 순서 확인", "판정 참조 표\n회귀 시험 168건"]),
        ("액티비티", [f"관광지 후보\n{A['tour']}행", f"서울 주소 필터\n{A['seoul_addr'][0]}행", "중복·결측 검사\n원문 보존", "후보 목록\n(행사 제외)"]),
        ("요식업", [f"음식점 {D['tourapi_intro']}곳\n비건·할랄·미쉐린", "영업시간 문장\n구조화", "사람 정답 대조\n100곳", f"식당 목록\n{D['ledger_total']:,}곳"]),
    ])
    F["train_flow"] = CH.flow(FIG_DIR / "그림1_분류_학습평가흐름.png", [
        ("입력", "학습·검증·시험 조각\n(8:1:1, seed=7)"),
        ("처리", "기준선\nTF-IDF + 로지스틱 회귀"),
        ("처리", "인코더 파인튜닝 4종\nGPU, bfloat16"),
        ("검증", "에폭별 검증\n일치율 기록"),
        ("처리", "검증 조각 점수로\n모델 선정"),
        ("출력", "시험 조각으로 1회 보고\n부트스트랩 2,000회\n95% 신뢰구간"),
    ])
    F["deps"] = CH.flow(FIG_DIR / "그림1_학습데이터와_의존라이브러리.png", [
        ("입력", f"코어: 기준 모델 라벨\n{K.CLS['labeled']:,}건, 합성 {K.CLS['synth']}건\n(Ollama {t['ollama']})"),
        ("처리", f"PyTorch {t['torch'].split('+')[0]}\nTransformers {t['transformers']}"),
        ("출력", "SafeTensors 인코더 2종\nmetrics.json\n(제출 모델)"),
        ("입력", "이동: 판정 점검 사례\n8,648건(특징 27개)"),
        ("처리", f"scikit-learn {t['scikit_learn']}\nNumPy {t['numpy']}"),
        ("출력", "pkl(HGB v1·v2)\n미채택 비교 모델"),
    ], cols=3, snake=False, no_arrow_after=(2,))
    return F
