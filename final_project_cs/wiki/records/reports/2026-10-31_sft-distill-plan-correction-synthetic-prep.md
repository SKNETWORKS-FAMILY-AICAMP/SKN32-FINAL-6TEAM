---
type: report
title: SFT 증류 계획 정정과 합성 검사 준비물 — 배포 JSON 전체 목표·부정시험 35/35·관문별 문항 수·승인 경계 (2026-10-31)
description: 독립 검토 지적을 배포 코드(fab3da50a)·G 말뭉치·wiki 승인 기록과 대조해 계획을 정정. 고객 자료 0 합성 픽스처로 배포 decide() 재현 검사기와 부정시험을 실제 실행(양성 7/7, 부정 35/35 검출). 학습·추론·teacher 라벨·유료·x600 0
status: draft
domain: travel
---

# SFT 증류 계획 정정과 합성 검사 준비물 (2026-10-31)

대상: [원 계획](2026-10-31_sft-distill-training-plan.md) · [독립 검토](2026-10-31_sft-distill-plan-independent-review.md)
준비물: [`program/research/sft_distill_synth_prep_2026-10-31/`](../../../../program/research/sft_distill_synth_prep_2026-10-31/README.md)

작성: Claude Opus 5.5 하위 작업자. **학습 0, 모델 적재·추론 0, teacher 라벨 생성 0, 유료 API 0, x600 접속 0, 실제·고객 자료 사용 0, 운영 변경 0.** 원 계획·검토 파일과 기존 시험 파일은 수정하지 않았고(원 계획 맨 위에 정정 안내 한 줄만 추가), 다른 세션의 메모리 진단과 겹치지 않도록 모델·GPU를 쓰지 않았습니다.

## 0. 결론

1. 독립 검토의 심각 3건은 **근거와 코드로 모두 확인됐습니다**(§1). 계획을 이렇게 정정합니다: 학습 목표는 **배포 JSON 전체**(enum 칸 + `social`·`general_requests[].answer`·`reads[].advice`)이고, adapter를 A/B로 나누지 않으며, 평가는 칸별로 따로 냅니다.
2. 배포 `decide()`를 모델 없이 그대로 재현하는 검사기를 만들어 **실제로 실행했습니다.** 손으로 쓴 합성 양성 7/7 = 100%가 배포 생성 스키마와 서버 경로를 통과했고, 부정 사례 35/35 = 100%를 기대한 코드로 검출했습니다. 단위시험은 15/15 = 100%입니다.
3. **배포 서버 검증은 라벨 품질 필터가 될 수 없습니다.** 같은 부정 사례에서 서버는 답변 공백 7/8, 근거 없는 주장 7/7, 대상 혼동 6/7, 스키마 오류 3/8을 그대로 받아들였습니다. 원 계획 §6의 「서버 검증기 통과」만으로는 생략·지어냄·오지목을 학습시키게 됩니다.
4. 문항 수는 384 대신 **관문별로 exact 계산**했습니다(§4). 주 가설(+3%p, A′ 대비)은 불일치율 10% 가정 시 독립 920쌍이고, family 군집(m=3, ICC 0.2)을 반영하면 약 1,288행입니다.
5. 학습 승인은 「없음」이 아니라 **상시 승인 기록이 있고 이번 트랙에 적용되는지가 불명확**합니다. 지금은 현재 지시에 따라 시작 금지이며, 막는 것은 관문 7개 중 열린 5개(기준선·A′·holdout·학습 기계·회귀 기준선)입니다. 유료·개인정보 외부·실제 자료·x600·서빙 교체 경계는 따로 기록했습니다(§5).

## 1. 검토 지적 대조

