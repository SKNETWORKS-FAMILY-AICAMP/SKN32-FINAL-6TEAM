# -*- coding: utf-8 -*-
"""4차 v2 — 학습한 ML / DL 모델 본문 (팀별 통합 형식, 감정 모델 제외)."""
from __future__ import annotations

import hashlib
import json

import content_core_v2 as K
import content_teams_v2 as T
import docs_mobility_v2 as MOB
from common_v2 import (AUTHORS, COVER, DRIVE_URL, ML, REPO_URL, SUBMIT_DATE, VERSION_TAG, Composer, finish, need, template)

NAME = f"[데이터 전처리] 학습한 ML_DL 모델_{VERSION_TAG}_여행.docx"
PACK = ML / "_drive_upload" / "학습한_ML_DL_모델_3차_여행"


def check_hashes():
    """제출 폴더의 SHA256SUMS.txt 를 직접 다시 대조한다. 이 판의 대상(intent·issue_code)만 따로 센다."""
    manifest = PACK / "SHA256SUMS.txt"
    if not manifest.exists():
        raise SystemExit("[멈춤] 모델 해시 근거가 없다")
    rows = []
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        rel = rel.lstrip("*")
        h = hashlib.sha256()
        fp = PACK / rel
        with fp.open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        rows.append({"file": rel, "sha256": expected, "size": fp.stat().st_size, "result": "OK" if h.hexdigest() == expected.lower() else "FAIL"})
    if any(r["result"] != "OK" for r in rows):
        raise SystemExit("[멈춤] 모델 해시 불일치")
    return rows


def env_line(env):
    t, cpu = env["train"], env["cpu_eval"]
    return (f"학습 PyTorch {t['torch']}(CUDA {t['cuda']}), Transformers {t['transformers']}, scikit-learn {t['scikit_learn']} / "
            f"추론 검증 PyTorch {cpu['torch']}, Transformers {cpu['transformers']}, scikit-learn {cpu['scikit_learn']}")


