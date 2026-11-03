---
type: report
title: I01~I04·I06·I08 로컬 전용 공개 문구 — role-manager 계약 문구별 재대조와 이식 판정
status: verified
domain: travel
---
# I01~I04·I06·I08 로컬 전용 공개 문구 — role-manager 계약 재대조 (2026-10-26)

- 작성: 2026-10-26 KST · Hermes subagent(Opus) · Codex CLI 의견 2회(`codex exec -s read-only`, 파일 읽기만).
- 대상: role-manager tip `16d6b00ab240bd70f77bffd84ed7982bee8d44aa`(묶음 L 최종, push 안 된 로컬 tip).
- 입력: [묶음 L 보고서](2026-10-26_L_J실패해결_e9953838-16d6b00a.md) 5절, [로컬 전용 코드 감사](2026-10-26_로컬전용코드_vs_role-manager_감사.md) L02/L02b, [L07·L08·L02a 이식 후보](2026-10-26_L07-L08-L02a_role-manager_이식_후보.md) 결론 3, 수용 하네스 `acceptance49-L-20261026`.
- 증거 루트 `S = C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/port-I-rows-20261026` — `verdict.json`, `codex/q1.md·a1.md·q2.md·a2.md`, `ev/fast-16d6b00a/`, `gate4.sh`.
- 지킨 것: 원본 작업트리 코드 수정 0 · push 0 · 커밋 0 · 계약(wiki/external·decisions) 수정 0 · 하네스 수정 0 · 모델/유료/알림 호출 0 · DB 접근 0.

## 결론

1. **6행 모두 (b) 계약 변경 필요 — 이식하지 않는다.** 6행이 걸리는 검사는 하나다. `public_not_registered_reply`(`acceptance49-L-20261026/deps/support49.py:35`)는 접수 GET 에 공개 키 `response` 가 있고 그 `execution_status` 가 `review_required`, `answer` 에 「아직 여행을 등록하지 않았」가 있어야 통과한다. 이 키는 role-manager 계약에 없는 **새 공개 필드**다.
2. **문구 6개(W1~W6) 모두 (b)** 다. 판정 (a) 0/6 = 0%, (b) 6/6 = 100%. 기존 계약 안에서 「도메인 동작만 추가」로 닫히는 문구는 없었다.
3. **후보 커밋은 없다.** (a) 가 0건이라 TDD 이식 대상이 없다. Codex 도 「0건이면 후보 커밋을 만들지 않는 것이 맞다」고 봤다(`codex/a2.md`).
4. **빠른 관문은 실패 0 이다.** 새 worktree(`S/rm`, 16d6b00ab, 변경 없음)에서 다시 돌렸다. 선택 10,392건 중 통과 10,219 · 실패 0 · 오류 0 · 건너뜀 173이다. 실패 0/10,392 = 0%, 건너뜀 제외 통과 10,219/10,219 = 100%. 묶음 L 의 값과 같다.
5. **수용 판정은 그대로 둔다.** 6행은 role-manager 대상에서 N/A(통과로 세지 않음)다. 6행의 다른 검사 112 − 6 = 106개는 모두 pass 다(`reverdict-J02-L.json`). 엄격 통과 0/6 = 0%, N/A 포함 비실패 6/6 = 100%.

## 1. 계약 대조 근거

| 근거 | 내용 |
|---|---|
| role-manager 접수 GET 계약 | `final_project_cs/wiki/external/rest-endpoints/web-intakes.md:20`(GET) · `:24`(confirm) · `:25`(plan) — `response` 키 정의 없음 |
| role-manager 실관측(J 2차, `acceptance49-J-20261026/runs/J-real-729a3ed3-02-localstream`) | I01·I06·I08 접수 GET 최상위 키 22개에 `response` 없음. `status: review` · `trip_id: null` 로 「등록 전」은 이미 표현된다(하네스 `no_registration` 검사 pass) |
| role-manager 전체 검색 | `execution_status` · `review_required` · `confirmation_recorded` · `plan_generated` — 제품 · wiki · `frontend` · `final_project_ui` 에서 0건 |
| 이 키를 정의한 문서 | `wiki/external/travel-response.md` · `wiki/external/web-response-status.md` — 원본 로컬 작업트리의 **미추적 파일**이고 role-manager 에 없다. 두 문서 모두 「선택 필드를 더한다」는 가산형 공개 계약이며 「계약 소비자 검토 · 운영 승인 미완료」라고 적혀 있다 |
| 앞선 판정 | 감사 L02b · L02a 이식 결론 3이 계획 writer(`response/plan.py`)를 「관찰 가능한 공개 계약 변경(UI 협의)」으로 보류했다 |

## 2. 문구별 판정

출처: 로컬 계보 `integ-v9-20261026-025943/source/final_project_cs/app/domains/travel_ops/components/response/plan.py`.

| ID | execution_status · 문구 | 공개 자리 | 판정 | 근거 |
|---|---|---|---|---|
| W1 | `reading` 「계획서를 읽고 있어요. 아직 여행을 등록하지 않았어요.」 | 접수 GET · edits · restore 의 `response` | **b** | 새 공개 키 + 새 enum |
| W2 | `review_required` 「계획서의 읽은 내용을 검토해 주세요. 아직 여행을 등록하지 않았어요.」 | 같은 자리. **6행 검사 대상** | **b** | 위와 같다. 검사가 `response.execution_status` 를 본다 |
| W3 | `failed` 「계획서 읽기 또는 확인을 마치지 못했어요. …」 | 같은 자리(review_error · blocked 근거일 때) | **b** | 새 공개 실패 상태. 기존 `review_error` · `blocked` 와 뜻이 겹친다 |
| W4 | `confirmation_recorded` 「접수에 등록 상태가 기록되어 있어요. …」 | 같은 자리(confirmed) | **b** | 새 공개 상태 |
| W5 | `registered` 「여행 등록과 저장을 확인했어요. …」 | `…/confirm` · 웹 `…/plan` · `/v1/trips/plan`(등록) 결과의 `response` + `verify_plan_registration` | **b** | 새 공개 키. 검증만 따로 떼는 안은 아래 3절에서 기각 |
| W6 | `plan_generated` 「초안 일정을 만들었어요. 아직 여행을 등록하지 않았어요. …」 | `/v1/trips/plan`(미등록 초안) 결과의 `response` | **b** | 에이전트 API 에 새 공개 키 |