| 지적 | 대조 방법 | 결과 |
|---|---|---|
| 한 번의 호출 JSON에 사용자에게 보이는 문장이 섞임 | 배포 사본 `decision_unit.py`(sha `248328c5…`) | 확인. `decide()`의 모델 호출은 한 번이고(경로 3개 중 하나, L731–739), 필수 칸에 `social`·`general_requests`가 있습니다(L476). 서버가 일반 답에 `GENERAL_NOTE`를 붙여 `social`로 합칩니다(L873–875) |
| 공백이 학습될 위험 | 같은 파일 L851–868 | 확인. `social`이 있으면 빈 일반 답은 **오류 없이 버려집니다**(잡담 재생 7.7% 주석, L861). 근처 식당 일반 답도 조용히 비워집니다(L869–872). 아래 부정시험 P6-G3·P7-U4에서 실제로 서버가 받아들였습니다 |
| G 18,927행의 채팅 형식 0건 | `processed/*.jsonl.gz` 읽기 전용 재계수 | 확인. train 18,927행 중 decision_unit 표지 0행, 다른 분할도 모두 0([g_recount.json](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/g_recount.json)) |
| x600 num_ctx 12288 vs 로컬 8192 | 배포 `settings.py` L162 | 확인. 기본값 12288. L87 주석의 8192는 낡은 문구입니다. 검사기는 8192를 거부합니다(K1) |
| 기준선 0/47 · 메모리 | [골든 평가](../../../../wiki/records/reports/2026-10-31_guguroute-model-golden-eval.md), [메모리 진단](../../../../wiki/records/reports/2026-10-31_guguroute-golden-eval-memory-gpu-diagnosis.md) 읽기만 | 0/47 PASS로 기준선은 여전히 없습니다. 이 작업은 모델·GPU를 쓰지 않았습니다 |
| 기존 학습 승인 | `slm-model-evaluation.md` 「자동으로 이어갈 학습과 재평가」 | 기록은 있습니다. 다만 모델 비교 후보(혼합 짚기 평가) 맥락이고, 현행 서빙 E4B의 채팅 결정 증류를 명시하지 않습니다 → §5 |
| 384 표본 | exact 재계산 | 확인. n=384·346정답의 양측 95% CP 구간은 [0.8667, 0.929]로 검토 값과 같습니다. 관문 검정력 근거가 아닙니다 |

## 2. 계획 정정 (원 계획 대비)

| 원 계획 | 정정 |
|---|---|
| §4 Track A(enum) / Track B(자연어) adapter 분리, `E_TARGET_TYPE_MIX` | 한 manifest = 한 서빙 호출 계약, `target_scope=full_serving_json`만 허용(`E_TARGET_SCOPE`). 자연어 칸을 비운 정답은 `E_ANSWER_GAP_*`로 거부 |
| §6 라벨 필터 「서버 검증기 통과」 | 배포 **생성 스키마**(로컬 문법) + 서버 재생 + 대상 결합 + 답변 공백 + 근거 없는 주장 검사를 모두 통과해야 합니다. 유료·plain 스키마 경로 출력은 생성 스키마로 반드시 다시 검사합니다(서버는 필수 칸 누락·추가 칸·문자열 숫자를 받았습니다: S1·S2·S7) |
| §8 비교군 ①~⑤ | A1(프롬프트만)·A2(검색·서버 조립만)·A′(둘 다) 무학습 대조군 추가, 주 비교 = 후보+A′ 코드 vs A′ ([prereg_v2](../../../../program/research/sft_distill_synth_prep_2026-10-31/config/prereg_v2.json)) |
| §5 「과제당 384」 | 관문별 exact 문항 수(§4) |
| §7 시간·메모리(1.9k 토큰 과제 실측 이전) | 입력 계약상 system 15,629자(코드 주석 6,771토큰) + 사용자 입력, 생성 스키마는 턴마다 19만~22만 자입니다. 시간·메모리는 8~9k 토큰 기준 실측 전까지 「모름」으로 둡니다 |
| R09 「학습 승인 없음」 blocked | 학습 승인 = 상시 기록 있음·적용 범위 확인 1건. 차단 사유는 기술 관문으로 표시 |
| 운영 입력 계약 칸 없음 | system sha·user 렌더링 sha·생성 스키마 sha·num_ctx·num_predict·temperature·모델·renderer를 행마다 고정(`E_SYSTEM_MISMATCH`·`E_USER_PROMPT_MISMATCH`·`E_SCHEMA_MISMATCH`·`E_CONTEXT_MISMATCH`·`E_SAMPLING_MISMATCH`) |

### 운영과 같은 입력 context 계약 ([serving_input_contract.json](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/serving_input_contract.json))
- 호출: Ollama `/api/chat`, `think=false`, `messages=[system, user]`, `format=` 배포 `_schema(stops, changes, message=masked(message))`. 옵션은 num_ctx 12288, num_predict 1200(guardrails `travel.decision_unit.num_predict`), temperature 0이고, Modelfile 값은 top_k 64·top_p 0.95입니다.
- system: `decision_unit.SYSTEM + edit_intent.SYSTEM`, sha256 `003a670fd9d63ead…`, 15,629자.
- user 렌더링 순서: 지금(한국 시각) → 일정 목록(서버가 센 날·순번·끼니) → 바뀐 이력(최근 8) → 직전 대화(턴당 160자) → 구조화된 직전 답변 대상 → 화면에서 고른 일정 → 고객 문장(마스킹).
- 학습 예 모양: `[system, user] → assistant(JSON 전체)`, 생성 스키마 sha와 num_ctx를 함께 기록합니다(`target_check.training_messages`). G의 범용 지시문은 이 계약과 맞지 않아 그대로 쓸 수 없습니다.

