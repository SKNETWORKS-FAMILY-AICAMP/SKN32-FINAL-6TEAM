---
type: report
title: SFT 합성 검사기 후보 0.3 — 토큰 수 실측(T3)·행별 렌더 동일성(T1)·정답 전체 비교(M1)·개체 언급 검수 표시(M3) 반영과 남은 결정 목록 (2026-10-31)
description: 후보 0.2를 candidate_v0_3에 복사해 고침. 토큰 수는 렌더된 서빙 prompt 전체를 stdin·--no-bos로 한 번 세고 여유 가정 삭제(system 7,439·user 몫 3,636, 경계 결론 불변 0/21). 행별 학습 렌더 == 서빙 렌더(HF sha 0a2c8073… 고정, 12b/26b/31b·빈 생각 블록 실패), 정답 JSON 전체 비교 fail-closed(HN9 닫힘), R_ENTITY_IN_FREE_TEXT 검수 표시(7/26·오표시 0/17, 판정 영향 0). 시험 RED 18/19·7/7 → GREEN 52/52. T2·완성부 \n·G5·출력 공백은 결정 목록(코드 변경 없음). 학습·추론·GPU·유료·x600·고객 자료 0
status: draft
domain: travel
---

# SFT 합성 검사기 후보 0.3 — T3·T1·M1·M3 반영과 남은 결정 (2026-10-31)

이전: [템플릿·토크나이저 동일성·근거 판별 일반화](2026-10-31_sft-template-tokenizer-parity-grounding-feasibility.md) §2·§3·§4 · [합성 검사기 독립 검토](2026-10-31_sft-distill-synthetic-checker-independent-review.md)
후보: [`program/research/sft_distill_synth_review_2026-10-31/candidate_v0_3/`](../../../../program/research/sft_distill_synth_review_2026-10-31/candidate_v0_3/README.md)(git 미추적)
작성: Claude Opus 5.5 하위 작업자, 2026-10-31 05:38~06:20 KST. **학습 0 · 모델 적재·추론 0 · GPU 0 · 유료 0 · x600 접속 0 · 고객 자료 0 · 운영 변경 0 · 커밋 0.** 로컬 Ollama 는 부르지 않았다. llama-tokenize 는 CPU(어휘만)로 실행했다. 판정 모델과 서빙 계약은 바꾸지 않았다.

## 0. 결론

1. **T3 고침.** 렌더된 서빙 prompt 전체를 바이트 그대로 stdin 에 한 번(`--no-bos`) 넣어 센다. 여유 가정 32는 지웠다. 서빙 prompt 10/10 = 100% 가 동일성 실측과 같았다.
   - system 7,439, 템플릿 표지 13, user 몫 12,288−1,200−7,439−13 = **3,636**
   - 0.2 의 과대는 208–255
   - 경계 결론은 그대로다. 격자 21 사례 중 결론이 바뀐 것 0/21이다. 32항목·8턴은 적합(여유 633), 48항목·4턴은 초과(−199)다.
2. **T1 반영.** 행마다 「학습 prompt 렌더 == 서빙 렌더」를 fail-closed 로 검사한다.
   - 학습 템플릿은 HF sha `0a2c8073c878ab1da004bee933a998606537bbb62016310352c7285c3f01c5b5`로 고정한다. 파일 sha 가 다르거나 행이 선언한 sha 가 다르면 `E_TRAIN_TEMPLATE_PIN`이다.
   - 모델 이름에 `12b/26b/31b`가 있으면 `E_LARGE_RENDERER_MODEL`, 빈 생각 블록이 있으면 `E_EMPTY_THOUGHT_BLOCK`이다.
   - 양성 7/7 은 학습 렌더 sha = 서빙 렌더 sha = 동일성 실측 sha 였다.
3. **M1 반영.** 정답 JSON 전체를 비교한다(보이는 글 칸은 값만 뺀다). 기준 정답이 없으면 `E_REFERENCE_MISSING`이다.
   - 79행 기준 구조 변경 거부 23/24. 남은 1건은 잘린 JSON 이라 `E_JSON_PARSE`로 이미 거부된다.
   - 받아야 할 것 오표시 0/17
   - **보류 탐침 HN9 가 닫혔다**(`E_REFERENCE_MISMATCH`). 보류 탐침에서 놓친 수는 0.2 의 7/12 에서 6/12 로 줄었다.
