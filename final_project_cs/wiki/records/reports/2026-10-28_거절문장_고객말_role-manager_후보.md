# 2026-10-28 일정 검사 · 채팅 거절 문장을 고객 말로 — role-manager 커밋 후보

## 결론
- 후보 커밋 `bdb48ffc9035e175098592c2a64c9cc642e8732b`, 기준은 role-manager `1bc497956c94bbe5fa2a4ed98222dc0da5d82255`(ls-remote 팀 저장소). **push하지 않았다.**
- worktree: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/fix-refusal-wording-20261028-0756/rm`
- patch: `.../fix-refusal-wording-20261028-0756/out/fix-refusal-wording.patch`, sha256 `11573310abbd23088ffe9dce116134d9f80060bfd6fdef87bffb8b71441035c9`
- 빠른 관문(5 shard, `-m 'not live and not db and not slow'`): 실제 오늘 10699/10872 통과(실패 0, 오류 0, skip 173), `RELDATE_SHIFT_DAYS=37` 10699/10872 통과(실패 0, 오류 0, skip 173). 두 실행 모두 새 시험 23건을 포함했고, 실행 전후 바뀐 파일 해시가 같았다.
- 상태: 원격 반영 안 됨, x600 배포 안 됨, 로컬 서빙 반영 안 됨.

## 결함(x600 e78e038b 보고 `2026-10-28_x600_e78e038b_시각옮기기_확인.md`)
채팅 시각 변경 거절 답, 응답 `violations[].reason`과 `remedy`에서 고객에게 보이는 문장에 다음 문제가 있었다.
- 반말 평서형으로 끝났다.
- 숫자와 조사를 띄어 썼다(「19:00 까지」).
- 받침과 맞지 않는 조사를 썼다(「N서울타워(19:00 시작)이」, 「광장시장 를」).

## 고친 곳
| 파일 | 내용 |
|---|---|
| `itinerary/itinerary_checks.py` | 모든 위반 `reason`·`remedy`를 해요체로 바꿨다. 숫자 뒤 조사는 붙여 쓴다. 새 `particle()` 헬퍼가 한글 받침과 숫자 읽는 소리로 조사를 고르고, 영문처럼 읽는 소리를 모를 때는 「을(를)」·「(으)로」로 둔다. 내부 자료 이름(요식 원장·활동 원장)은 문장에서 뺐다. 「이름: 설명」 머리는 유지했다(`itinerary_delay.Knock.sentence` 호환). 새 `refusal_message()`는 422 메시지를 만든다. |
| `conversation/chat_edit.py` | `_refusal(itinerary_infeasible)`은 `violations[].reason`을 문장으로 잇는다. 위반 상세가 없으면 개발용 메시지를 다시 내보내지 않는다. `CommitRefused` 경로가 violations를 넘긴다. |
| `entry/trip_api.py`, `intake/reopen_commit.py` | 422 `itinerary_infeasible` 메시지를 `refusal_message()`로 만든다(「이 일정은 그대로 진행할 수 없어요 — …」). |
| `itinerary/itinerary_delay.py` | `knock_on_text`의 「점심 식사은(는)」을 받침에 맞는 조사로 바꿨다. |

- 공개 필드 `code`·`items`·`reason`·`remedy`는 그대로 두고 값 문구만 바꿨다. 고객 문장에는 순번을 넣지 않는다. `items`는 공개 필드라 남겼다.
- 영문 고객 문장: 서버가 만드는 영문 위반 문장은 없다. 웹 영문 화면은 `error-text.ts` 표의 영문 문장을 쓴다.
- 웹 확인:
  - 위반의 `remedy`는 웹이 그리지 않는다. 웹이 그리는 `remedy`는 여행의 `warnings`(품질·밀도 경고, `trip-attention.tsx:413`)이고, 이번 범위 밖이다.
  - 422 메시지는 이제 해요체로 끝난다. 그래서 웹(`error-text.ts` `POLITE_KOREAN`)이 일반 문구 대신 서버의 상세 문장을 보여 준다. 웹 코드는 바꾸지 않았으므로 vitest는 해당 없음.

## 문장 전/후
| 어디 | 전 | 후 |
|---|---|---|
| 채팅 거절 답 | 그렇게 바꾸면 일정이 맞지 않아 바꾸지 않았어요 — 북촌한옥마을: 19:00 까지인데 17:00 에 닫는다 / 지하철 3호선→4호선 50분 · 3.5km(19:50 종료)와 N서울타워(19:00 시작)이 겹친다 | 그렇게 바꾸면 일정이 맞지 않아 일정은 바꾸지 않았어요. 북촌한옥마을: 17:00에 문을 닫는데 19:00까지 머물게 돼요. N서울타워: 19:00에 시작하는데 앞 일정(지하철 3호선→4호선 50분 · 3.5km)이 19:50에 끝나 시간이 겹쳐요. |
| after_closing remedy | 17:00 이전에 끝나게 줄이거나 앞당긴다 | 17:00 전에 끝나도록 줄이거나 앞당겨 주세요 |
| overlap remedy | N서울타워 를 19:50 뒤로 옮기거나 앞 항목을 줄인다 / 광장시장 를 … | N서울타워를 19:50 뒤로 옮기거나 앞 일정을 줄여 주세요 / 광장시장을 … |
| 422 메시지 | 이 일정은 그대로 수행할 수 없습니다: …닫는다 | 이 일정은 그대로 진행할 수 없어요 — …머물게 돼요 |
| 휴무(활동) | 궁: 09월 23일은 쉬는 날이다(활동 원장 — 매주 화요일 휴관) | 궁: 안내 문구 「매주 화요일 휴관(공휴일 제외)」에 따라 9월 23일은 쉬는 날이에요 |
| 지연 안내 | 점심 식사은(는) 30분 늦어도 괜찮지만 … 15:30 까지인데 15:10 에 닫는다 | 점심 식사는 30분 늦어도 괜찮지만 … 15:10에 문을 닫는데 15:30까지 머물게 돼요 |

## 시험
- RED(`out/red.log`, rc=1): 새 시험 `tests/unit/travel/test_refusal_customer_wording.py` 7건 실패. `particle`·`refusal_message`·`violations` 인자 자리만 옛 문구로 먼저 넣은 상태에서 돌렸다.
- GREEN(`out/green.log`, `out/green2.log`): 관련 파일 82건과 43건이 모두 통과했다.
- 새 시험은 14개 위반 코드 전부에 다음을 건다.
  - 해요체로 끝난다.
  - 반말 평서형으로 끝나지 않는다.
  - 숫자 뒤 조사를 띄어 쓰지 않는다.
  - 한글 이름 뒤에 겸용 조사를 쓰지 않는다.
  - 문장에 「원장」이 나오지 않는다.
- 옛 문구를 단언하던 시험 7곳은 `contract_correction` 주석을 달고 새 문구로 바꿨다. 판정 단언(코드·거절·미반영)은 그대로다. 그중 `tests/scenario/test_apply_*recheck.py` 2곳은 DB 시험이라 빠른 관문에 들어가지 않아 **실행하지 않았다.**
- 빠른 관문 첫 실행(`out/*_interim`)은 실행 도중 소스를 고쳤으므로 중간 관측으로만 보관했다. 위 결론의 숫자는 안정된 트리에서 다시 돌린 결과다.

## Codex 검토(`codex/`, gpt-6.1-sol, 본문만 보는 검토, tokens 16,998)
판정은 approve_with_changes였고, 나온 지적은 다음처럼 처리했다.
- 인용문 괄호가 겹치면 웹이 문장을 해요체로 인식하지 못한다 → 인용문을 문장 가운데 「」로 옮겼다. 시험도 추가했다.
- `after_last_entry`와 폐업, `usable_minutes` 없는 분기를 시험이 다루지 않았다 → 시험에 추가했다.
- `IntakeConflict` 경로 확인 요청 → `itinerary_infeasible`을 내는 곳은 `trip_api`와 `reopen_commit` 둘뿐이라 해당 없음.
- 422 상세 노출은 받아들일 만하고, 시험 단언 변경은 검증 약화가 아니라고 했다.

## 남은 것
- 여행 `warnings`(품질·밀도 경고, `itinerary_quality.py`·`density.py`)의 `remedy`도 반말 평서형이다(「…바꾼다」). 웹 화면에 보이는 문장이므로 별도 후보가 필요하다.
- `planner.py`의 계획 위반 `remedy`도 같은 문제가 있다.
- push·x600 확인은 부모가 진행한다.
