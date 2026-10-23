# 사실 확인 F — v15 그림·문서의 바뀐 문장이 코드와 맞나 (읽기만, 짧게, 적대적으로)

저장소: C:\Users\playdata2\Documents\final_workspace\final_project_cs (현재 작업 트리 기준. 커밋 82aff095 · 06c3cb16 포함)
아래 표의 파일:줄 근처만 읽어라(필요하면 그 함수 전체까지). 다른 탐색 금지.

| # | 그림·문서 문장 | 근거로 든 곳 |
|---|---|---|
| 1 | 활동 담당은 대체 후보를 위에서 6곳까지만 다시 확인한다 | app/modules/travel_ops/itinerary_changes.py:731 · activity/team.py:115-125 |
| 2 | 도구 한도(허용 밖 · 예산 12번 · 같은 질문 반복)에 걸린 후보는 「못 봤다」로 빼고 고르지 않는다 — 실행이 예외로 실패하지 않는다. 앞 후보가 통과했으면 그 안으로 변경안을 낸다 | app/modules/travel_ops/itinerary_team.py:243-260 · itinerary_changes.py 의 plan_activity_adjustment / choose |
| 3 | 감시 회차 안에서 한 건(Case)이 예외로 터져도 그 건만 오류(escalated · team_error)로 닫고 다른 일정은 계속 점검한다 | app/modules/travel_ops/trip_watch_cases.py:130-170 |
| 4 | 외부 조회 실패 · 실행 오류로 닫힌 건은 5분 뒤 다시 열어 최대 3번 다시 본다. 고객에게는 알리지 않는다 | trip_watch_cases.py:54-55, 240-266 · config/guardrails.yaml:270-280 |
| 5 | 「최대 3번」이 맞나 — 첫 시도 포함 3번인지, 재시도 3번(총 4번)인지 | trip_watch_cases.py:255-266 (total 계산) |
| 6 | 대안을 못 찾으면(itinerary_unresolved) 일정은 그대로 두고 고객에게 원인을 알린다 · 같은 사건에 한 번 | trip_watch_cases.py:176-188 · pending.py:166 unresolved_notice |
| 7 | 변경안 확인(처리 총괄의 사실 대조)에서 떨어지면 고객에게 알리지 않는다 · 다시 열지도 않는다 | app/application/controller.py:381-400 · trip_watch_cases.py:55, 181 |
| 8 | 답 없는 선택 요청은 그 일정이 끝나면 닫힌다(기본 감시가 만료 처리를 부른다) · 고르기 요청 때도 끝난 · 낡은 요청은 닫는다 | trip_watch_cases.py:90-100 · pending.py:279-336 |
| 9 | 고른 안의 확인이 실패해도 요청은 열린 채 남는다(의도 — 다른 안을 고를 수 있게) | pending.py:300-340 · app/modules/travel_ops/trip_api.py 의 choose 호출부 |
| 10 | 번역 숫자 검사가 개수까지 맞춘다 — 빠진 숫자 · 새로 생긴 숫자 모두 실패 | app/infrastructure/notify/translate.py:40-50 |
| 11 | 고객이 고정한 일정은 지금 점검에서 아예 빠진다 | trip_watch_cases.py:100-106 |
| 12 | 자동 점검은 지금 1분마다 돈다 | scripts/ops/jobs.py:71-80 |

결과는 표 하나: `# | 맞음 / 틀림 / 일부 | 근거 파일:줄 | 틀렸으면 고칠 문장`.
그다음, 표에 없는데 v15 그림에서 이 수정들 때문에 **틀려진** 다른 문장이 있으면 3개 이내로(그림 글: C:\Users\playdata2\Documents\final_workspace\program\산출물양식\w5\아키텍처_한눈에\v15\src\fig_uc.py 의 fig_uc2 만).
마지막 줄: 「사실 맞음」 또는 「고칠 것: …」.
