---
type: handoff
title: A11 P2 독립 검증 — 고객이 숙박으로 고른 짝 없는 체크아웃 줄의 등록 막음 · 화면 안내 · 실제 해결 길
status: draft
domain: travel
---

# 결론

기록 2026-10-29 KST, Hermes(Claude) 서브에이전트. 대상은 [A11 P2 · P3 수정](2026-10-29_routing-a11-checkout-choice-review-fix.md)이고, 후보 트리 `C:/_proj/routingresume1029`(HEAD `d1b06357e`, 커밋 안 함)를 이어 썼습니다. 새 clone · DB · pip 설치는 0건입니다. 보호 XML 보안 HOLD는 그대로 두었습니다(manifest 118/118 = **100%** 해시 같음). push · 배포 · 운영 DB 쓰기도 0건입니다.

앞 수정을 독립적으로 검증했습니다. 고객이 확인 화면에서 종류를 직접 고친 길(`items[n].kind`, `customer`)에서는 등록이 막히고 문구도 보였습니다. **실제 고객 경로에서는 결함 3건이 더 나와 고쳤습니다.**

1. **고객 선택이 덮임(P2).** 체크아웃 줄에 식사 말 같은 다른 종류 말이 함께 있으면 종류 확인 질문이 붙습니다(예: 「체크아웃 후 라운지 브런치」). 읽기 AI가 그 줄을 숙박으로 읽었고 고객이 **1안 「숙박」**을 고르면, `interpretations.edits_for`는 고칠 것이 없다고 보고 답 값 줄(`reading.answer:<id>`)만 남깁니다. 그래서 `_stays`는 이 줄을 고객 선택으로 보지 않았습니다. 줄은 「들르는 일정(activity)」으로 바뀌었고 문제 0으로 등록할 수 있었습니다. 질문 화면에는 답이 「숙박」으로 보였습니다. probe 증거: `indep/probe_after.jsonl`의 수정 전 대조(`two-kinds-answer-reading`).
   - 고친 것: 새 `interpretations.answered_kinds`가 질문 답을 읽습니다. 1안을 고른 답은 읽은 종류로 풉니다. `assemble.collect`가 이 값을 줄에 달고, `_stays.picked`는 `customer` 고치기 **또는** 숙박 답을 고객 선택으로 봅니다. 결과는 종류 숙박 유지 · 끝 없음 · `stay_without_check_in`으로 등록 막음입니다.
2. **안내대로 해도 화면에서 풀 수 없었음.** 확인 화면 「일정 추가」 폼(`add-stop.tsx`)은 종류를 **활동 · 식사만** 고를 수 있고, 장소를 고르면 이름을 장소 이름으로 채웁니다. 「서울신라호텔」 활동을 추가해도 체크인이 되지 않아 문제가 남았습니다. 실제 `newStopEdits` 여섯 칸을 `pipeline._checked`에 넣어 확인했습니다. 이름에 「체크인」이 들어가야 기존 `_stays` 규칙으로 짝이 지어지고 문제가 풀립니다.
   - 고친 것: 문구를 「「…」 — 숙박으로 고르셨지만 … · 체크아웃 전에 「서울신라호텔 체크인」 일정을 넣거나 들르는 일정으로 바꿔 주세요」로 바꿨습니다. 짝짓기 규칙은 바꾸지 않았습니다. 호텔 이름만 있는 활동은 고객 의도를 짐작하지 않고 문제를 그대로 남깁니다.
3. **대체 화면에서 안내가 안 보였음.** 시각 없는 짝 없는 체크아웃 줄의 「체크아웃 시각이 아니에요」 말은 `review._time_line`(warn)에만 있었습니다. 종류 안내(`items[n].kind` 채움)도 `check.filled`의 시각 칸만 읽는 접수 기반 대체 화면(`plan-check/from-intake.ts`)에는 보이지 않았습니다.
   - 고친 것: `assemble._checkout_time_notes`가 그 줄 `filled`의 `items[n].starts_at` 메모를 「체크아웃 시각이 적혀 있지 않아 일정 배치 규칙으로 HH:MM에 두었다 · 실제 체크아웃 시각이 다르면 고쳐 주세요」로 바꿉니다. 시각 값과 배치 규칙은 그대로입니다. `from-intake.ts`는 `kind` 채움도 시간 줄에 함께 보입니다. `review._time_line`의 warn은 그대로 1번만 보입니다.

새 상수 · 임계값 · 시각 값 · 숙박 기간은 하나도 만들지 않았습니다. 등록 막음은 기존 `check.problems` 계약을 따릅니다(`trip_api` 확정 422).

# 바꾼 파일(후보 트리, 커밋 안 함, CRLF 유지, `git diff --check` 통과)

