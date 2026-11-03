---
type: report
title: 한 채팅 메시지의 여러 변경 (요식·활동 동시 수정) — 격리 후보
date: 2026-10-26
---

# 한 채팅 메시지의 여러 변경 — 격리 후보

사용자 요청: 「한번에 요식, 엑티비티 동시에 수정하거나 여러건 동시에 교차로 수정요청 챗으로 보낼수도 있잖아」.
계약: [trip-chat-context.md 「2026-10-26 한 메시지 여러 변경」](../../external/trip-chat-context.md).

## 결론

- 기준: role-manager `c34bd376fce473ac8b42bb101974f7f374e4e10b`. 로컬 격리 후보(staged, push 안 함). x600 배포 · 로컬 서빙 반영 없음.
- 빠른 관문(tests/architecture · contract · unit · security, `not live and not db and not slow`): 9562건 중 실패 0 · 오류 0 · 건너뜀 173 (9389 통과). 새 시험 19/19.
- 실 E4B(tripilot-pointer:e4b-ft) 4회: 여러 변경 2문장 중 **1/2 = 50%** 분리 성공, 단일 회귀 1/1 = 100%, 기준 비교 1회.
  - 「점심 식당은 다른 데로 바꾸고 박물관은 한 시간 미뤄줘」 → 맨 위 `apply_change`/광장시장(식사 → dining) + 추가 `change_time`/국립중앙박물관 60분(활동 → activity). 모델은 −60 을 냈지만 서버가 원문(「미뤄」 · 「한 시간」)으로 +60 을 셌다.
  - 「북촌 빼고 덕수궁 추가해줘」 → **해석 실패**. 모델이 맨 위를 `apply_change`/북촌 + `time_edit.boundary=start`(인용 없음)로 내 인용 확인에서 떨어졌다(추가 항목 `add_item`/덕수궁은 맞게 냈다). 같은 문장을 기준 트리로 부르면 `replace_named` 북촌→덕수궁(한 변경으로 바꾸기)이었다 — 이 문장은 **후보가 기준보다 나쁘다**. 인용 검사는 약화하지 않았다. 다음 할 일: 학습 데이터 · 프롬프트 보강 후 새 holdout 으로 재측정.
  - 단일 「점심 식당은 다른 데로 바꿔줘」 → `apply_change`/광장시장, `additional_changes=[]` (지어낸 추가 변경 없음).
- 로컬 live 카운터(`integ-v9-20261026-025943/runtime-v9-serving/policy-counters.json`) 전후 동일.

## 설계

- 해석 스키마에 `additional_changes`(최대 2) — 항목: `text`(원문 인용) · `action`(바꾸는 할 일 8종 `MULTI_ACTIONS`) · `target_item` · `destination_text` · `condition_text` · `minutes` · 앞뒤 칸. 맨 위 칸은 그대로(첫 변경).
- `decision_unit._decide_all`: 인용을 위치로 확인(`_additional_quotes` — 그대로 있음 · 겹치지 않음 · 맨 위 원문이 남음), 항목마다 「해당 없음」 칸을 채운 해석을 그 원문으로 `_interpret`(전 `decide` 뒷부분 그대로)에 통과. 맨 위 변경은 추가 원문을 뺀 나머지 문장으로 확인. 맨 위와 같은 할 일 · 같은 일정이면 버림. 낱말 규칙 없음.
- `trip_messages._run_additional_changes`: 맨 위 처리 뒤 문장 순서로 추가 변경마다 Case(`request_id#N`, 기록 `multi_change`)를 열고 `_run_decision` 으로 처리(담당 배정 · 보호 · 판 확인 그대로, 변경마다 새 판). 되묻기 · 실패 · 값 모자람은 실행하지 않고 Case 도 열지 않음. 같은 일정 겹침은 이어서 바꾸지 않음. 답은 「1) … / N) 「원문」 — …」로 묶고 응답 `multi_change` 에 변경별 원문 · Case · 상태.

## 기본안(되돌릴 수 있음)

- 일부 되묻기: 확정된 것은 처리하고 남은 것만 알린다. 맨 위의 되묻기만 대기 질문이 되고, 추가 변경의 되묻기는 「따로 다시 말씀해 주세요」로 알린다(한 메시지에 대기 질문 여럿을 만들지 않음).
- 판: 변경마다 새 판(묶지 않음 — 팀 실행 · 되돌리기가 판 단위).

## 한계

- 같은 `request_id` 재전송은 맨 위 Case 답만 돌려준다.
- 실 E4B 측정은 2문장뿐이다(1/2). 이 두 문장은 프롬프트 예시에 넣지 않았다(예시는 다른 문장 — holdout 유지).
- DB 시험 · 웹 e2e 미실행(오케스트레이션은 `_open_message_case` · `_run_decision` 대역 시험).