## 3. 실제 부정시험 결과

실행: 2026-10-31, Python 3.12.15(기존 `date_risk_env_312`, 읽기만), 배포 사본 `fab3da50a`, 모델 호출 0, 네트워크 차단 시도 0건.

| 묶음 | 결과 | 배포 서버가 받아들인 수 |
|---|---|---|
| 합성 양성(손작성 7, 가상 장소) | 7/7 = 100% 통과(생성 스키마·서버·전 검사) | 7/7 |
| 답변 공백(인사 무응답·빈 일반 답·이유 없는 추천·「네.」·읽기 누락·식단 조언 누락) | 8/8 = 100% 검출 | 7/8 |
| 근거 없는 주장(「가장 유명한」·프롬프트에 없는 숫자·영업시간 단정·근처 가게 지어냄·취향 기억·메뉴 확인 주장·연도/평점) | 7/7 = 100% | 7/7 |
| 대상 혼동(다른 식당·다른 일정 이동·지시어 오결합·할 일 바꿈·읽기 요청에 쓰기·목록 밖 id·사실 종류 바꿈) | 7/7 = 100% | 6/7 |
| 스키마 오류(필수 칸 누락·추가 칸·목록 밖 할 일·인용 아닌 근거·일반 답 9개·잘린 JSON·문자열 숫자·25:00) | 8/8 = 100% | 3/8 |
| 입력 계약(num_ctx 8192·다른 system·다른 user 렌더링·다른 스키마·temperature 0.7) | 5/5 = 100% | 5/5(서버는 입력 계약을 보지 않음) |
| 합계 부정 | **35/35 = 100%** | 28/35 = 80% |
| 단위시험(위 + manifest 계약·승인 경계 10건) | **15/15 = 100%** | — |
| 검사기 절제 시험(부류별 검사를 끄면 놓치는 수) | 답변 공백 7/8, 주장 7/7, 대상 5/7, 스키마 6/8, 계약 5/5 | — |
| manifest CLI | 정상 manifest rc=0. A/B 분리·8192·teacher 라벨·학습 시작 요청 manifest rc=1(`E_TARGET_SCOPE`·`E_CONTEXT_MISMATCH`·`E_MIXED_CONTRACT`·`E_TEACHER_NOT_ALLOWED_NOW`·`E_TRAINING_GATE`) | — |

절제 시험에서 다른 부류가 일부 사례를 대신 잡은 것(예: T6은 스키마로, S3은 할 일 불일치로)은 겹친 결함 때문입니다. 각 부류의 검사가 비어 있지 않다는 근거입니다. 증거: [negative_suite_run.json](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/negative_suite_run.json) · [unittest 출력](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/unittest_negative_suite.txt) · [manifest CLI](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/manifest_cli_runs.txt).

한계: 공백·주장 검사는 **규칙 기반**입니다. 패턴 목록과 최소 길이는 `[제안]`이라 표현을 바꾼 지어냄은 놓칠 수 있습니다. 그래서 사람 rubric(2인, κ)을 대신하지 않습니다. 픽스처 7건은 검사기 시험용이고, 행동 범위(되돌림·범위 이동·날씨·근처 기준 등)를 대표하지 않습니다.

## 4. 관문별 문항 수 (exact, [근거](../../../../program/research/sft_distill_synth_prep_2026-10-31/evidence/sample_size_exact.json))

| 관문 | 출처 | 검정 | 독립 n(검정력 0.8) |
|---|---|---|---|
| 후보+A′ vs A′ +3%p | `[제안]` 원 계획 §8 | exact 조건부 McNemar, 단측 α 0.025 | 불일치 5%: 463 · 10%: 920 · 15%: 1,362쌍 |
| 행 PASS ≥95% | wiki 혼합 평가 기준(채팅 적용은 `[제안]`) | 단측 95% CP 하한 ≥0.95 | 참값 0.97: 624(정답 ≥602) · 0.98: 260(≥253) |
| 오지목 ≤1% | wiki 기준 | 단측 95% exact 상한 ≤0.01 | 오류 0이면 299 · 참값 0.2%: 628 · 0.4%: 1,441 |
| 공유 과제별 손실 ≤2%p | wiki 기준(과제별 적용은 `[제안]`) | 짝지은 비열등, exact 조건부 | 불일치 4%: 804 · 8%: 1,624쌍(과제마다) |

