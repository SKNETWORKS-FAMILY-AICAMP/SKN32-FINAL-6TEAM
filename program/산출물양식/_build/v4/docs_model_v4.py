# -*- coding: utf-8 -*-
"""4차 v4 — 학습한 ML / DL 모델 본문. 소유: 파일·입출력·의존성·로딩·무결성, 로컬 모델 미연결의 상세와 연결 조건."""
from __future__ import annotations

import hashlib

import content_core_v2 as K
import content_teams_v2 as T
from mob_data import MOB as m
from common_v2 import (AUTHORS, COVER, DRIVE_URL, ML, REPO_URL, SUBMIT_DATE, VERSION_TAG, Composer, finish, template)

NAME = f"[데이터 전처리] 학습한 ML_DL 모델_{VERSION_TAG}_여행.docx"
PACK = ML / "_drive_upload" / "학습한_ML_DL_모델_3차_여행"
HISTORY = [
    ("2026.09.17", "전체", "선정 모델 3종(인코더 3종)의 구조·저장·추론 작성", "전체", "v1.0"),
    ("2026.09.28", "전체", "제품 미연결 정정, 라벨 어휘 차이·해시 확인·미채택 이동 모델 추가", "전체", "v2.0(4차)"),
    ("2026.09.28", "전체", "팀별 통합 형식으로 재구성, 감정 모델 제외, 요식 e5 시험 모델·계획 읽기의 쓰는 모델 추가, 이동 2차 반영", "전체", "v3.0(4차 v2)"),
    ("2026.09.28", "전체", "쇼핑 매장 크롤링 제외, 액티비티를 후보 805행 기준으로 재작성, 「확인 필요」 문구를 확인한 사실로 교체", "전체", "v4.0(4차 v3)"),
    ("2026.09.28", "전체", "결론 먼저 순서로 재구성, 성능·연결·한계를 나눠 표를 재배치, 해시 목록을 상세 근거로 이동", "전체", "v5.0(4차 v4)"),
]


def check_hashes():
    """제출 폴더의 SHA256SUMS.txt 를 직접 다시 대조한다."""
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