## 3. 검토하고 기각한 우회안 (Codex 와 같은 결론)

| 안 | 판정 | 이유 |
|---|---|---|
| 기존 공개 필드(`stage_label` · `check` · `needs_review[].note`)에 W2 문장 넣기 | 기각 | 검사는 `response.execution_status` 를 보므로 통과하지 않는다. `stage_label` 은 단계 이름이고 SSE `state` 에도 같은 값으로 나간다(`web-intakes.md:125`). 넣으면 기존 필드의 뜻이 바뀐다 = 계약 변경 |
| writer 결과를 내부(Case · 접수 기록)에만 남기는 「내부 이식」 | 기각 | 소비자가 없다. RULE.md 「사용하지 않는 선행 기능을 만들지 않는다」에 걸린다. 공개 검사도 닫지 못한다 |
| `verify_plan_registration`(커밋 뒤 범위 재조회)만 단독 이식 | 기각 | role-manager confirm 은 이미 한 트랜잭션 안에서 생성 · `mark_confirmed` 를 하고 request_id 로 멱등이다(`trip_api.py:2074-2086`). 커밋과 재조회 사이에 판이 오르면(감시 자동 변경 · 다른 탭) **등록은 됐는데 500** 이 난다. 문장이 보류인 동안 더하는 보장이 없다 |
| 하네스에서 이 검사를 빼거나 OR 로 넓히기 | 하지 않음 | 시험 약화 금지. 묶음 L 의 N/A 처리(대상 명시 · 통과로 세지 않음 · 오타 대상 중단)를 그대로 둔다 |

## 4. Codex 논의

- q1(`codex/q1.md` → `a1.md`): W1~W6 전부 b. 기존 필드 재사용 안 b(통과도 안 하고 의미 훼손). 내부 이식 b(미사용 선행 기능). N/A 유지가 맞다. Q4(검증 단독)만 「분리 검토 가능하나 커밋 뒤 ValueError 방식은 그대로 이식할 근거 부족」.
- q2(`codex/q2.md` → `a2.md`): 검증 단독 이식도 제외. 「(a) 0건이면 후보 커밋을 만들지 않는 것이 맞음」.

## 5. 빠른 관문

- 위치: 새 worktree `S/rm`(`git -C …/allpast-hotfix-20261025-2005/repo worktree add --detach`, HEAD `16d6b00ab240…` — `ev/fast-16d6b00a/head.txt`). 작업트리 변경 0.
- 명령: `bash S/gate4.sh fast-16d6b00a`. 묶음 L `gate.sh` 와 선택 · 마커(`not live and not db and not slow`) · 격리 runner(`run_isolated.py` 사본: 네트워크 · DB 차단)가 같다. 프로세스만 8+1 → 3+1 = 4개로 줄였다(CPU 4스레드 이내, BLAS 스레드 1).

| 묶음 | 선택 | 통과 | 실패 | 오류 | 건너뜀 |
|---|---:|---:|---:|---:|---:|
| s9(architecture · contract · security · eval · unit 비여행) | 2,348 | 2,302 | 0 | 0 | 46 |
| shard_00(unit/travel 1/3) | 2,137 | 2,032 | 0 | 0 | 105 |
| shard_01(2/3) | 2,665 | 2,643 | 0 | 0 | 22 |
| shard_02(3/3) | 3,242 | 3,242 | 0 | 0 | 0 |
| **합계** | **10,392** | **10,219** | **0** | **0** | **173** |

모든 프로세스 exit 0(`ev/fast-16d6b00a/exit.txt`). 건너뜀은 분모에서 빼지 않고 따로 적었다.

## 6. 남은 일

1. W1~W6 공개 `response` 를 role-manager 에 넣을지는 **계약 결정**이다. 넣는다면 순서는 이렇다: `travel-response.md` · `web-response-status.md` 를 정본 wiki 로 옮기고 검토 → `web-intakes.md` GET · confirm · plan 에 선택 필드 정의 → 웹(`final_project_ui` 포함) 소비 협의 → 그 뒤 TDD 이식. 그때 W5 는 커밋 뒤 재조회 불일치를 500 으로 만들지 않는 설계가 함께 필요하다.
2. 그 결정 전까지 6행은 role-manager 대상 N/A 로 따로 센다(통과로 세지 않음).
3. 로컬 v9 웹은 이 필드를 소비한다. B 전략(role-manager 기준 재구축)으로 바꾸면 로컬 화면의 응대 상태 문장이 사라진다(감사 4절과 같은 경고).

## 한계

- 계약 대조는 role-manager 트리의 wiki · 코드 · 웹 소스 정적 검색과 J 2차 실관측 파일로 했다. 실 E4B 재실행은 하지 않았다(코드 변경이 없어서).
- 빠른 관문은 변경 없는 tip 을 다시 확인한 것이다. 새 기능의 GREEN 증거가 아니다. DB 시험은 다시 돌리지 않았다(묶음 L 68/68 그대로).
