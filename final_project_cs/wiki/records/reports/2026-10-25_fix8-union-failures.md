# 2026-10-25 I06 합집합 실패 8건 원인 수정 (fix8)

결론: 8/8 = 100% 실제 통과. 같은 2184 exact nodeid 합집합은 **2184/2184 = 100%**(H 자료 하네스 공급 시, 실패 0·skip 0), 팀 CI와 같은 자료 조건에서는 2182 pass + 2 skip(실패 0)입니다. 제품 코드(app/config) 변경 0. skip·xfail·삭제·단언 약화 0.

- 작업 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/fix8-20261025-233836-57b3694d/` (기준 I06 후보 폴더는 읽기만 했고 수정하지 않음)
- patch: `fix8.patch` SHA256 `664813b174f36fa2c7a2d06c144d554b29b16dade8ce37e94cff2a0e62a3f793` — 동결 I06 source 사본에 `git -c core.autocrlf=false apply` RC0, 적용 결과 5204 파일 해시가 작업 사본과 동일(`roundtrip-check.json`).

## 원인과 수정

| 실패 | 원인 | 분류 | 수정 |
|---|---|---|---|
| A1–A3 g96 (3) | 후보 스냅샷이 git 추적 파일 `final_project_cs/eval/datasets/travel_{golden,holdout}.jsonl`을 빠뜨림 | 스냅샷 자료 누락 | 기준 6c34589b blob 그대로 포함(develop d2ab93a·원본 HEAD와 blob 동일) |
| A4–A5 rag (2) | 같은 이유로 `program/scripts/rag_gate/human_eval/{human_eval_sheet.html,1006_사람평가_A.csv,claude_opinion.json}` 누락 | 스냅샷 자료 누락 | 같은 방식으로 포함 |
| B1–B3 reading stream (3) | 후보의 reader 정책(`travel.intake_reader.external_fallback_enabled: false` 기본 차단 + 유료 시도별 strict `reader_budget`)이 팀 시험 이후에 들어옴. 팀 시험은 허용·gate 없이 유료 넘김을 기대 | 시험 fixture가 새 계약을 모름 | 시험 fixture에 strict reader gate를 주입하고, 유료 넘김 시험의 호출에서 `external_fallback_enabled=True`를 명시. 유료 시도마다 reserve 1회 단언 추가. 기본 차단을 확인하는 짝 시험 2개 추가 |

B의 판단 근거: [plan-reading-restoration 「공급자 안전 보완 계약」](../../external/plan-reading-restoration.md) 40·43행(gate 없음 fail-closed, 외부 기본 차단, 해제는 사용자 확인 대상)과 [reader-provider-safety 보고](2026-10-24_reader-provider-safety.md) 49행의 같은 처리 선례. 제품 기본값은 바꾸지 않았습니다.

## 검증

| 실행 | 결과 |
|---|---|
| RED (수정 전, 8 nodeid) | 8 failed — FileNotFoundError 5, `reader_external_disabled` 3 (`out/red8/`) |
| GREEN (8 nodeid) | 8/8 = 100% (`out/green8-nodata/`) |
| GREEN + 신규 짝 2 + H 2 | 12/12 = 100% (`out/green12-hdata/`) |
| 합집합 2184 (H 자료 공급) | 2184/2184 = 100%, 차단 사건 0, 원 실행과 nodeid 집합 동일, 결과가 바뀐 node는 8 fail→pass·2 skip→pass뿐 (`out/union-hdata/`) |
| 합집합 2184 (H 자료 없음, 팀 CI 조건) | 2182 pass, 2 skip, 0 fail (`out/union-nodata/`) |
| ruff (수정 시험 파일) | All checks passed |
| role-manager 08b99597 독립 추출 트리, 같은 8 nodeid | 8/8 = 100% → 해당 없음 (`out/rm-red8/`) |

## 2 skip

`pointing_h` 2건은 H 원본(`datasets/core/pointing/testset/confusing_trap_sentences_v1/h_set_test_30_20261015.json`)이 git 밖이라 없으면 건너뛰도록 설계됐습니다(32adb7817, 팀 CI도 skip). 이 PC에도 없어서 32adb7817^의 git blob(합성 시험 문장, PII 패턴 0)을 작업 폴더의 `harness-datasets/`로 꺼내고 `TRIPILOT_DATASETS_ROOT`로 가리켜 실제로 실행했고 2/2 통과했습니다. 이 자료는 patch에 넣지 않았습니다(git 밖 자료 규칙).

## 한계

- 제품 E4B·외부 유료 모델·네트워크·DB 호출 0. 격리 runner 단위 시험만 실행했고 전체 관문(DoD·contract·security 전체)은 실행하지 않았습니다.
- 서빙 교체·push 0.
