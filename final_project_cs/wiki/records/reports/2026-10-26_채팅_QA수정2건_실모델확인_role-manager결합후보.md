# 2026-10-26 채팅 QA 수정 2건 — 실 E4B 추가 확인과 role-manager 결합 후보

- 작성: 2026-10-26 01:00~ (KST), Claude Opus 하위 작업자. 커밋·푸시·x600 배포·로컬 서빙 교체는 하지 않았다(부모 몫). 원본 코드는 수정하지 않았다.
- 대상: [야외 교체 보고서](2026-10-25_채팅_실내를_야외로_바꿔줘가_실내로_바뀐다.md)(건 A), [고른 일정 대상 보고서](2026-10-25_chat-selected-stop-subject.md)(건 B). 두 보고서 본문은 각 patch 안에 있다.
- 모델: `tripilot-pointer:e4b-ft` digest ef0a580a…, 127.0.0.1:11434, num_ctx 8192, 동시 1, temperature 0. 호출마다 live(8042, v7a) 카운터 admitted=completed, `/api/ps`, E4B lease(`_coord/e4b_lease.py`, owner qa-verify) 확인. 실고객 DB·x600 쓰기·알림·유료 0.

## 결론

- 건 A: 「다른 곳으로 바꿔줘」 실패는 **이번 patch의 회귀**였다. 수정 전 코드는 통과, 첫 patch는 `place_search` 에 바꿀 일정을 기준(near)으로 적고 인용을 비워 `unquoted place_search` 로 실패. 프롬프트 두 줄을 더한 뒤 실모델 통과.
- 건 B: 최종 수정본으로 박물관을 고른 상태의 질문 2/2 = 100% 박물관으로 답하고 되묻지 않았다. 저장된 채팅(재조회)도 같은 답.
- role-manager 08b99597 기준 두 patch 결합: 코드 충돌 0, 공유 wiki 1곳 충돌은 양쪽 절 모두 보존. 결합 상태 전체 관문 실패 0.

## 실모델 호출 — 5/6회 사용 (A 3/3, B 2/3)

| # | 건 | 코드 | 문장 | 결과 |
|---|---|---|---|---|
| 1 | A | 원래 d2ab93a | 다른 곳으로 바꿔줘 | 통과: apply_change, place_search none |
| 2 | A | 첫 patch | 다른 곳으로 바꿔줘 | 실패: `unquoted place_search`(near·i1·evidence 빈칸). place_setting 은 any 로 정상 |
| 3 | A | 수정 patch | 다른 곳으로 바꿔줘 | 통과: #1 과 같은 해석 |
| 4 | B | 최종 | 거기 운영시간 알려줘 (박물관 선택) | 국립중앙박물관으로 답, 재조회 같음 |
| 5 | B | 최종 | 운영시간 알려줘 (박물관 선택) | 국립중앙박물관으로 답, 재조회 같음 |

- 운영시간 값은 시험 환경에 관광공사 조회가 없어 「모르겠어요」로 끝난다. 확인한 것은 답하는 대상이다.

## 추가 수정 (건 A)

- `edit_intent.SYSTEM` place_setting 안내 끝에 두 줄: place_setting 과 place_search 는 별개이고, 주변·근처 기준을 말하지 않았으면 place_search 는 none/빈 값이며 바꿀 일정을 기준으로 옮겨 적지 않는다. 검증기·휴리스틱 변경 없음.
- 시험 2개: 안내 문구 확인(RED 1/22 실패 → GREEN 22/22), 실모델이 낸 그대로의 칸이 여전히 실패하는지(검증기 약화 금지 확인).

## 시험

| 트리 | 관련 시험 | 전체 관문 `tests/architecture tests/contract tests/unit tests/security -m "not live and not db and not slow"` | ruff F,E9 |
|---|---|---|---|
| role-manager 08b99597 + A + B 결합 | place_setting 22/22, selected_subject 24/24 | 9,290 통과 · 실패 0 · 건너뜀 173 / 9,463 (통과 9,290/9,463 = 98.2%, 실패 0/9,463 = 0%) | 통과 |
| A 단독 role-manager 08b99597 | 22/22 | 9,266 통과 · 실패 0 · 건너뜀 173 / 9,439 | 통과 |
| A 단독 develop d2ab93a | 22/22 | 9,402 통과 · 실패 0 · 건너뜀 173 / 9,575 | 통과 |

- 각 관문 실행 전후 staged diff 해시가 같다(결합 `78b48196…`, A `962541c6…`). 실행 root 는 runner 첫 줄에 찍었고 develop 전용 시험(`test_dining_clarifications`)은 develop 트리에만 있다.
- 건 B patch 는 보고서 절 추가만 바뀌었다(코드·시험 동일). develop `b-repo.patch` `60f60d6e…`, role-manager `b-rolemgr.patch` `a88f3a8f…`.

## 남은 한계

1. 건 A 수정 프롬프트로 「실내를 야외로 바꿔줘」「야외로 바꿔줘」는 실모델로 다시 재지 않았다(A 예산 3/3). 야외 조건 추출은 첫 patch 프롬프트에서만 실모델 확인(2/2)이다.
2. 건 A 실모델은 결정 단위만이다. API→팀→저장 전 경로는 mock 시험뿐이다.
3. 건 B 의 모델은 여전히 relation=before 를 적는다. 이번 수정이 그 칸을 떼어 막는다.

## 산출물

- 작업 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/combo-rm-20261026/` (결합 트리 `combined/`, 증거 `evidence/`, 백업 `backup-*`)
- 결합 patch: `rolemanager-08b99597-chat-outdoor+subject.patch` sha256 `78b48196644b20506619bf00345e66d62a2037052b092c0391694ea52c96c958`
- 순서 patch: `1of2-chat-outdoor` `962541c6…`, `2of2-chat-subject-after-outdoor` `eb3e24f0…` — 차례로 적용한 tree = 결합 patch tree `8d62fee1`