- `final_project_cs/app/domains/travel_ops/components/intake/interpretations.py`: `answered_kinds` 추가, `__all__` 갱신.
- `.../intake/assemble.py`: `collect`에서 `kind_answer`를 달고 `_checkout_time_notes`를 호출합니다. `_stays`에 `picked`(lone/chosen)를 넣고 `open_stay` 문구를 바꿨습니다.
- `final_project_cs/frontend/apps/web/src/features/plan-check/from-intake.ts`(+ `.test.ts`에 시험 1건): `FILLED_FIELDS`.
- `final_project_cs/wiki/external/rest-endpoints/web-intakes.md`의 「숙박」 절에 이 계약을 적었습니다.
- 새 시험 `final_project_cs/tests/unit/travel/test_intake_stay_checkout_answer_path.py`(7개): 실제 `read_source`, 질문 `view` → `edits_for` → 답 값 줄, 「일정 추가」 `_checked` 길을 씁니다.
- 시험 실행 보조(untracked): `frontend/apps/web/a11-indep.vitest.config.mts`(캐시를 증거 폴더에 둡니다). `frontend/apps/web/node_modules`는 원본 `C:/_proj/final_workspace/final_project_cs/frontend/apps/web/node_modules`를 가리키는 **연결점(junction, 복사 0 바이트)**입니다. 두 파일 모두 이 세션이 만들었고 지우지 않았습니다. 연결점을 지울 때는 `rmdir`로 연결점만 지워야 합니다(대상 폴더 재귀 삭제 금지).

# 실행 결과(DB · 외부 연결 차단: 닫힌 포트 DB URL + guard sitecustomize, 3.12 격리 실행기)

| 실행 | 결과 |
|---|---|
| RED(새 시험 7, 수정 전) | 3/7 통과 = 43%. 실패 4건은 결함 ①②③과 같습니다 |
| GREEN(새 시험 + 앞 A11 시험 + 호텔 종류 시험) | 37/37 = **100%** |
| 확대(앞 인계 확대 98파일 + 새 파일 = 99) | **1275/1275 = 100%**, `hash_same: true` |
| 웹 RED(from-intake) | 11/12, 실패 1건이 결함 ③입니다 |
| 웹 vitest 전체 | 137 파일 · **1228/1228 = 100%** |
| 웹 `tsc --noEmit` | 오류 0 |
| `find_leaks`(바뀐 파일 7개) | 0건 |

DB 관문(회귀 1510 · 계약 · 보안 · DoD)은 다시 돌리지 않았습니다. 실제 모델 · 브라우저 화면 수락도 확인하지 않았습니다.

# 증거(`C:/_proj/routinga11p2fix1029_evidence`, 이번 추가 약 0.6 MB)

- `indep/before/`: 수정 전 사본.
- `indep/apply_fix.py`, `indep/apply_front*.py`: 정확히 1회 치환.
- `indep/probe_kind_answer.py`, `indep/probe_add_checkin.py`, `indep/probe_after.jsonl`.
- `indep_red/`, `indep_green1/`, `indep_expand/`(pytest.xml · log · run.json).
- `indep/front_red.log`, `indep/front_green.log`, `indep/front_all.log`, `indep/tsc.log`.
- `indep/candidate-tracked.after.patch`, `indep/xml-preservation-check.json`.

삭제는 0건입니다.

# 남은 것

1. 보안 XML HOLD를 정식으로 처리하기 전에는 통합 · push하지 않습니다. 이번 변경으로 DB 관문을 다시 돌려야 합니다.
2. 이번 수정도 독립 검토가 필요합니다.
3. 질문에 **아직 답하지 않은** 상태에서는 계약상 「1안으로 계산」이어야 합니다. 그런데 짝 없는 체크아웃 줄은 A11 규칙이 활동으로 계산하고, 질문은 1안 「숙박」을 보입니다. `kind_unanswered`가 등록을 막고 시간 줄에 종류 안내도 보이므로 이번에는 고치지 않았습니다. 사용자 결정 거리입니다.
4. 「일정 추가」 폼에 숙박 종류가 없는 문제는 프런트 설계 결정이라 손대지 않았습니다. 지금은 문구로 「<호텔> 체크인」 이름을 안내합니다.
5. 질문이 없는 줄(「…체크아웃」만 적힌 줄, 종류 말 1개)은 확인 화면에서 숙박으로 고를 UI가 없습니다. 이 줄을 고객 선택 숙박으로 만드는 길은 API 직접 고치기뿐이라 위 ①의 범위 밖입니다.
6. 독립 검토 P2(좌표 차이 167 m인 같은 호텔)는 별도 요구로 그대로 남아 있습니다.
