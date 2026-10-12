# -*- coding: utf-8 -*-
"""4차 v2 — 세 문서의 그림을 한곳에서 만든다."""
from __future__ import annotations

import charts_v2 as CH
import content_core_v2 as K
import content_teams_v2 as T
import docs_mobility_v2 as MOB
from common_v2 import FIG_DIR


def make_figures(exp, env):
    F = {}
    D, A = T.DINING, T.ACTIVITY
    F["cls_flow"] = CH.flow(FIG_DIR / "그림_분류데이터_전처리흐름.png", [
        ("원천 · 선별", [f"공정위 소비자상담 원천\n{K.CLS['rows_read']:,}행", f"여행 서비스 {K.CLS['has_data']}개 품목\n{K.CLS['travel_rows']:,}행", f"정규화·마스킹·중복·길이 이상 제거\n고유 {K.CLS['unique']:,}건"]),
        ("표본 · 라벨 · 분할", [f"품목별 최대 400건\n표본 {K.CLS['pool']:,}건", f"교사(Gemma 4 12B) 라벨\n확정 {K.CLS['labeled']:,}건", "라벨 기준 층화 분할 8:1:1\n(seed=7)"]),
    ], note_size=9.0)
    F["plan_flow"] = CH.flow(FIG_DIR / "그림_고객계획_읽기흐름.png", [
        ("원문 처리", ["글·사진·PDF·docx·xlsx 접수\n(종류는 바이트로 가림)", "파서 · 사진 받아쓰기\n전체+반쪽 완전성 검사", "규칙으로 먼저 읽기\n시각·일차·날짜·예약번호·인원·끼니", "남은 줄만 LLM이 원문 조각 인용\n(원문에 없으면 버림)"]),
        ("해석·확인", ["날짜: 적힌 날짜 > 일차 > 상대 날짜\n없으면 첫날만 묻는다", "장소: 우리 표 > 자모 오타 > 관광공사\n> 카카오(이름만, 값은 관광공사 재확인)",
                   "확인 화면: 필수값 검사·규칙 배치\n고객이 고친 값은 별도 보존", "등록: 값마다 방법·근거 저장\n외부 장소는 그 여행 전용 행"]),
    ], note_size=8.6)
    F["eval_format"] = CH.hbar(FIG_DIR / "그림_계획읽기_평가셋_형식별.png", [(n, v, CH.ORANGE if v < 95 else CH.BLUE) for n, v in K.EVAL60["by_format"]],
                              xmax=100, xlabel="항목 재현율(%), 2회차, 합성 60건(전체 326/336 = 97.0%)", target=(95, "목표 95%"))
    F["hours"] = CH.before_after(FIG_DIR / "그림_영업시간_구조화_전후.png",
                                 [("영업시간을 아는 일정 항목\n(실데이터 2일 초안, 1회)", K.HOURS["before"][0], K.HOURS["after"][0], 10)], xlabel="개수(분모 10)")
    F["methods"] = CH.hbar(FIG_DIR / "그림_계획읽기_방식선정.png",
                           [(n, k, CH.ORANGE if (k < d or "스키마" in n) else CH.BLUE) for n, k, d, note in K.PLAN_METHODS],
                           xmax=6, fmt="{:.0f}/6", xlabel="시각 항목 6개 중 맞게 읽은 수(합성 사진 1장, 방식마다 1회). 주황은 실패 또는 변조가 섞인 방식")
    MOB.figures(F, FIG_DIR)
    F["activity_flow"] = CH.flow(FIG_DIR / "그림_액티비티_전처리흐름.png", [
        ("현재(저장소 산출물)", [f"TourAPI 서울 관광지 후보\n{A['tour']}행", f"서울 주소 필터\n{A['seoul_addr'][0]}/{A['seoul_addr'][1]}행", "중복·결측 검사\ncontentid 충돌 0", "신분류(lclsSystm1) 확인\n영업시간·휴무는 원문 그대로", "적재 스크립트: EV 제외 권장,\n서울 밖 좌표 10행은 NULL"]),
        ("초기 산출물(09-17 검토본)", ["데이터랩 랭킹 원본 100행", "장소명 정규화·병합 66개", "TourAPI 자동 매칭 58 + 수동 5", "activities_clean.csv 63건\n(보류 3)", "내부 category 변환은 예정"]),
    ], note_size=8.6)
    F["dining_flow"] = CH.flow(FIG_DIR / "그림_요식_전처리흐름.png", [
        ("TourAPI 원장", [f"서울 음식점 목록\n{D['tourapi_list']}곳", f"소개정보 수신\n{D['tourapi_intro']}곳(09-27 +{D['tourapi_added']})", f"문장 구조화\n영업 구간 {D['intervals'][0]}/{D['intervals'][1]}곳, 휴무 규칙 {D['rules']}곳",
                        f"사람 정답 대조(100곳)\n{D['truth_before']}%에서 {D['truth_after']}%", f"원장 적재\n{D['ledger'][0][1]:,} + 비건·할랄·미쉐린"]),
        ("새 원천(사람 손이 낀 목록)", [f"비건 목록 {D['vegan']['rows']}행\n신규 {D['vegan']['new']}곳", f"할랄 시트 {D['halal']['rows']}행\n웹 근거", f"미쉐린 서울 2026 {D['michelin']['total']}곳\n속성 {D['michelin']['matched']}곳 · 신규 {D['michelin']['new']}곳",
                             f"노키즈 검수 시트 {D['nokids']['sheet']}곳\n확인 칸은 비어 있음", f"원장 {D['michelin']['ledger_before']:,}곳에서 {D['ledger_total']:,}곳"]),
    ], note_size=8.6)
    # 학습 결과서용
    lab = {r["exp"]: r for r in exp["intent"] + exp["issue_code"]}
    tuned = {"intent": (9, 10, 11, 12, 13), "issue_code": (17, 18, 19, 20, 21)}
    names = ["TF-IDF", "A.X-Encoder", "mmBERT", "kf-deberta(선정)", "Qwen3-Embedding"]
    colors = [CH.GRAY, CH.AQUA, CH.ORANGE, CH.BLUE, "#4A3AA7"]
    F["exp_bar"] = CH.grouped(FIG_DIR / "그림_요청종류_문제코드_교사일치도.png", ["요청 종류", "문제 코드"],
                              [(names[i], colors[i], [lab[tuned["intent"][i]]["acc"], lab[tuned["issue_code"][i]]["acc"]]) for i in range(5)],
                              xmax=1.0, xlabel="시험 교사 일치도(Gemma 라벨 기준, 실제+합성·가중 조정판)", height=4.6)
    ax_int = {r["run_key"]: r for r in exp["intent"] if r["model"] == "skt/A.X-Encoder-base"}
    ax_iss = {r["run_key"]: r for r in exp["issue_code"] if r["model"] == "skt/A.X-Encoder-base"}
    F["tuning"] = CH.grouped(FIG_DIR / "그림_가중조정_전후.png", ["요청 종류 A.X 검증", "문제 코드 A.X 검증"],
                             [("첫 판(빈도 역수 가중 상한 20, 4에폭)", CH.GRAY, [ax_int["p1_real_only"]["valid"], ax_iss["p1_real_only"]["valid"]]),
                              ("조정판(제곱근 가중 상한 5, 8에폭, 배치 16)", CH.BLUE, [ax_int["p1b_real_tuned"]["valid"], ax_iss["p1b_real_tuned"]["valid"]])],
                             xmax=1.0, xlabel="검증 정확도", height=3.2)
    e5 = D["e5"]
    F["e5"] = CH.grouped(FIG_DIR / "그림_요식_대체유사도.png", ["분류 일치@3(157곳)", "태그 없는 11곳의 일치@3", "보기 맞추기 hit@5"],
                         [("규칙(태그)", CH.GRAY, [e5["rule"]["top3"], None, None]),
                          ("e5 그대로", CH.AQUA, [e5["raw"]["top3"], e5["raw"]["notag"], e5["raw"]["hit5"]]),
                          ("e5 학습(미세조정)", CH.BLUE, [e5["tuned"]["top3"], e5["tuned"]["notag"], e5["tuned"]["hit5"]])],
                         xmax=1.0, xlabel="시험 173곳, 1회. 분류 일치는 대리 지표(분류도 메뉴에서 규칙으로 뽑음)", height=4.0)
    F["e5_flow"] = CH.flow(FIG_DIR / "그림_요식_임베딩학습흐름.png", [
        ("학습", ["관광공사 음식점 980곳\n8:2 분할(학습 807·시험 173)", f"짝 만들기: 상호+대표메뉴 / 취급메뉴\n(둘 다 있는 {e5['train']}곳)", f"InfoNCE 대조학습\n{e5['epochs']}에폭·배치 {e5['batch']}·lr {e5['lr']}·CPU {e5['secs']}초"]),
        ("평가", ["시험 173곳(분류 산정 157곳)\n규칙·e5 그대로·e5 학습 비교", "사람 판정 시트 237행\n(아직 비어 있음)", "제품에는 미적용"]),
    ], note_size=8.8)
    t = env["train"]
    F["train_flow"] = CH.flow(FIG_DIR / "그림_분류_학습평가흐름.png", [
        ("학습", ["전처리 조각\n학습·검증·시험", "기준선\nTF-IDF + 로지스틱 회귀", "인코더 파인튜닝 4종\nGPU, bfloat16", "에폭별 검증\n정확도 기록"]),
        ("선정·보고", ["검증 조각 점수로\n모델 선정", "시험 조각은 선정 뒤\n1회 보고", "부트스트랩 2,000회\n95% 신뢰구간"]),
    ])
    F["deps"] = CH.flow(FIG_DIR / "그림_학습데이터와_의존라이브러리.png", [
        ("학습 데이터", [f"사건제목 교사 라벨\n{K.CLS['labeled']:,}건(요청 종류·문제 코드)", f"합성 문장 {K.CLS['synth']}건\n(일관성 필터 통과)", f"요식 가게 {e5['train']}곳\n(대체 유사도 짝 학습)", "이동 탐침 8,648건\n(특징 27개, 미채택 실험)"]),
        ("학습 라이브러리", [f"PyTorch {t['torch'].split('+')[0]}\nTransformers {t['transformers']}", f"scikit-learn {t['scikit_learn']}\nNumPy {t['numpy']}", f"Ollama {t['ollama']}\n교사 {t['teacher_model']}"]),
        ("모델 파일", ["SafeTensors\n(인코더 가중치)", "metrics.json\n(학습 설정·지표)", "pkl(이동 HGB)\n미채택 비교 모델"]),
    ], note_size=8.4)
    F["infer"] = CH.flow(FIG_DIR / "그림_제품분류와_로컬모델.png", [
        ("제품 분류", ["고객 메시지", "Gemma 4 12B\n없으면 OpenAI", "제품 분류·후속 라우팅"]),
        ("로컬 모델 시험", ["제출 kf-deberta-base\n요청 종류·문제 코드", "로컬 어댑터\n계약 시험", "제품 분류 조립에는\n연결되지 않음"]),
    ])
    return F