4. **M3 반영.** `R_ENTITY_IN_FREE_TEXT`는 검수 표시만 한다. 79행에서 보이는 글 거부 7/26 을 표시했고(social·일반 답 4, advice 3) 오표시는 0/17 이었다. 동일성 보고 수치를 재현했다.
   - 판정 영향은 0이다. 표시를 끄고 켜도 errors·ok 가 같다(시험).
   - 비어 있지 않은 보이는 글 칸은 모두 `human_rubric_queue`(rubric 부류 5개)로 나간다. 남은 19/26 이 모두 큐에 들어갔다.
5. **시험.**
   - 새 시험 19개: 0.2 도구에서 18/19 실패(RED)
   - 독립 검토(Codex 1회) 반영 시험 7개: 반영 전 트리에서 7/7 실패(RED)
   - 최종 **52/52 = 100%**(기존 26 + 새 26), 부정 39/39 = 100%, 양성 7/7
   - 0.2 와 같은 조건(M1 끔)의 절제 값은 0.2 와 같다. 기존 기준은 약화하지 않았다. 기존 시험은 수정 0개이고, 부정 사례의 기대 코드도 그대로다.
6. **결정 목록 4건**(§3)은 코드를 바꾸지 않고 선택지와 승인 필요 여부만 정리했다.

## 1. 바꾼 것 (후보 0.2 대비)

| 항목 | 내용 | 근거 |
|---|---|---|
| `tools/token_budget.py` | 임시 파일 제거. stdin 바이트로 보내고 `tokenizer_args`(config)를 쓴다. 실행 파일·어휘 sha 고정(크기·수정 시각이 바뀌면 다시 해시). 빈 결과·형이 틀린 결과는 실패 | `evidence/t3_budget_recount.json` |
| `tools/render_parity.py`(새) | 서빙 = Ollama v0.31.1 gemma4 small 포트(sha 고정, 해시한 바이트를 그대로 실행). 학습 = HF jinja. 비교 | 시험 `T1RenderParity` |
| `tools/target_check.py` | T3 실측 예산(`budget`), T1, M1 `reference_errors`(dict/list·JSON 형 구분, 보이는 글은 있음/없음·형 비교), M3 `review_flags`·`rubric_queue`·`human_review_pending`. 예산·렌더·정답 비교 `enabled=false`는 멈춤 | 시험 `M1ReferenceCompare` · `M3ReviewFlag` · `CodexReviewFixes` |
| `tools/negatives.py` | 양성에 `reference_target`. 부정 +4: K6 large 이름, K7 템플릿 sha, R1 question 변경, R2 기준 정답 없음 | `evidence/negative_suite_run.json` |
| `tools/run_suite.py` | 부류 `reference_compare`, 절제 값 `missed_when_class_and_m1_disabled` | 같은 파일 |
| `tools/budget_boundary.py` · `tools/grounding_recheck.py`(새) | T3 재측정, 79행 M1·M3 재현 | `evidence/*` |
| `config/prep_config.json` | `context_budget_check`(여유 삭제, args·sha), `render_check`, `reference_compare`, `review_flags` | — |
| `fixtures/hf_chat_template.jinja`(18,569B) · `tools/ollama_gemma4_port.py` | 템플릿은 기존 캐시가 없어(scratch 가 지워짐) HF `ee0ef602` 에서 다시 받았다. sha 가 parity evidence 와 같았다. 포트는 검증물 사본이며 sha 가 같다 | — |

### 독립 검토(Codex CLI, 읽기 전용 1회) 지적과 처리

| 지적 | 처리 |
|---|---|
| (높음) 어휘·템플릿 캐시가 고정 확인을 건너뜀 | 어휘는 (경로·크기·수정 시각) 키로 다시 해시, 템플릿은 부를 때마다 다시 읽어 해시. 시험 2개 |
| (높음) M1·T3 를 설정으로 조용히 끌 수 있음 | `enabled=false` → SystemExit. 시험 1개 |
| (높음) 잎 경로 평탄화가 dict/list·true/1 을 구별 못함 | 튜플 경로·JSON 형 비교. 시험 1개 |
| (중간) 보이는 글 칸 삭제가 숨겨짐 | 있음/없음·형은 비교하고 값만 제외. 시험 1개 |
| (중간) 고정 파일과 import 모듈 연결 약함, jinja 경로 영구 추가 | 포트는 해시한 바이트를 고유 이름으로 실행. jinja2 버전을 고정하고, 경로는 import 동안만 넣는다 |
| (중간) 검수 큐가 있어도 ok=true | `human_review_pending` 표시. 학습 투입 관문 연결은 **미구현**(한계) |
| (중간) 양성 기준 정답이 동어반복 | 한계로 기록(§4) |
| (낮음) 실행 파일 sha·빈 출력 | 실행 파일 sha 고정, 빈 결과·bool 거부. 시험 1개 |