def build(F, exp, env, hashes):
    c = Composer(template("[데이터 전처리] 학습한 ML_DL 모델.docx"))
    c.cover(COVER, "데이터 전처리", SUBMIT_DATE + " (4차 v3)", REPO_URL, AUTHORS)
    pi = next(r for r in exp["intent"] if r.get("picked"))
    pj = next(r for r in exp["issue_code"] if r.get("picked"))
    ours = [r for r in hashes if r["file"].startswith(("intent/", "issue_code/"))]
    size = {r["file"]: r["size"] for r in hashes}
    mib = lambda b: f"{b / 1024 / 1024:.0f}"  # noqa: E731
    e5 = T.DINING["e5"]
    m = MOB.MOB

    c.para("개정 기준 2026년 9월 28일(4차 v3). " + K.SERVICE_NOTE + " " + K.EXCLUDE_NOTE + " 제출 모델 폴더에는 3차 제출 당시의 감정 모델(쇼핑 리뷰 학습)도 들어 있으나 이 판의 설명 대상에서 뺐다.")
    c.callout("이 문서를 읽는 법", [
        "제출한 학습 모델은 요청 종류·문제 코드 인코더 2종이다. 요식 대체 유사도(e5 미세조정)와 이동 판정 ML은 시험·비교 모델이고 제품에는 쓰이지 않는다.",
        "제품의 인라인 분류는 Gemma 4 12B(Ollama, 없으면 OpenAI)가 한다. 로컬 모델은 어댑터와 계약 시험까지 구현됐고 제품 분류 조립에는 연결되지 않았다(2026-09-28 코드 확인).",
        "점수는 교사(Gemma) 일치도이며 사람 정답과의 정확도가 아니다.",
    ])
    c.kpi([
        ("2종", "제출한 학습 모델", "요청 종류·문제 코드, kf-deberta-base 인코더 각 709 MiB"),
        (f"{len(ours)}/{len(ours)}", "이 판 모델 파일 해시 일치", f"제출 폴더 전체는 {len(hashes)}/{len(hashes)}(2026-09-28 직접 대조)"),
        ("미연결", "제품 분류와의 연결", "제품 분류는 LLM. 연결 전 v3 지침(18종)으로 재라벨·재학습 필요"),
        ("3종", "시험·비교 모델", "요식 e5 미세조정 1종(제품 미적용), 이동 HGB 2종(미채택)"),
    ])

    # ── 1. 모델 개요 ─────────────────────────────────────────
    c.h1("모델 개요")
    c.line("모델 유형", "파인튜닝한 인코더 분류기 2종(kf-deberta-base, 요청 종류·문제 코드, 과제별로 검증 조각에서 선정). 시험·비교 모델: 요식 문장 임베딩 미세조정(multilingual-e5-small), 이동 판정 HistGradientBoosting(미채택)")
    c.line("담당 태스크", "로컬 분류 시험: 요청 종류 5종, 문제 코드 17종(제품 18종). 요식: 대체 식당 유사도 시험. 이동: 판정 대조 실험")
    c.line("프레임워크 / 버전", env_line(env))
    c.para(K.LABEL_NOTE + " " + K.LOCAL_NOTE)

    # ── 2. 모델 구조 정의 ────────────────────────────────────
    c.h1("모델 구조 정의")
    c.h2("2.1 구성 요소 (전처리 · 학습 · 후처리)")
    c.h3("코어 · 분류 모델(제출)")
    c.table(["구성 요소", "유형", "기능", "의존성", "비고"], [
        ("전처리", "정규화·마스킹", "NFKC, 반복 글자 축약, 개인정보 치환", "제품 마스킹 모듈", "학습·추론 공용"),
        ("특징", "모델별 토크나이저", "하위 단어 분할, 최대 96토큰", "transformers", "모델 폴더에 함께 저장"),
        ("학습기 1", "kf-deberta-base(FT)", "요청 종류 5분류", "transformers", f"사건제목 학습 4,859건, 합성 {K.CLS['synth']}건"),
        ("학습기 2", "kf-deberta-base(FT)", "문제 코드 17분류", "transformers", f"사건제목 학습 4,867건, 합성 {K.CLS['synth']}건"),
        ("시험 어댑터", "로컬 분류 어댑터", "로컬 모델 호출과 계약 시험까지 구현했다", "tests/unit/ml", "제품 분류 조립에는 연결되지 않았다"),
    ], [12, 22, 27, 17, 22])
    c.h3("코어 · 학습하지 않고 쓰는 모델")
    c.table(["구성 요소", "모델", "기능", "학습 여부", "비고"], [
        ("제품 분류", "Gemma 4 12B(Ollama), 없으면 OpenAI", "인라인 분류·후속 라우팅 입력", "학습하지 않음", "app/composition.py의 build_classifier가 이 경로를 조립"),
        ("계획 읽기", "Gemma 4 12B 비전(gemma4:12b, 온도 0, 생각 끔)", "사진 받아쓰기, 규칙이 못 읽은 줄의 원문 인용", "학습하지 않음", "원문에 글자 그대로 있는 인용만 받는다"),
        ("규정 검색", "bge-m3(Ollama, 1024차원)", "여행 규정 130청크 임베딩", "학습하지 않음", "검색 문턱 0.55는 채팅 질문 답에만 적용"),
    ], [12, 27, 27, 12, 22])
    c.h3("이동 에이전트(mobility)")
    c.table(["구성 요소", "유형", "기능", "의존성", "비고"], [
        ("특징", "판정 입력 27개(v2는 33개)", "구간·시각·소스 존재 등", "numpy", "탐침에서 만든 특징"),
        ("모델 A", "HistGradientBoosting v1", "판정(성립·불가·근거없음) 분류", "scikit-learn", "model_hgb.pkl 2.9MB, 미채택"),
        ("모델 B", "HistGradientBoosting v2", "근거없음 구간 9종을 더한 재학습", "scikit-learn", "model_hgb_v2.pkl 1.6MB, 미채택"),
    ], [12, 24, 27, 15, 22])
    c.h3("요식업 에이전트(dining)")
    c.table(["구성 요소", "유형", "기능", "의존성", "비고"], [
        ("입력 문장", "상호+대표메뉴 / 취급메뉴", "같은 가게의 두 모습을 짝으로 사용", "가게 원장", "분류 낱말은 문장에 넣지 않음(답을 보고 푸는 것 방지)"),
        ("인코더", "multilingual-e5-small(FT)", "문장 임베딩, 평균 풀링, 최대 96토큰", "transformers, torch", f"학습 {e5['train']}곳, {e5['epochs']}에폭, CPU {e5['secs']}초"),
        ("이웃 고르기", "임베딩 유사도 상위 3곳", "대체 식당 후보", "-", "제품에는 미적용(제품은 태그 자카드)"),
    ], [12, 24, 27, 15, 22])

    c.h2("2.2 입 · 출력 스펙")
    c.table(["모델", "입·출력 필드", "타입", "shape / 길이", "설명"], [
        ("분류 모델", "text", "str", "메시지 1건", "마스킹된 고객 입력"),
        ("분류 모델", "input_ids", "int64", "[1, 최대 96]", "인코더 토크나이저 출력"),
        ("분류 모델", "score / probability", "float32", "[1, 라벨 수]", "인코더 logits(요청 종류 5, 문제 코드 17)"),
        ("분류 모델", "label, confidence", "str, float", "1개, 0~1", "제품 어휘 라벨과 최대 확률(어휘 밖이면 분류 실패로 처리)"),
        ("요식 e5", "text", "str", "가게 한 곳의 한 모습", "상호+대표메뉴 또는 취급메뉴"),
        ("요식 e5", "embedding", "float32", "[1, 384]", "평균 풀링 뒤 정규화한 벡터(e5-small 차원 384)"),
        ("이동 HGB", "features와 label", "float / str", "[1, 27]과 1개", "성립·불가·근거없음"),
    ], [16, 20, 14, 22, 28])
    c.note("e5-small의 임베딩 차원 384는 공개 모델 설정(hidden_size 384, 2026-09-28 조회)에서 온 값이다. 학습된 파일은 요식 담당 작업 PC의 datasets/ml/dining_sim/에 저장되며 이 저장소와 이 PC에는 없다.")

    c.h2("2.3 학습 데이터 · 의존 라이브러리 다이어그램")
    c.para("분류 모델은 교사 라벨을 붙인 사건제목(조정판·전체판은 일관성 필터를 통과한 합성 문장 포함)으로 학습했다. 학습과 추론 검증에 쓴 라이브러리 버전은 실행 환경에서 직접 기록했다.")
    c.figure(F["deps"], "학습 데이터와 의존 라이브러리", 13.0, 10.0)

    # ── 3. 모델 저장 및 추론 ─────────────────────────────────
    c.h1("모델 저장 및 추론")
    c.h2("3.1 저장 · 로딩 파이프라인")
    c.line("모델 파일", "intent, issue_code 폴더(인코더는 model.safetensors·config.json·토크나이저, 공통 metrics.json). 제출 위치: 팀 공유 드라이브 " + DRIVE_URL)
    c.para("CPU 추론 지연은 이 판에서 재지 않았다. 3차에 실린 값은 쇼핑 리뷰로 학습한 감정 모델로 잰 것이라 뺐다. 요청 종류·문제 코드 모델의 CPU 지연은 미측정이다.")
    c.figure(F["infer"], "제품 LLM 분류와 미연결 로컬 모델의 시험 경로", 11.0, 7.0)
    c.table(["항목", "값", "단위", "측정 조건", "서비스 타겟", "비고"], [
        ("크기(요청 종류 모델)", mib(size["intent/model.safetensors"]), "MiB", "model.safetensors 파일 크기", "목표 미설정", "토크나이저 파일 별도"),
        ("크기(문제 코드 모델)", mib(size["issue_code/model.safetensors"]), "MiB", "model.safetensors 파일 크기", "목표 미설정", "토크나이저 파일 별도"),
        ("CPU 지연", "미측정", "-", "-", "목표 미설정", "3차의 값은 감정 모델이라 제외"),
        ("이동 HGB 크기", "2.9 · 1.6", "MB", "model_hgb.pkl · model_hgb_v2.pkl(팀 보고)", "-", "미채택 비교 모델"),
        ("요식 e5 파일", "미측정", "-", "저장소 밖(요식 담당 작업 PC의 datasets/ml/dining_sim/)이라 파일 크기를 재지 않음", "-", "제품 미적용"),
    ], [20, 11, 8, 30, 13, 18])

    c.h2("3.2 성능 · 한계와 후속 연계")
    c.table(["구분", "항목", "값 / 방법", "설명 및 관리 방안"], [
        ("성능", "요청 종류 시험 교사 일치도", f"{pi['acc']:.4f}, 95% 신뢰구간 [{pi['ci'][0]:.4f}, {pi['ci'][1]:.4f}], macro F1 {pi['f1']:.4f}", f"사건제목 시험 {pi['n_test']}건, Gemma 라벨 기준, 선정 사유: 검증 조각 교사 일치도 최고({pi['valid']:.4f})"),
        ("성능", "문제 코드 시험 교사 일치도", f"{pj['acc']:.4f}, 95% 신뢰구간 [{pj['ci'][0]:.4f}, {pj['ci'][1]:.4f}], macro F1 {pj['f1']:.4f}", f"사건제목 시험 {pj['n_test']}건, Gemma 라벨 기준, 선정 사유: 검증 조각 교사 일치도 최고({pj['valid']:.4f})"),
        ("성능", "요식 대체 유사도(시험)", f"분류 일치@3 {e5['tuned']['top3']:.3f}(규칙 {e5['rule']['top3']:.3f}, e5 그대로 {e5['raw']['top3']:.3f})", "시험 173곳·1회, 대리 지표. 사람 판정 시트 237행은 비어 있다"),
        ("성능", "이동 판정 ML(미채택)", f"HGB v1 {m['ml']['hgb'][0]:.3f}, v2 {m['ml']['hgb_v2'][0]:.3f}", "이동 팀 보고 2026-09-16, 회귀 71/85와 73/85. 제품 판정 경로에 넣지 않는다(2차 09-28에도 유지)"),
        ("미채택 비교", "라벨 체계", "model_hgb.pkl·v2의 라벨 = 규칙 v0.3.1 판정 3클래스", "현행 판정기 v0.9.1은 성립/불가 둘과 이유 코드 10을 내므로 같은 라벨로 재평가하려면 매핑이 필요하다. 재학습·재평가 없음(2026-09-28)"),
        ("이동 통계", "bus_seg_profile_v1", "717노선 구간 x 평일/휴일 x 0~23시 p10/p50/p90, 9.6 MB", "학습 모델 아님(분위수 표). 판정기 버스 승차 소요의 입력. 셀 관측 5일 미만이면 값 없음"),
        ("저장", "형식과 버저닝", "인코더 SafeTensors, 모델 폴더별 metrics.json", "인코더 가중치는 SafeTensors로 로딩한다"),
        ("로딩", "호출 코드", "LocalLabelModel(model_dir).predict(text)", "시험 어댑터 경유. 제품 분류 조립에는 연결되지 않았다"),
        ("제품 추론", "LLM 분류", "Gemma 4 12B(Ollama), 없으면 OpenAI", "app/composition.py의 build_classifier는 로컬 모델을 연결하지 않는다"),
        ("한계", "교사 라벨 의존", "요청 종류·문제 코드 점수는 Gemma 라벨과의 일치도", "사람 검수 표본이 없어 교사 라벨의 정확도를 측정하지 못함(2026-09-28 사람 라벨 0건)"),
        ("한계", "심각도 미지원", "severity 라벨 학습 데이터 없음", "제품은 LLM 값을 사용하며, 규칙으로 채울지는 후속 정책 확정이 필요함"),
        ("한계", "감정 모델 없음", "여행 도메인 감정 학습 데이터 미확보", "제품의 감정(긍정·중립·부정)은 LLM이 낸다. 쇼핑 리뷰 학습 모델은 이 판에서 뺐다"),
        ("어휘 한계", "문제 코드", "제출 17종·제품 18종", "booking_revert_request를 출력할 수 없다. v3로 재라벨·재학습한 뒤 연결을 검토한다"),
        ("연계", "팀 라우팅", "제품 LLM의 문제 코드와 요청 종류를 후속 라우팅 입력으로 사용", "문제 코드 접두별 case_type·담당 팀 매핑은 제품 라우팅 규칙에 별도로 둔다"),
        ("무결성", "SHA256SUMS.txt", f"이 판의 모델 {len(ours)}/{len(ours)}, 제출 폴더 전체 {len(hashes)}/{len(hashes)} 일치", "2026-09-28 파일을 다시 읽어 대조했다. 검사 기록은 검사결과.json"),
        ("계획 읽기", "학습하지 않는 모델", "Gemma 4 12B, bge-m3", "정확도는 평가셋 60건과 소표본 실측으로 본다(학습 결과서). 값 변조 3.4%로 목표 0에 못 미침"),
    ], [11, 18, 36, 35], first_bold=True)
    c.note("이동·요식 항목은 각 팀의 보고와 파일을 인용한 값이다. " + MOB.SRC)

    c.h1("변경 이력 및 적용 전략")
    c.table(["변경일", "변경자", "변경내용", "영향 받는 항목", "비고"], [
        ("2026.09.17", "전체", "선정 모델 3종(인코더 3종)의 구조·저장·추론 작성", "전체", "v1.0"),
        ("2026.09.28", "전체", "제품 미연결 정정, 라벨 어휘 차이·해시 확인·미채택 이동 모델 추가", "전체", "v2.0(4차)"),
        ("2026.09.28", "전체", "팀별 통합 형식으로 재구성. 쇼핑 리뷰 감정 모델 제외. 요식 e5 시험 모델·계획 읽기의 쓰는 모델 추가. 요약 카드 추가. 이동 2차 반영(통계 프로파일·라벨 체계)", "전체", "v3.0(4차 v2)"),
        ("2026.09.28", "전체", "4차 v2에서 쇼핑 매장 크롤링을 제외하고 액티비티를 관광지 후보 805행 기준으로 다시 씀. 저장소·스키마·커밋 시각으로 확인한 사실로 「확인 필요」 문구를 바꿈", "전체", "v4.0(4차 v3)"),
    ], [13, 9, 52, 13, 13], keep=True)
    c.para("적용 전략: 제출 모델 폴더는 판마다 새로 만들고 기존 폴더를 덮어쓰지 않는다(ml/package_models.py는 출력 폴더가 있으면 멈춘다). 받는 쪽은 SHA256SUMS.txt로 파일을 확인한 뒤 교체한다.")
    return finish(c, NAME)
