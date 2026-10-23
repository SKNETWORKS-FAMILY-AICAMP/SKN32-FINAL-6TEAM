# -*- coding: utf-8 -*-
"""4차 v4 — 세 문서의 그림. 폭 6.4인치 · 300dpi · 글자 9.5pt 이상 · 흐름도 6노드 이하."""
from __future__ import annotations

import charts_v4 as CH
import content_core_v2 as K
import content_teams_v2 as T
from common_v2 import FIG_DIR
from mob_data import MOB


def make_figures(exp, env):
    F = {}
    D, A, E = T.DINING, T.ACTIVITY, K.EVAL60
    e5 = D["e5"]
    t = env["train"]

    # ── 전처리 결과서 ────────────────────────────────────────
    F["cls_flow"] = CH.flow(FIG_DIR / "그림_분류데이터_전처리흐름.png", [
        ("입력", f"공정위 소비자상담 원천\n{K.CLS['rows_read']:,}행"),
        ("처리", f"여행 서비스 {K.CLS['has_data']}개 품목\n{K.CLS['travel_rows']:,}행 선별"),
        ("처리", f"정규화·마스킹·중복·길이\n제거, 고유 {K.CLS['unique']:,}건"),
        ("처리", f"품목별 최대 400건\n표본 {K.CLS['pool']:,}건"),
        ("처리", f"교사(Gemma 4 12B) 라벨\n확정 {K.CLS['labeled']:,}건"),
        ("출력", "라벨 기준 층화 분할\n8:1:1 (seed=7)"),
    ])
    F["plan_flow"] = CH.flow(FIG_DIR / "그림_고객계획_읽기흐름.png", [
        ("입력", "글·사진·PDF·docx·xlsx\n접수(종류는 바이트로 판별)"),
        ("처리", "파서·사진 받아쓰기\n전체+반쪽 완전성 검사"),
        ("처리", "규칙으로 먼저 읽기\n시각·일차·날짜·예약번호"),
        ("처리", "남은 줄만 LLM이 원문 조각\n인용(원문에 없으면 버림)"),
        ("처리", "날짜·장소 해석\n우리 표>오타>관광공사>카카오"),
        ("출력", "확인 화면·등록\n값마다 방법·근거 저장"),
    ])
    F["eval_format"] = CH.hbar(FIG_DIR / "그림_계획읽기_평가셋_형식별.png", [(n, v, CH.ORANGE if v < 95 else CH.BLUE) for n, v in E["by_format"]],
                              xmax=100, xlabel="항목 재현율(%), 2회차, 합성 60건(전체 326/336 = 97.0%)", target=(95, "목표 95%"))
    F["mob_flow"] = CH.flow(FIG_DIR / "그림_이동_전처리흐름.png", [
        ("입력", "공공 API 6종·파일 3종\n수집일 기록"),
        ("처리", "정규화\n분 단위 시각·정규 역명"),
        ("처리", "버스 구간 통행시간 표\n100일·구간 99.2%"),
        ("검증", "소스 간 대조 C1~C6\n역 순서 777간선"),
        ("처리", "적재\n참조 표 + 산출 표"),
        ("검증", f"회귀 168건\n탐침 {MOB['probes']:,}건"),
    ])
    F["activity_flow"] = CH.flow(FIG_DIR / "그림_액티비티_전처리흐름.png", [
        ("입력", f"TourAPI 서울 관광지\n후보 {A['tour']}행"),
        ("처리", f"서울 주소 필터\n{A['seoul_addr'][0]}/{A['seoul_addr'][1]}행"),
        ("검증", "중복·결측 검사\ncontentid 충돌 0"),
        ("처리", "신분류(lclsSystm1) 확인\n영업시간·휴무는 원문 그대로"),
        ("처리", f"서울 밖 좌표 {A['out_of_box']}행은\n적재 때 NULL"),
        ("출력", "적재 스크립트\nEV 제외 권장"),
    ])
    F["dining_flow"] = CH.flow(FIG_DIR / "그림_요식_전처리흐름.png", [
        ("입력", f"서울 음식점 목록 {D['tourapi_list']}곳\n소개정보 {D['tourapi_intro']}곳"),
        ("처리", f"문장 구조화\n영업 구간 {D['intervals'][0]}/{D['intervals'][1]}곳\n휴무 규칙 {D['rules']}곳"),
        ("검증", f"사람 정답 대조 100곳\n{D['truth_before']}%에서 {D['truth_after']}%"),
        ("입력", f"새 원천 4종: 비건 {D['vegan']['rows']}행\n할랄 {D['halal']['rows']}행·미쉐린 {D['michelin']['total']}곳\n노키즈 시트 {D['nokids']['sheet']}곳"),
        ("처리", f"속성·신규 장소 병합\n미쉐린 속성 {D['michelin']['matched']}곳\n신규 {D['michelin']['new']}곳"),
        ("출력", f"원장 {D['michelin']['ledger_before']:,}곳에서\n{D['ledger_total']:,}곳"),
    ])

    # ── 학습 결과서 ──────────────────────────────────────────
    lab = {r["exp"]: r for r in exp["intent"] + exp["issue_code"]}
    tuned = {"intent": (9, 10, 11, 12, 13), "issue_code": (17, 18, 19, 20, 21)}
    names = ["TF-IDF", "A.X-Encoder", "mmBERT", "kf-deberta(선정)", "Qwen3-Embedding"]
    colors = [CH.GRAY, CH.AQUA, CH.ORANGE, CH.BLUE, "#4A3AA7"]
    F["train_flow"] = CH.flow(FIG_DIR / "그림_분류_학습평가흐름.png", [
        ("입력", "전처리 조각\n학습·검증·시험"),
        ("처리", "기준선\nTF-IDF + 로지스틱 회귀"),
        ("처리", "인코더 파인튜닝 4종\nGPU, bfloat16"),
        ("검증", "에폭별 검증\n정확도 기록"),
        ("처리", "검증 조각 점수로\n모델 선정"),
        ("출력", "시험 조각은 선정 뒤\n1회 보고, 부트스트랩\n2,000회 95% 신뢰구간"),
    ])
    ax_int = {r["run_key"]: r for r in exp["intent"] if r["model"] == "skt/A.X-Encoder-base"}
    ax_iss = {r["run_key"]: r for r in exp["issue_code"] if r["model"] == "skt/A.X-Encoder-base"}
    F["tuning"] = CH.grouped(FIG_DIR / "그림_가중조정_전후.png", ["요청 종류 A.X 검증", "문제 코드 A.X 검증"],
                             [("첫 판(빈도 역수 가중 상한 20, 4에폭)", CH.GRAY, [ax_int["p1_real_only"]["valid"], ax_iss["p1_real_only"]["valid"]]),
                              ("조정판(제곱근 가중 상한 5, 8에폭, 배치 16)", CH.BLUE, [ax_int["p1b_real_tuned"]["valid"], ax_iss["p1b_real_tuned"]["valid"]])],
                             xmax=1.0, xlabel="검증 정확도", height=3.4, legend_cols=1)
    F["methods"] = CH.hbar(FIG_DIR / "그림_계획읽기_방식선정.png",
                           [(n.replace(" 사진을 ", "\n사진을 ").replace("받아쓴 글을 ", "받아쓴 글을\n") if len(n) > 20 else n, k, CH.ORANGE if (k < d or "스키마" in n) else CH.BLUE)
                            for n, k, d, note in K.PLAN_METHODS],
                           xmax=6, fmt="{:.0f}/6", xlabel="시각 항목 6개 중 맞게 읽은 수(합성 사진 1장, 방식마다 1회)\n주황은 실패·변조가 섞인 방식", height=3.8)
    F["mob_ml"] = CH.hbar(FIG_DIR / "그림_이동_ML대조.png", [
        ("다수결 기준선", MOB["ml"]["majority"], CH.GRAY, "탐침 8,648건"),
        ("로지스틱 회귀", MOB["ml"]["logreg"][0], CH.BLUE, f"±{MOB['ml']['logreg'][1]:.3f}"),
        ("MLP 64-32", MOB["ml"]["mlp"][0], CH.BLUE, f"±{MOB['ml']['mlp'][1]:.3f}"),
        ("HistGradientBoosting v1", MOB["ml"]["hgb"][0], CH.BLUE, f"±{MOB['ml']['hgb'][1]:.3f}"),
    ], xmax=1.0, fmt="{:.3f}", xlabel="판정 일치 정확도(구간 단위 GroupKFold 5폴드 x 시드 5, 같은 탐침 8,648건)", height=2.9)
    F["e5"] = CH.grouped(FIG_DIR / "그림_요식_대체유사도.png", ["분류 일치@3(157곳)", "태그 없는 11곳 일치@3", "보기 맞추기 hit@5"],
                         [("규칙(태그)", CH.GRAY, [e5["rule"]["top3"], None, None]),
                          ("e5 그대로", CH.AQUA, [e5["raw"]["top3"], e5["raw"]["notag"], e5["raw"]["hit5"]]),
                          ("e5 학습(미세조정)", CH.BLUE, [e5["tuned"]["top3"], e5["tuned"]["notag"], e5["tuned"]["hit5"]])],
                         xmax=1.0, xlabel="시험 173곳, 1회. 분류 일치는 대리 지표(분류도 메뉴에서 규칙으로 뽑음)", height=4.0)
    F["e5_flow"] = CH.flow(FIG_DIR / "그림_요식_임베딩학습흐름.png", [
        ("입력", "관광공사 음식점 980곳\n8:2 분할\n(학습 807·시험 173)"),
        ("처리", f"짝 만들기\n상호+대표메뉴 / 취급메뉴\n(둘 다 있는 {e5['train']}곳)"),
        ("처리", f"InfoNCE 대조학습\n{e5['epochs']}에폭·배치 {e5['batch']}·lr {e5['lr']}\nCPU {e5['secs']}초"),
        ("검증", f"시험 {e5['test']}곳\n(분류 산정 {e5['scored']}곳)\n세 방법 비교"),
        ("검증", "사람 판정 시트 237행\n(아직 비어 있음)"),
        ("출력", "제품에는 미적용"),
    ])

    # ── 모델 문서 ────────────────────────────────────────────
    F["deps"] = CH.flow(FIG_DIR / "그림_학습데이터와_의존라이브러리.png", [
        ("입력", f"코어: 사건제목 교사 라벨\n{K.CLS['labeled']:,}건 + 합성 {K.CLS['synth']}건\n(교사 Ollama {t['ollama']})"),
        ("처리", f"PyTorch {t['torch'].split('+')[0]}\nTransformers {t['transformers']}"),
        ("출력", "SafeTensors 인코더 2종\nmetrics.json\n(제출 모델)"),
        ("입력", "이동: 탐침 8,648건\n(특징 27개)"),
        ("처리", f"scikit-learn {t['scikit_learn']}\nNumPy {t['numpy']}"),
        ("출력", "pkl(HGB v1·v2)\n미채택 비교 모델"),
    ], cols=3, snake=False, no_arrow_after=(2,))
    F["infer"] = CH.flow(FIG_DIR / "그림_제품분류와_로컬모델.png", [
        ("입력", "고객 메시지"),
        ("처리", "제품 분류: Gemma 4 12B\n(없으면 OpenAI)"),
        ("출력", "제품 분류·\n후속 라우팅"),
        ("입력", "제출 kf-deberta-base\n요청 종류·문제 코드"),
        ("검증", "로컬 어댑터\n계약 시험"),
        ("출력", "제품 분류 조립에는\n연결되지 않음"),
    ], cols=3, snake=False, no_arrow_after=(2,))
    return F
