---
type: handoff
title: SFT 템플릿·토크나이저 동일성 + 근거 판별 일반화 인계 — 서빙 prompt·토큰 10/10 일치, 남은 차이 3건(내장 템플릿 빈 생각 블록·BPE 동순위·토큰 수 CRLF 과대), 근거 판별 일반 해결 7/26 (2026-10-31)
description: 배포 Ollama 0.31.1 gemma4 renderer·토크나이저와 HF Gemma 4 E4B 학습 쪽을 CPU 로 대조. 어휘·병합·특수 동일, 템플릿 HF 현재 = 서빙, 학습 토큰 접두사 보존 7/7. 검사기 token_budget 과대 208–255(system 7,439 실측). 근거 판별은 정답 전체 비교·일정 개체 언급만 어휘 목록 없이 가능, 19/26 의미 판단 필요. 모델·GPU·유료·x600·고객 자료 0
status: draft
domain: travel
---

# SFT 템플릿·토크나이저 동일성 + 근거 판별 일반화 — 인계

보고: [동일성·일반화 보고](../../final_project_cs/wiki/records/reports/2026-10-31_sft-template-tokenizer-parity-grounding-feasibility.md) · 검증물: [`program/research/sft_template_tokenizer_parity_2026-10-31/`](../../program/research/sft_template_tokenizer_parity_2026-10-31/README.md) · 이전: [합성 검사기 독립 검토 인계](2026-10-31_sft-distill-synthetic-checker-independent-review.md)

## 한 일
- 배포 blob 어휘(로컬 Ollama `/api/show`, 메타데이터만)를 세 곳과 비교했습니다: HF `gemma-4-E4B-it@ee0ef602` tokenizer.json(메모리로만 읽음), 검사기 어휘 파일, Ollama v0.31.1 소스. 토큰·병합·특수 24개가 모두 같았습니다.
- Ollama `gemma4` small renderer 와 BPE(heap 동순위 포함)를 파이썬으로 옮겼습니다. 이 포트로 픽스처 7개와 규모 사례 3개를 대조했습니다.
  - 서빙 prompt 와 HF 현재 템플릿: 10/10 일치
  - 포트와 llama-tokenize 의 토큰: 10/10 일치
  - 학습 문자열 접두사 보존: 7/7
  - HF 기준 벡터: llama-tokenize 46/46, 포트 45/46
- 기존 탐침과 부정사례 79행에 어휘 목록 없는 판별 3종을 한 번씩 돌렸습니다.

## 남은 장애 (다음 담당)
1. **T3 토큰 수 과대(확인됨):** 후보 0.2의 `token_budget.count`는 텍스트 모드 임시 파일을 써서 `\n`이 `\r\n`이 되고, 여기에 BOS 2개와 가정 여유 32가 더해집니다. 그 결과 208–255토큰을 과대 추정합니다. system 은 7,605가 아니라 7,439토큰이고, user 몫은 3,636토큰입니다. 경계 결론(32항목·8턴 적합, 48항목·4턴 초과)은 그대로입니다. 고칠 방법: 렌더된 서빙 prompt 전체를 stdin 과 `--no-bos`로 한 번 셉니다.
2. **T1 템플릿:** 어휘 GGUF 내장 템플릿과 `gemma4-large`는 생성 프롬프트에 빈 생각 블록을 붙입니다. 학습 템플릿은 HF sha `0a2c8073…`로 고정하고, 행마다 「학습 prompt == 서빙 렌더」를 fail-closed 로 검사합니다. 후보 모델 이름에 `12b/26b/31b`가 들어가면 large renderer 가 선택되므로 쓰지 않습니다.
3. **T2 BPE 동순위(포트 예측, Go 미실행):** 반복 문자(ㅋ 5회 이상, ㅎ·ㅠ 3회 이상 등)에서 Ollama 와 HF 의 토큰이 달라질 수 있습니다. 서빙과 같은 토크나이저로 `input_ids`를 미리 만들거나, 차이가 나는 행을 표시합니다. Go 도구로 Ollama `tokenizer` 패키지를 직접 돌려 확인해야 합니다.
4. **근거 판별:** 아래 둘을 반영합니다.
   - M1 정답 JSON 전체 비교: 구조 결함용 fail-closed 검사로 넣습니다. 보류 탐침 HN9 도 이것으로 닫힙니다.
   - M3 일정 개체 언급: 표시 전용으로 넣습니다. 7/26 검출, 오표시 0/17 이지만 이 합성 표본 한정입니다.

   나머지 19/26은 사람 rubric 이나 승인된 판정 모델로 다룹니다. 다른 길은 일반 답 구조화(추천 대상·이유 칸)인데, 이는 서빙 계약 변경이라 구현 담당의 승인이 필요합니다.
5. 완성부 끝 `\n`(서빙은 `<turn|>`에서 멈춤)을 손실에서 뺄지, 서빙 출력 JSON 공백 형식이 어떤지도 정해야 합니다. 후자는 x600 원응답을 읽기 전용으로 대조합니다.

## 하지 않은 것
학습, 모델 적재·추론, GPU, 유료 호출, x600 접속, 고객 자료, 운영 변경, 커밋은 모두 0입니다. 후보 0.2와 이전 검토물은 수정하지 않았습니다(해시 19/19 동일). x600 동일성은 같은 blob 해시, 같은 Ollama 버전, 같은 renderer 이름으로 추론했습니다. 다음은 확인하지 않았습니다.
- Ollama 실행 파일 해시
- adapter 의 토크나이저 영향
- x600 TEMPLATE 줄