## 2. 실행 결과 (센 값)

| 검사 | 결과 | 파일 |
|---|---|---|
| 0.2 사본 기존 시험 | 26/26 | `evidence/baseline_v0_2_copy_unittest.txt` |
| 새 시험 on 0.2 도구 | 실패 18/19(통과 1 = 보이는 글만 바꾼 경우 M1 비표시, 회귀 방지용) | `evidence/red_v03_new_tests_on_v0_2_tools.txt` |
| 검토 반영 시험 on 반영 전 | 실패 7/7 | `evidence/red_review_fixes_on_prefix_tree.txt` |
| 최종 | **52/52** · 부정 39/39 · 양성 7/7 | `evidence/unittest_negative_suite.txt` · `negative_suite_run.json` |
| T3 서빙 prompt | 10/10 실측 일치, 0.2 과대 208–255, 경계 결론 변화 0/21 | `evidence/t3_budget_recount.json` |
| M1 | 구조 거부 23/24, 오표시 0/17, HN9 거부 | `evidence/grounding_recheck.json` |
| M3 | 7/26 표시(HN4·HN5·U3·FN2·HN3·U6·FN3), 오표시 0/17, rubric 큐 19/26 | 같은 파일 |
| 보류 탐침(0.3, 맹검 아님) | FP 잘못 거부 1/6(HF6, 0.2 와 같음), FN 놓침 6/12(0.2 는 7/12) | 같은 파일 |

첫 GREEN 실행에서 시험 하나가 틀린 기대를 갖고 있었다(user 메시지 끝 공백 → 렌더 불일치 기대). 두 renderer 가 모두 trim 하므로 렌더는 같은 것이 맞다. 그래서 「끝 공백은 렌더 동일·해시 불일치만」과 「앞 글자 추가는 렌더 불일치」로 나눠 고쳤다. 제품 코드를 그 시험에 맞추지 않았다.

## 3. 결정·담당 목록 (코드 변경 없음)

| # | 항목 | 선택지 | 지금 결과 | 권고 | 승인 필요 |
|---|---|---|---|---|---|
| D1 | **T2 Ollama 토크나이저 직접 확인**(「좋아요ㅋㅋㅋㅋㅋ」 등 반복 문자, 포트 예측: ㅋ 5회부터 HF 와 다름) | (a) Go 툴체인을 설치하고 Ollama v0.31.1 `tokenizer` 패키지를 어휘 메타(`/api/show`)로 CPU 실행 (b) 승인된 서빙 호출의 `prompt_eval_count` 대조 (c) 확인 없이 학습 `input_ids`를 포트(go 동순위)로 만들고 HF 와 다른 행에 `E_TOKENIZATION_DIVERGENCE` 표시 | **미실행.** 이 호스트에 Go 가 없음(`which go` 없음). 포트 예측만 있음 | (a) 다음 (c). (b)는 모델 적재라 피함 | (a) 도구 설치(네트워크·디스크) 승인 · (b) 추론 승인 · (c) 학습 도구 담당 결정 |
| D2 | **완성부 끝 `\n` 손실 제외**(서빙은 `<turn|>` id 106 에서 멈추고, 학습 문자열 끝 `\n` id 107 은 서빙에서 생성되지 않음) | (a) 손실 마스크로 id 107 제외(템플릿 렌더는 그대로) (b) 그대로 학습 (c) 학습 문자열에서 `\n` 삭제 | 학습 문자열 = 서빙 + 정답 + `<turn|>\n` 7/7(동일성 검증). 0.3 검사기는 전체 렌더 접두사만 검사 | (a). (c)는 HF 템플릿 렌더와 달라져 T1 검사가 깨짐 | 학습 도구 담당 결정(G5). 학습 시작 자체는 별도 승인 |
| D3 | **G5 학습 도구 고정** | ① HF 템플릿 sha `0a2c8073…`(0.3 이 행마다 강제) ② BOS: 문자열 `<bos>` 1개만(템플릿이 넣음). 토크나이저 자동 BOS 끔(HF post_processor 는 BOS 를 안 붙임. 다른 도구의 add_bos 는 확인 필요) ③ input_ids: (a) HF 토크나이저 (b) 서빙과 같은 토크나이저(포트/Ollama)로 미리 만듦 (c) (a)+차이 행 표시 | ①은 검사기에 반영. ②·③은 도구 미정 | ① 고정, ② 「BOS 1개」를 시험으로 확인, ③은 D1 결과에 따라 (b) 또는 (c) | 학습 도구 담당 결정. 학습 실행은 G1~G7 승인 |
| D4 | **서빙 출력 JSON 공백 형식 대조**(학습 정답은 `json.dumps(ensure_ascii=False)` 기본 구분자 `", "`·`": "`. 생성 문법은 공백을 허용) | (a) x600 의 기존 원응답 로그를 읽기 전용으로 표본 대조 (b) 로컬에서 같은 blob 으로 추론해 대조 (c) 대조 없이 학습 정답 공백 형식을 문서로만 고정 | **미확인**(x600 접속 금지 범위) | (a) | (a) x600 읽기 접속 승인 · (b) 모델 적재·추론 승인 |