- 몬테카를로 대조(4,000회, seed 20261031): McNemar n=463 검정력 0.800, 정확도 n=624 0.812로 exact 값과 맞았습니다.
- 독립 단위는 family입니다. 행 수 = n × (1+(m−1)·ICC)이고, m=3·ICC 0.2이면 1.4배입니다. 이산 검정이라 n이 조금 더 커질 때 검정력이 잠깐 기준 밑으로 내려갈 수 있습니다(톱니).
- 불일치율은 아직 모릅니다. B0 vs A′ 파일럿에서 잰 뒤 다시 계산해야 합니다. 사람 2인이 수백~천여 쌍을 검수해야 하므로, 인력이 정해지기 전까지는 오지목 0건 299 같은 소표본 관문부터 운용할 수 있습니다.

## 5. 승인 경계 ([approval_boundaries.json](../../../../program/research/sft_distill_synth_prep_2026-10-31/config/approval_boundaries.json))

| 경계 | 상태 | 근거·조건 |
|---|---|---|
| 학습 | 상시 승인 기록 **있음**, 이번 트랙 적용은 **불명확**, 현재 시작 **금지** | 기록 범위: 「상위권·소형·기존 자원」 후보 대기열, 원본 보존, 자동 교체 금지. 오늘 지시는 평가·계약·자원 확인 전 시작 금지입니다. 새 승인 요청 대신 「적용 범위 한 줄 확인 + 관문 결과 통지」로 처리합니다 |
| 학습 시작 관문 | 2/7 = 29% 완료 | G3 입력 계약 고정·G7 문항 수 사전 등록은 완료. G1 기준선(num_ctx 12288)·G2 A′ 측정·G4 holdout 봉인·G5 학습 기계 8~9k 토큰 스모크·G6 공유 가중치 회귀 기준선은 열려 있습니다 |
| teacher 라벨 생성 | 금지(현재 지시) | `E_TEACHER_NOT_ALLOWED_NOW`·`E_LABEL_SOURCE_FORBIDDEN_NOW` |
| 유료 API | 미승인, 상한 0 | 승인 후에도 synthetic만 보냅니다(`E_PAID`) |
| 개인정보 외부 전송 | 금지 | 외부 모델에는 synthetic·public만 보냅니다(`E_EXTERNAL_PRIVATE`) |
| 실제 자료 학습 | 미승인 | 검수·비식별·승인 후 로컬 교사만 씁니다(`E_PRIVACY`) |
| x600 부하 | 미승인 | 운영 서버입니다(`E_X600`) |
| 서빙 교체 | 미승인 | 새 이름·digest 고정·롤백 절차가 있어야 합니다(`E_SERVING_SWAP`) |

## 6. 다음 순서 (진행 0/5 = 0%)
1. 학습 승인 적용 범위를 한 줄 확인합니다(사용자). 새 승인 요청은 아닙니다.
2. G1: 다른 세션의 메모리 진단이 끝난 뒤, 기준선을 num_ctx 12288로 측정합니다(평가자 소유).
3. G2: 라우팅·채팅 구현 담당이 A1/A2를 만들고, 같은 검사기와 평가로 비교합니다.
4. G4: 사람이 작성·검수한 holdout을 family 단위로 봉인합니다. 규모는 §4 표와 파일럿 불일치율로 정합니다.
5. G5·G6이 끝나고 teacher 라벨 생성 허용 지시가 있은 뒤에, 이 검사기를 teacher 출력의 필수 필터로 씁니다.

## 7. 산출물·백업
- 준비물: `program/research/sft_distill_synth_prep_2026-10-31/`(193KB, 파일 해시 `evidence/file_hashes.txt`). 배포 코드 사본: `scratch/sft-synth-prep-20261031/deployed_code_fab3da50a/`(17MB, disk_guard check 통과).
- 원 계획 파일에는 맨 위에 정정 안내 한 줄만 추가했습니다. 본문은 그대로입니다. 덮어쓴 파일이 없어 백업은 필요하지 않았습니다.
- 원본 저장소 Git: `tools/safe_git.py`가 Python에서 WindowsApps git을 실행하지 못해(WinError 5) 실패했습니다. 대신 `GIT_OPTIONAL_LOCKS=0`로 읽기 전용 `cat-file`·`log`·`ls-tree`만 bash에서 직접 실행했고, 로컬 원본에는 `fab3da50ab` 객체가 없다는 것을 확인했습니다. fetch·쓰기는 하지 않았습니다. 그래서 배포 코드는 골든 평가자 사본(GitHub blob과 6/6 대조됨)에서 가져왔습니다. safe_git 실행 경로 문제는 별도로 고쳐야 합니다.