## 디스크
- 검증 폴더는 117,935B(파일 20개)이고 보고서는 15.4KB입니다. 대용량 사본은 0입니다.
- 내가 만든 임시 작업폴더 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/sft-tmpl-tok-20261031/`(26개 파일, 26,353,402B, 최대 26,355,042B)와 실수로 만든 목록 파일 809B를 삭제했습니다. 남은 임시 파일은 0개입니다. 받은 소스의 sha256 은 `evidence/parity.json`에 남겼습니다.
- C: 여유는 209.52GB(측정 05:21 KST)로 목표 400GB에 미달합니다. `disk_guard check`는 allowed 였고 다른 소유 자료는 건드리지 않았습니다.
- 주의: Hermes 터미널이 `PYTHONPATH`에 3.14 site-packages 를 넣습니다. 3.12 venv 를 실행할 때는 `unset PYTHONPATH`가 필요합니다.

## 진행 — 후보 0.3 (2026-10-31 06:20 KST 덧붙임)

보고: [후보 0.3 T3·T1·M1·M3 반영](../../final_project_cs/wiki/records/reports/2026-10-31_sft-candidate-v0_3-template-token-grounding.md) · 후보: [`program/research/sft_distill_synth_review_2026-10-31/candidate_v0_3/`](../../program/research/sft_distill_synth_review_2026-10-31/candidate_v0_3/README.md)(git 미추적)

### 한 일 (위 「남은 장애」 기준 반영 3/5 = 60%, 나머지 2건은 결정 목록)
- **1. T3 고침.** 렌더된 서빙 prompt 전체를 stdin·`--no-bos`로 한 번 세고, 여유 가정은 지웠다.
  - system 7,439 · 표지 13 · user 몫 3,636, 서빙 prompt 10/10 실측 일치
  - 경계 결론 변화 0/21(32항목·8턴 여유 633, 48항목·4턴 −199)
- **2. T1 반영.** 행별 학습 렌더 == 서빙 렌더를 fail-closed 로 검사한다(HF sha `0a2c8073c878ab1da004bee933a998606537bbb62016310352c7285c3f01c5b5` 고정). `12b/26b/31b`와 빈 생각 블록은 실패다.
- **4. M1·M3 반영.**
  - M1 정답 JSON 전체 비교: fail-closed 이고 HN9 가 닫혔다. 보류 탐침 놓침은 7/12 에서 6/12 로 줄었다.
  - M3 `R_ENTITY_IN_FREE_TEXT`: 검수 표시만 한다. 7/26 표시, 오표시 0/17이고 판정 영향은 0이다. 나머지 글 칸은 `human_rubric_queue`로 보낸다.
- 시험: RED 18/19(0.2 도구) · 7/7(검토 반영 전) → GREEN **52/52 = 100%**, 부정 39/39. 기존 시험·기대 코드는 수정 0개다. Codex 독립 검토 1회의 지적 8건 중 7건을 고쳤고, 1건(동어반복)은 한계로 기록했다.

### 남은 결정 (담당·승인, 코드 변경 없음 — 보고서 §3)
- D1 T2 Go 확인: 이 호스트에 Go 가 없어 미실행이다. 도구 설치 승인 또는 추론 승인이 필요하다. 그 전에는 포트로 `input_ids`를 만들거나 차이 행을 표시하는 안이 있다.
- D2 완성부 끝 `\n`: 손실 마스크로 제외하는 안을 권고한다. 학습 도구 담당이 정한다.
- D3 G5 도구 고정: 템플릿 sha 는 검사기가 강제한다. BOS 1개와 `input_ids` 방식은 학습 도구 담당이 정하며, input_ids 는 D1 결과에 따른다.
- D4 서빙 출력 JSON 공백: x600 원응답 읽기 대조를 권고한다. x600 접속 승인이 필요하다.
- 미구현: `human_review_pending` 을 학습 투입 관문에 연결하는 일.

### 하드코딩·대체 기록
- `render_check.jinja2_site_packages` 는 Hermes 판 번호가 든 경로다. 갱신되면 행이 `E_TRAIN_RENDERER_MISSING` 으로 실패하고, 조용한 대체는 없다. jinja2 버전은 3.1.6 으로 고정했다.
- markupsafe 는 순수 파이썬 구현이 쓰일 수 있다(라이브러리 내부 대체). 렌더 sha 7/7 일치로 결과 영향이 없음을 확인했다.
- `llama-tokenize.exe` 는 실행 파일 sha 만 고정했다(DLL 은 고정하지 않음).

### 불변·디스크
- 후보 0.2·이전 검토물·이 검증물 88/88 파일의 sha256 이 시작과 끝에서 같았다. 이 인계와 목차는 덧붙이기만 했다(편집 전 sha `241d7edd…`·`0453fd39…`).
- 새 후보 폴더는 317,256B·43파일이다. 내 임시폴더 `…/cache/scratch/sft-v03-20261031/`(54파일, 672,906B)는 삭제해 남은 것이 0이다.
- 시험 임시 폴더가 시스템 Temp 에 잠깐 만들어졌다가 지워졌다. 셸의 `TMPDIR=/tmp`가 Windows Python 에서 무효이기 때문이다. 남은 것은 0이다.
- `disk_guard check` 는 allowed 였다. C: 여유는 220,002,107,392B(06:17 KST)로 목표 400GB 에 미달한다.
- 학습·모델 적재·추론·GPU·유료·x600·고객 자료·운영 변경·커밋은 모두 0이다. Ollama 호출도 0이다.