판정 모델 도입과 일반 답 구조화(서빙 계약 변경)는 이번 범위가 아니며 하지 않았다(동일성 보고 §3 의 선택지 2·3 그대로).

## 4. 한계 · 하드코딩·대체 기록

- **경로 하드코딩(config):** `render_check.jinja2_site_packages`는 Hermes 설치 판 번호가 든 경로다(3.12 venv 에 jinja2 가 없음). Hermes 가 갱신되면 행이 `E_TRAIN_RENDERER_MISSING`으로 실패한다. 조용한 대체는 없다. 버전은 3.1.6으로 고정했다.
- **라이브러리 내부 대체:** 3.14 용 markupsafe 를 3.12 에서 읽으므로 C 확장 대신 순수 파이썬 구현이 쓰일 수 있다. 렌더 sha 7/7 일치로 결과 영향이 없음을 확인했다.
- **포트:** 서빙 렌더·BPE 는 Go 원본이 아니라 포트다(동일성 10/10). `llama-tokenize.exe`는 실행 파일 sha 만 고정했고, DLL 은 고정하지 않았다.
- **M1 동어반복:** 손작성 픽스처에서는 기준 정답이 정답 자체다. 실제 자료에서는 기준 정답이 다른 출처여야 의미가 있다. 동등한 다른 구조 답(허용 집합)은 지원하지 않아 거부된다.
- **M3:** 일반어 제목(「점심」 등)을 개체로 볼 수 있다. 79행 합성 표본 한정이며 맹검이 아니다. `human_review_pending`을 학습 투입 관문에 연결하는 일은 남았다.
- 시험 기대값은 동일성 검증물 evidence 에서 읽는다(손으로 적은 수 없음).
- 보류 탐침은 이미 열람·실행한 것이라 맹검이 아니다. 새 보류 탐침은 별도 작성자 몫이다(동일성 보고 §4-5).

## 5. 정리·디스크·불변 확인

- 후보 0.2·이전 검토물·동일성 검증물 88개 파일의 sha256 을 시작·끝에서 비교했다(§인계). 새 폴더 `candidate_v0_3/`는 317,256B·43파일이다(복사 145,055B + 추가·변경 172,201B, Codex 검토문 `evidence/codex_review_once.txt` 포함).
- `disk_guard check`는 쓰기 전 allowed(C: 여유 220,248,363,008B, 목표 400GB 미달)였다. 대용량 사본은 0이다. 어휘 GGUF·HF tokenizer.json 은 복사하지 않았다(시험 하나가 어휘 15.8MB 를 임시 폴더에 잠시 복사하고 지운다). **주의:** 셸의 `TMPDIR=/tmp`가 Windows Python 에서 무효라 시험 임시 폴더가 시스템 Temp(`%LOCALAPPDATA%/Temp`)에 만들어졌다가 바로 지워졌다. 끝난 뒤 남은 것은 0이다. 다음 실행 때는 `TMPDIR`을 작업 scratch 의 Windows 경로로 준다.
- 임시 작업폴더 `…/cache/scratch/sft-v03-20261031/`(54파일, 672,906B: 시작·끝 해시, RED·GREEN 로그, diff, 반영 전 재구성 트리, 받은 템플릿)는 필요한 로그를 evidence 로 옮긴 뒤 직접 삭제했다. 남은 것은 0이다. 끝난 뒤 C: 여유는 220,002,107,392B 다.
- 인계·목차는 덧붙이기만 했다. 편집 전 sha256: `index.md` `0453fd39…`, 인계 `241d7edd…`.
