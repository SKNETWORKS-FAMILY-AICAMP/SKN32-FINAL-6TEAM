# 최종 프로젝트 산출물 문서 양식

2026-08-28 배포받은 제출 양식이다. 원본 압축파일도 이 폴더에 함께 둔다.

## 폴더 구조

```
program/산출물양식/
  README.md                  ← 이 파일
  [기획] ...                 ← 신 양식 18개
  [데이터 수집 및 저장] ...
  [데이터 전처리] ...
  [모델링 및 평가] ...
  [모델배포] ...
  [최종_프로젝트]_...pptx
  구) 양식/                  ← 이전 양식 19개 (참고용)
  최종 프로젝트 산출물 문서 양식-20260828T054153Z-1-001.zip
```

신 양식을 쓴다. `구) 양식/`은 항목이 어떻게 바뀌었는지 대조할 때만 본다.

## 제출 문서와 우리 산출물의 대응

각 양식을 채울 때 어느 문서를 근거로 삼으면 되는지 적는다. 빈칸부터 채우지 말고
여기 적힌 문서를 먼저 읽는다.

### 기획

| 양식 | 근거로 쓸 우리 문서 |
|---|---|
| `[기획] 프로젝트 기획서_양식.docx` | `program/plan/A-COP_구현계획서_v8.md` |
| `[기획] WBS_양식 (1).xlsx`, `(2).xlsx` | `program/research/_WBS원본_2026-08-17.md` |
| `[모델배포]_요구사항 정의서_양식.xlsx` | 계획서 §27 DoD 1~29 |

### 데이터 수집 및 저장

| 양식 | 근거로 쓸 우리 문서 |
|---|---|
| `[데이터 수집 및 저장] 수집 데이터 보고서.docx` | `datasets/README.md`와 각 데이터셋의 `REPORT.md` |
| `[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx` | `final_project_cs/app/infrastructure/db/migrations/` |

수집 데이터 보고서는 데이터셋이 여럿이라 분량이 크다. 다음 순서로 적으면 빠뜨리지 않는다.

- 상용 주문 데이터: `commerce/coupang_order_history`, `commerce/naver_order_history`
- 배송 조회 도구: `commerce/courier_tracking`
- 공개 VOC 데이터: `voc/*` 9종
- 번역 성능 비교: `mt/olist_reviews_mt_bench`

### 데이터 전처리

| 양식 | 근거로 쓸 우리 문서 |
|---|---|
| `[데이터 전처리] 데이터 전처리 결과서.docx` | 각 데이터셋의 `scripts/normalize.py`와 `processed/` |
| `[데이터 전처리] 머신러닝_딥러닝 학습 결과서.docx` | `mt/olist_reviews_mt_bench/REPORT.md` |
| `[데이터 전처리] 학습한 ML_DL 모델.docx` | 동 |

**주의**: VOC 5종은 아직 전처리 전이다. 상태는 `datasets/README.md`가 정본이다.
없는 것을 있다고 적지 않는다.

### 모델링 및 평가

| 양식 | 근거로 쓸 우리 문서 |
|---|---|
| `[모델링 및 평가] AI 시스템 아키텍처 (멀티 에이전트 아키텍처)_양식.docx` | 계획서 §8 Core 1/Core 2 구조, `program/plan/diagram/` |
| `[모델링 및 평가] 멀티 에이전트 테스트 계획 및 결과 보고서_양식.docx` | `final_project_cs/eval/`, `docs/evidence/DoD-*.md` |
| `[모델링 및 평가] 벡터DB_GraphDB 구축 결과서_양식.docx` | `app/infrastructure/rag/`, `app/infrastructure/graphstore/` |
| `[모델링 및 평가] 자체 sLLM 인공지능_양식.docx` | 주제 3·4 선택 시에만 해당. 우리 주제와 맞는지 먼저 확인한다 |

### 모델 배포

| 양식 | 근거로 쓸 우리 문서 |
|---|---|
| `[모델배포] 시스템 구성도_양식.docx` | 계획서 §12, `program/plan/diagram/` |
| `[모델배포] 개발된 LLM 연동 웹 애플리케이션_양식.docx` | `final_project_ui/`, `final_project_cs/app/presentation/` |
| `[모델배포] 서비스 테스트 계획 및  결과 보고서_양식.docx` | `final_project_cs/tests/`, `docs/evidence/` |

### 발표

| 양식 | 시점 |
|---|---|
| `[최종_프로젝트]_중간_발표회_발표(예시)_템플릿.pptx` | 중간발표 2026-09-15 |
| `[최종_프로젝트]_최종_발표회_프로젝트 결과보고서_템플릿.pptx` | 최종발표 2026-10-26 |

일정 근거는 `program/research/_WBS원본_2026-08-17.md`다.

## 채울 때 지킬 것

문서에 없는 것을 지어내지 않는다. 미완성 항목은 미완성이라고 적는다. 이 프로젝트는
DoD 증빙과 평가 지표로 판정하므로, 근거 없는 서술은 검증 단계에서 드러난다.

수치를 적을 때는 어느 파일의 언제 결과인지 함께 적는다. 예를 들어 번역 성능은
GPU 서버 재검증(2026-08-24) 이후 값이 정본이고, 그 이전 GGUF 결과는 양자화 문제로
신뢰할 수 없다. 근거는 `datasets/mt/olist_reviews_mt_bench/REPORT.md`다.