def build(F, exp, env, hashes):
    c = Composer(template("[데이터 전처리] 학습한 ML_DL 모델.docx"))
    c.cover(COVER, "데이터 전처리", SUBMIT_DATE + " (4차 v4)", REPO_URL, AUTHORS)
    pi = next(r for r in exp["intent"] if r.get("picked"))
    pj = next(r for r in exp["issue_code"] if r.get("picked"))
    ours = [r for r in hashes if r["file"].startswith(("intent/", "issue_code/"))]
    size = {r["file"]: r["size"] for r in hashes}
    mib = lambda b: f"{b / 1024 / 1024:.0f}"  # noqa: E731
    e5, ml = T.DINING["e5"], m["ml"]
    t, cpu = env["train"], env["cpu_eval"]

    c.para("개정 기준 2026년 9월 28일(4차 v4). " + K.SERVICE_NOTE)
    c.callout("이 문서를 읽는 법", [
        "제출한 학습 모델은 요청 종류·문제 코드 인코더 2종이다. 요식 e5 미세조정과 이동 판정 ML은 시험·비교 모델이며 제품에는 쓰이지 않는다.",
        "점수는 교사(Gemma) 일치도이며 사람 정답과의 정확도가 아니다. 실험 상세는 학습 결과서에 있다.",
    ])
    c.kpi([
        ("제출", "2종", f"요청 종류·문제 코드 kf-deberta-base 인코더 각 {mib(size['intent/model.safetensors'])} MiB"),
        ("검증", f"{len(ours)}/{len(ours)}", f"이 판 모델 파일 해시 일치. 제출 폴더 전체 {len(hashes)}/{len(hashes)}(09-28 직접 대조)"),
        ("적용 상태", "미연결", "제품 분류는 LLM이 한다. 연결 전 v3 지침(18종)으로 재라벨·재학습 필요"),
        ("시험·비교", "3종", "요식 e5 미세조정 1종(제품 미적용), 이동 HGB 2종(미채택)"),
    ])

    # ── 1. 모델 개요 ─────────────────────────────────────────
    c.h1("모델 개요")
    c.lead("제출 모델, 시험·비교 모델, 제품에서 쓰는 모델을 구분해야 한다. 제출 모델은 아직 제품 분류에 연결되지 않았다.")
    c.table("팀별 모델 현황", ["팀", "모델", "유형", "적용 상태"], [
        ("코어", "kf-deberta-base 2종(요청 종류·문제 코드)", "제출 학습 모델", "제품 미연결(어댑터·계약 시험까지)"),
        ("코어", "Gemma 4 12B, bge-m3", "학습 없이 쓰는 모델", "제품 사용(분류·계획 읽기·규정 검색)"),
        ("이동", "HistGradientBoosting v1·v2", "시험·비교(미채택)", "판정 경로에 없음"),
        ("액티비티", "없음", "해당 없음", "전용 학습 없음(팀 저장소 검색 범위)"),
        ("요식업", "multilingual-e5-small 미세조정", "시험 모델", "제품 미적용, 파일은 저장소 밖"),
    ], [12, 34, 22, 32])
    c.line("담당 태스크", "로컬 분류 시험(요청 종류 5종·문제 코드 17종, 제품 18종), 요식 대체 유사도 시험, 이동 판정 대조 실험")
    c.para(K.LOCAL_NOTE)

    # ── 2. 모델 구조 정의 ────────────────────────────────────
    c.h1("모델 구조 정의")
    c.h2("2.1 구성 요소 (전처리 · 학습 · 후처리)")
    c.lead("각 구성 요소의 역할과 의존성이 팀별로 나뉘어 있고, 제출 대상은 코어의 인코더 두 개와 시험 어댑터다.")
    c.table("구성 요소", ["팀", "구성 요소", "기능", "의존성 · 비고"], [
        ("코어", "정규화·토크나이저", "NFKC, 반복 글자 축약, 개인정보 치환, 최대 96토큰(학습·추론 공용)", "제품 마스킹 모듈, transformers"),
        ("코어", "학습기 1 · 2", f"kf-deberta-base FT: 요청 종류 5분류, 문제 코드 17분류. 합성 {K.CLS['synth']}건", "transformers"),
        ("코어", "시험 어댑터", "로컬 모델 호출과 계약 시험(tests/unit/ml)", "제품 분류 조립에는 미연결"),
        ("코어", "쓰는 모델 3종", "Gemma 4 12B(분류·계획 읽기), bge-m3(규정 130청크)", "Ollama, 검색 문턱 0.55는 채팅 답에만"),
        ("이동", "특징 + HGB v1·v2", "판정 3분류(특징 27개, v2는 33개)", "numpy, scikit-learn, 미채택"),
        ("액티비티", "해당 없음", "전용 학습 모델 없음", "공통 분류 모델만 사용"),
        ("요식업", "e5-small 인코더(FT)", f"문장 임베딩, 평균 풀링, 이웃 상위 3곳. 학습 {e5['train']}곳, {e5['epochs']}에폭", "transformers, torch, 제품은 태그 자카드"),
    ], [11, 22, 42, 25])
    c.note("제품 분류는 app/composition.py의 build_classifier가 조립하며 로컬 모델을 연결하지 않는다(2026-09-28 코드 확인).")

    c.h2("2.2 입 · 출력 스펙")
    c.lead("모델을 부르려면 아래 입력을 주고 반환값을 받는다. 분류 모델의 어휘 밖 출력은 분류 실패로 처리한다.")
    c.table("입 · 출력 스펙", ["모델", "필드", "타입 · shape", "설명"], [
        ("분류 모델", "text", "str, 메시지 1건", "마스킹된 고객 입력"),
        ("분류 모델", "input_ids", "int64, [1, 최대 96]", "인코더 토크나이저 출력"),
        ("분류 모델", "logits", "float32, [1, 라벨 수]", "변환 전 점수(요청 종류 5, 문제 코드 17)"),
        ("분류 모델", "probability", "float32, [1, 라벨 수], 합 1", "logits에 softmax를 적용한 값"),
        ("분류 모델", "label, confidence", "str, float(1개, 0~1)", "반환값: 확률이 가장 큰 라벨과 그 확률"),
        ("요식 e5", "text", "str, 가게 한 곳의 한 모습", "상호+대표메뉴 또는 취급메뉴"),
        ("요식 e5", "embedding", "float32, [1, 384]", "평균 풀링 뒤 정규화한 벡터"),
        ("이동 HGB", "features, label", "입력 float [1, 27](v2는 [1, 33]), 출력 str", "성립·불가·근거없음"),
    ], [14, 22, 30, 34])
    c.note("e5-small의 차원 384는 공개 모델 설정(hidden_size 384, 2026-09-28 조회)의 값이다. 학습된 파일은 요식 담당 작업 PC의 datasets/ml/dining_sim/에 있고 이 저장소와 이 PC에는 없다.")

    c.h2("2.3 학습 데이터 · 의존 라이브러리 다이어그램")
    c.lead("제출 파일이 어떤 데이터와 실행 환경에 의존하는지 아래 그림으로 추적할 수 있다. 분류 모델은 일관성 필터를 통과한 합성 문장을 포함해 학습했다.")
    c.figure(F["deps"], "팀별 학습 데이터, 라이브러리, 산출 파일의 의존 관계(위 줄 코어, 아래 줄 이동. 두 줄은 서로 이어지지 않는다)")
    c.note(f"요식 e5는 학습 파일이 저장소 밖에 있어 그림에 넣지 않았다(PyTorch·Transformers 사용). 버전(직접 기록): 학습 PyTorch {t['torch']}(CUDA {t['cuda']}), Transformers {t['transformers']}, scikit-learn {t['scikit_learn']} / 추론 검증 PyTorch {cpu['torch']}, Transformers {cpu['transformers']}, scikit-learn {cpu['scikit_learn']}")

    # ── 3. 모델 저장 및 추론 ─────────────────────────────────
    c.h1("모델 저장 및 추론")
    c.h2("3.1 저장 · 로딩 파이프라인")
    c.lead("파일은 모델 폴더에 SafeTensors와 metrics.json으로 저장되고, 로딩은 시험 어댑터를 거치며 제품 분류 경로와는 분리되어 있다.")
    c.figure(F["infer"], "제품 LLM 분류 경로와 미연결 로컬 모델의 시험 경로")
    c.table("저장 · 로딩 명세", ["항목", "값", "측정 조건", "비고"], [
        ("저장 형식", "SafeTensors, 폴더별 metrics.json", "intent, issue_code 폴더", "토크나이저 파일 별도"),
        ("로딩 호출", "LocalLabelModel(model_dir).predict(text)", "시험 어댑터 경유", "제품 분류 조립에는 미연결"),
        ("크기(요청 종류)", f"{mib(size['intent/model.safetensors'])} MiB", "model.safetensors 파일 크기", "-"),
        ("크기(문제 코드)", f"{mib(size['issue_code/model.safetensors'])} MiB", "model.safetensors 파일 크기", "-"),
        ("CPU 지연", "미측정", "-", "3차의 값은 감정 모델이라 제외"),
        ("이동 HGB 크기", "2.9 · 1.6 MB", "model_hgb.pkl · v2(팀 보고)", "미채택 비교 모델"),
        ("요식 e5 파일", "미측정", "저장소 밖이라 크기를 재지 않음", "제품 미적용"),
    ], [16, 32, 32, 20])
    c.note("서비스 타겟(지연·크기 목표)은 정하지 않았다. 제출 위치와 파일 목록은 상세 근거 A·E에 있다.")

    c.h2("3.2 성능 · 한계와 후속 연계")
    c.lead("제출 모델의 검증 범위는 교사 일치도까지이고, 제품 연결에는 어휘 재정렬과 재학습이 먼저 필요하다.")
    c.table("성능 · 연결 · 한계", ["구분", "항목", "값 · 방법", "설명"], [
        ("성능", "요청 종류 시험", f"{pi['acc']:.4f}, 신뢰구간 [{pi['ci'][0]:.4f}, {pi['ci'][1]:.4f}], F1 {pi['f1']:.4f}", f"시험 {pi['n_test']}건, Gemma 라벨 기준, 검증 {pi['valid']:.4f}가 최고"),
        ("성능", "문제 코드 시험", f"{pj['acc']:.4f}, 신뢰구간 [{pj['ci'][0]:.4f}, {pj['ci'][1]:.4f}], F1 {pj['f1']:.4f}", f"시험 {pj['n_test']}건, Gemma 라벨 기준, 검증 {pj['valid']:.4f}가 최고"),
        ("성능", "요식 유사도(시험)", f"분류 일치@3 {e5['tuned']['top3']:.3f}(규칙 {e5['rule']['top3']:.3f}, 그대로 {e5['raw']['top3']:.3f})", "시험 173곳 중 산정 157곳, 1회, 대리 지표"),
        ("성능", "이동 ML(미채택)", f"HGB v1 {ml['hgb'][0]:.3f}(탐침 8,648건), v2 {ml['hgb_v2'][0]:.3f}(11,656건)", "v1·v2는 탐침 모집단이 달라 직접 비교 불가. 팀 보고 09-16, 회귀 71/85·73/85, 판정 경로 미투입"),
        ("연결", "제품 추론", "Gemma 4 12B(Ollama), 없으면 OpenAI", "로컬 모델은 조립에 없고 팀 라우팅은 LLM 값을 사용"),
        ("한계", "교사 라벨 의존", "점수는 Gemma 라벨과의 일치도", "사람 검수 표본이 없어 교사 정확도를 못 잼(09-28 사람 라벨 0건)"),
        ("한계", "어휘", "제출 17종·제품 18종", "booking_revert_request를 출력할 수 없어 v3 재라벨·재학습 뒤 연결 검토"),
        ("한계", "심각도·감정", "severity 학습 데이터 없음, 여행 감정 데이터 미확보", "제품은 LLM 값을 사용. 쇼핑 리뷰 감정 모델은 이 판에서 뺌"),
    ], [9, 17, 38, 36])

    # ── 4. 변경 이력 ─────────────────────────────────────────
    c.h1("변경 이력 및 적용 전략")
    c.lead("제출 모델 2종의 해시는 모두 일치하며, 이번 판에서 모델 파일과 성능 수치는 바뀌지 않았다.")
    c.table("변경 이력", ["변경일", "변경자", "변경내용", "영향 받는 항목", "비고"], HISTORY, [13, 9, 47, 13, 18], detail=True, five_ok=True)
    c.para(f"무결성: SHA256SUMS.txt로 이 판의 모델 {len(ours)}/{len(ours)}, 제출 폴더 전체 {len(hashes)}/{len(hashes)}가 일치했다(2026-09-28 파일을 다시 읽어 대조, 기록은 검사결과.json).")
    c.para("적용 전략: 제출 모델 폴더는 판마다 새로 만들고 기존 폴더를 덮어쓰지 않는다(ml/package_models.py는 출력 폴더가 있으면 멈춘다). 받는 쪽은 SHA256SUMS.txt로 확인한 뒤 교체한다.")

    # ── 상세 근거 ────────────────────────────────────────────
    c.h3("상세 근거")
    c.h4("A. 제출 파일 목록과 해시")
    rows = [(r["file"], f"{r['size']:,} B", r["sha256"]) for r in ours]
    c.table_split("이 판 제출 파일과 SHA256", ["파일", "크기", "SHA256"], rows, [26, 14, 60], limit=12)
    c.note("제출 모델 폴더에는 3차 제출 당시의 감정 모델(쇼핑 리뷰 학습) 파일도 들어 있으나 이 판의 설명 대상에서 뺐다.")
    c.h4("B. 실행 환경 버전")
    c.table("학습 · 추론 검증 환경", ["항목", "학습", "추론 검증"], [
        ("PyTorch", f"{t['torch']}(CUDA {t['cuda']})", str(cpu["torch"])),
        ("Transformers", str(t["transformers"]), str(cpu["transformers"])),
        ("scikit-learn", str(t["scikit_learn"]), str(cpu["scikit_learn"])),
        ("NumPy · Ollama", f"{t['numpy']} · {t['ollama']}", "-"),
    ], [24, 40, 36], detail=True)
    c.h4("C. 시험·비교 모델 세부")
    c.table("미채택 · 시험 모델 세부", ["항목", "내용", "비고"], [
        ("이동 라벨 체계", "model_hgb.pkl·v2의 라벨은 규칙 v0.3.1의 판정 3클래스", "현행 판정기 v0.9.1은 성립/불가 둘과 이유 코드 10을 내므로 재평가하려면 매핑이 필요. 재학습·재평가 없음"),
        ("이동 통계 표", "bus_seg_profile_v1: 717노선 구간 x 평일/휴일 x 0~23시 p10/p50/p90, 9.6 MB", "학습 모델이 아니라 분위수 표. 셀 관측 5일 미만이면 값 없음"),
        ("요식 e5", "학습 파일은 요식 담당 작업 PC에 있고 이 저장소에 없음", "사람 판정 시트 237행(가게 40곳마다 후보 5~6곳)이 비어 있음"),
        ("액티비티", "전용 학습 모델 없음", "team/role-activity 코드·문서를 검색한 범위에서 확인"),
    ], [20, 44, 36], detail=True)
    c.h4("D. 성능·연계 나머지 항목")
    c.table("성능 · 연계 나머지", ["구분", "항목", "값 · 방법", "설명"], [
        ("연계", "팀 라우팅", "제품 LLM의 문제 코드와 요청 종류를 후속 라우팅 입력으로 사용", "문제 코드 접두별 case_type·담당 팀 매핑은 제품 라우팅 규칙에 별도로 있음"),
        ("계획 읽기", "학습하지 않는 모델", "Gemma 4 12B, bge-m3", "정확도는 학습 결과서의 평가셋 60건과 소표본 실측(값 변조 3.4%로 목표 0 미달)"),
        ("저장", "버저닝", "인코더 SafeTensors, 모델 폴더별 metrics.json", "가중치는 SafeTensors로 로딩한다"),
    ], [12, 18, 38, 32], detail=True)
    c.note("이동·요식 값은 각 팀의 보고와 파일을 인용한 것이며 이번 작성에서 재실행하지 않았다. 이동은 2차(2026-09-28, role-mobility 94dd707) 기준이다.")
    c.h4("E. 제출 위치")
    c.para("제출 위치: 팀 공유 드라이브 " + DRIVE_URL)
    return finish(c, NAME), c
