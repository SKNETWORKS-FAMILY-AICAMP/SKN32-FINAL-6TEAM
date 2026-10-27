# 2026-10-27 TeamFlow(팀플로) 버그 수집 · 코드 대조 · 개선 후보 — J 세션

작성 2026-10-27 14:50 KST · 기준 role-manager `064208bdd`(14:27 ls-remote, 지시문의 922d628d 뒤로 이미 움직임) · 작업 트리 `cache/scratch/teamflow-J-20261027/rm`(브랜치 `fix/teamflow-J-20261027`, 원본 작업트리 미변경) · push 없음.

## 결론

- **「팀플로」 = TeamFlow**(https://jira-for-me.vercel.app, 프로젝트 id 84 · 키 `ST4F`) — 루트 `AGENTS.md`·`CLAUDE.md` 「TeamFlow (이슈 트래커)」 절로 확정. 토큰으로 `GET /api/issues` 읽기만 했다(쓰기 0, 토큰 미출력).
- TeamFlow 전체 이슈 **688건** 수집(유형별 필터 합 = 272 task + 265 story + 129 bug + 22 epic; 한 번에 500건 상한이라 필터로 나눠 받음). 대상 = 미해결(완료 아님) 117건 ∪ 최근 30일(09-27~) 버그 110건 = **189건**(중복 제목 0건).
- 보조 채널: SKN 저장소 GitHub 이슈 0건 · 열린 PR 0건. CI 최근 40회 중 실패 4회는 모두 role-manager 수동 실행(10-26 00:33~04:04, 계획 읽기 e2e 숙소 질문·결정 문맥 창)이고 뒤 실행(04:19)과 develop·main 은 통과 — 이미 고쳐진 것으로 분류.
- 결함(버그 유형 + 직접 재현한 작업 1건) 111건 중 해결 93/111 = 83.8%(TeamFlow 완료 또는 검토 대기 — 그중 설명의 근거 커밋이 role-manager 064208bdd 조상인 것 86/93 = 92.5%, 나머지는 TeamFlow 표시만이고 코드 재대조 안 함), 미해결 18/111 = 16.2%(그중 직접 재현 4건), 오탐 0건 확인(0%) — **오탐 판정은 재현을 시도한 4건 안에서만** 했고 나머지 미해결 14건은 코드로 대조하지 않았다.
- 후보 커밋 3개(아래). LB-04 · 체크아웃 줄 두 번째 숙박(잠재)은 A(접수) 영역이라 `_coord/A-intake-audit-NOTICE.md` 로 넘겼다.

## 후보 커밋 (`fix/teamflow-J-20261027`, 기준 064208bdd)

| SHA | 항목 | 내용 | 시험 |
|---|---|---|---|
| `669a384c2` | ST4F-709 숙소 팀 몫 | team/role-booking-transit `206f151fa` 체리픽(숙소 후보에 `price_limit`) — 시험 파일 충돌은 LB-05 시험만 가져옴 | 그 시험 포함 |
| `e889d9889` | ST4F-709 코어 몫 | 고를 때 재확인 1박 값 > 상한이면 웹 `409 over_price_limit` · 채팅 `lodging_over_limit`(일정 그대로). 판정은 `recheck.over_price_limit` 한 곳. 계약 `trips.md` 한 줄 | 새 5건(RED 2 → GREEN), 게이트 3건 등록 |
| `760de217c` | ST4F-685 | 「…중지될 수 있음」의 「수」 → 수요일 휴무 오판. 요일 한 글자 뒤 「있·없」 제외(`place_hours.NOT_A_DAY_AFTER`, `closure_rules._BARE_DAY` 공용) | 새 8건(RED 4 → GREEN) |

## 실행한 검증 (Python 3.12 격리 실행기 `date_risk_pytest_runner.py`, 소켓·DB 차단, 합성 설정)

| 묶음 | 결과 | 비고 |
|---|---|---|
| `tests/unit/travel/booking` 전체층(`-m "booking_full or not booking_full"`) | 후보 320/321 통과 · 기준 314/315 | 실패 1건 `test_the_trip_center_of_the_stay_dates_gives_distances_and_orders_google` 은 **기준 064208bdd 에서도 같은 실패**(게이트 밖, 별건) |
| 활동 · 영업시간(`tests/unit/travel/activity` + place_hours · seoul_hour_readers · intake_holiday_conditions · notice_place_closure) | 803/803 | 685 수정 뒤 |
| `tests/architecture` · `contract` · `security`(`-m "not live and not db"`) | 633/633 (29 deselected = db) | 처음 실행 3건 WinError 5 는 WindowsApps git 경로 탓 — 휴대용 git 을 PATH 앞에 두고 통과 |
| ruff F·E9 (바뀐 파일) | 통과 | |
| `tests/unit/travel` 한 프로세스(`-m "not live and not db and not slow"`) | **중간 중단** — 322파일 중 앞 53%까지 3,224 통과 · 0 실패 · 80 skip | `test_disaster_msg_api.py` 에서 7건 뒤 8분 넘게 멈춰 끊음 — ST4F-547(한 프로세스 전체 실행 멈춤) 재현으로 기록, 나머지 47% 미실행 |
| DB · e2e · 웹 화면 · 실서버 | **미실행** | x600·아마존 변경 금지 시간대, DB 없음. 웹은 409 를 서버 문장(해요체)으로 그대로 보이는 기존 `refusalSentence` 경로 — 화면 확인 안 함 |

## 분류 요약

| 구분 | 건수 |
|---|---|
| 요청·작업(결함 아님) | 78/189 = 41.3% |
| 해결(TeamFlow 완료) | 72/189 = 38.1% |
| 해결(검토 대기·커밋 포함) | 21/189 = 11.1% |
| 미해결(TeamFlow 열림·코드 미대조) | 14/189 = 7.4% |
| 미해결·재현 | 4/189 = 2.1% |

| 담당 영역 | 건수 |
|---|---|
| 배포 | 64 |
| 접수 | 36 |
| 웹 | 31 |
| 데이터 | 27 |
| 채팅 | 14 |
| 기타(문서·결정) | 11 |
| 컨트롤러 | 6 |

| 우선순위 | 건수 | 기준 |
|---|---|---|
| P0 | 0 | 자료 손실·보안·전면 중단(확인된 미해결 0) |
| P1 | 80 | TeamFlow high, 또는 고객 조건 위반·거짓 휴무처럼 고객에게 틀린 결과(709·710·685 올림) |
| P2 | 104 | TeamFlow medium |
| P3 | 5 | TeamFlow low · 정리 작업 |

영역 분류는 제목 낱말 규칙(배포→접수→채팅→웹→데이터→컨트롤러 순)이라 거칠다 — 직접 본 7건만 손으로 고쳤다.

## 미해결 결함 (우선 처리 대상)

| 키 | P | 영역 | TeamFlow | 제목 | 대조 결과 · 다음 |
|---|---|---|---|---|---|
| ST4F-504 | P1 | 배포 | todo | 같은 답장을 동시에 두 번 보내도 한 번만 처리되는 시험이 develop 에서 또 실패함(3번째 불안정) | 미해결(TeamFlow 열림·코드 미대조); CI 흔들림 — 로컬 재현 안 함 |
| ST4F-521 | P3 | 배포 | todo | 로컬 모델 닫힌 포트에서 유료 대체로 빨리 넘어가는지 재는 시험이 전체 시험 부하 중 3.2초로 실패함(불안정) | 미해결(TeamFlow 열림·코드 미대조); 부하 의존 시간 시험 — 재현 안 함 |
| ST4F-547 | P2 | 배포 | todo | 파이썬 단위 시험 전체를 한 프로세스로 돌리면 멈추거나 강제 종료되는 현상(원인 미확인) | 미해결(TeamFlow 열림·코드 미대조); 이번에도 tests/unit 을 묶음으로 나눠 돌림 |
| ST4F-554 | P1 | 배포 | todo | x600 서버 채팅 응답 4건 중 3건이 15초를 넘음(9.2·17.9·26.1·29.6초) | 미해결(TeamFlow 열림·코드 미대조); x600 지연 — Hspeed 세션 측정 중 |
| ST4F-555 | P1 | 배포 | todo | develop 서버(Oracle ARM)에서 질문·대안·변경 3단계가 해석 모델 오류로 실패(4/4) | 미해결(TeamFlow 열림·코드 미대조); 오라클 서버 — 금지 시간대 |
| ST4F-556 | P1 | 배포 | todo | develop 서버에서 3곳 계획의 셋째 장소를 못 찾아 등록이 422 로 막힘 | 미해결(TeamFlow 열림·코드 미대조); develop 서버 — 금지 시간대 |
| ST4F-589 | P1 | 배포 | todo | x600 서버의 관광공사 검색 호출 예산이 소진(budget_exhausted)돼 이름 조회가 모두 실패함: 예산 설정 점검 | 미해결(TeamFlow 열림·코드 미대조); x600 예산 설정 — 금지 시간대 |
| ST4F-597 | P2 | 데이터 | todo | 요식 대체 후보의 「비슷한 곳」 축이 원장에 메뉴 원문이 없어 비어 나옴 | 미해결(TeamFlow 열림·코드 미대조); 요식 원장 자료 — E |
| ST4F-631 | P2 | 접수 | todo | 테스트 계획 20번의 메모 「도착일이라 가볍게」가 여행 제목이 됨(계획 읽기) | 미해결(TeamFlow 열림·코드 미대조); 계획 읽기 — A |
| ST4F-653 | P2 | 웹 | todo | 웹 「로그인 상태가 끝났을 때(session_expired) 여행 화면에 로그인 단추가 주 단추로 뜬다」 화면 시험이 실패함(이름 변경 전 판에서도 같은 기존 결 | 미해결(TeamFlow 열림·코드 미대조); 웹 화면 시험 — D |
| ST4F-678 | P2 | 데이터 | todo | 창덕궁 휴무 경고가 다른 원인으로 남아 있음(후속 조사) | 미해결(TeamFlow 열림·코드 미대조); 활동 휴무 — 원인 조사 필요 |
| ST4F-685 | P1 | 데이터 | todo | 공공데이터 안내 문구 「…가동 중지될 수 있음」의 「수」를 수요일로 읽어 휴무로 판정함(미수정) | 미해결·재현 — closed_on_weekday(「가동 중지될 수 있음」, 수요일)=True 재현(064208bdd) → 후보 커밋으로 수정; 후보 760de217c |
| ST4F-692 | P2 | 배포 | todo | 요식 판정 시험 test_dining_agent_judge 가 고객 메모 2,000자 자르기에서 실패함(develop 에 원래 있던 것) | 미해결(TeamFlow 열림·코드 미대조); 통합(DB) 시험 — 미실행 |
| ST4F-694 | P1 | 웹 | todo | 웹 mock 서버 화면 시험 870개 중 바탕 판에서도 실패하는 35건 고치기(「mock-35」 세션이 고치는 중) | 미해결(TeamFlow 열림·코드 미대조); 웹 mock 35 — D(mock-35 세션) |
| ST4F-709 | P1 | 컨트롤러 | todo | [버그] 숙소를 고를 때 다시 확인한 가격이 1박 상한을 넘어도 그대로 적용됨 (LB-05) | 미해결·재현 — 코어 몫 미구현: 상한 초과 재확인 값을 그대로 적용(시험 RED 2건 재현) → 후보 커밋으로 수정; 후보 e889d9889 · 669a384c2 |
| ST4F-710 | P1 | 접수 | todo | [버그] 같은 날 체크아웃 시각이 비면 체크아웃이 체크인보다 빨라짐 (LB-04) | 미해결·재현 — _stays 직접 호출: 15:00 체크인 → 같은 날 11:00 체크아웃(064208bdd) — A(접수) 영역이라 _coord 전달; A 에 전달(_coord) |
| ST4F-711 | P2 | 웹 | todo | [버그] 서버가 잠깐 끊기면 접수 화면이 「보내고 있어요」에서 멈춤 (LB-09) | 미해결(TeamFlow 열림·코드 미대조); 웹 접수 화면 — D |
| ST4F-714 | P3 | 컨트롤러 | todo | [작업] project.yaml 요식 팀 블록 중복 정리 (LB-16) | 미해결·재현 — config/project.yaml 요식 블록 required·capabilities 두 번(코드 확인); P3 — 손대지 않음(YAML 뒤 값이 이긴다, 두 블록 값은 같음) |

## 시연 계열 잠재 결함 사전 탐지 (호텔 · 읽기 화면 · 후보 고르기)

| # | 계열 | 발견 | 재현 | 처리 |
|---|---|---|---|---|
| 1 | 후보 고르기(호텔) | 상한 조건을 넘는 재확인 가격이 적용됨(ST4F-709) | 시험 RED | 후보 커밋 |
| 2 | 읽기 화면(휴무 경고) | 「수 있음」의 「수」 → 수요일 휴무(ST4F-685). 같은 규칙이 `days_in` 공용이라 식당 · 장소 영업시간 읽기에도 같은 오판 | 스크립트 · 시험 RED | 후보 커밋 |
| 3 | 호텔(접수) | 같은 날 시각 없는 체크아웃 → 끝이 시작보다 앞(ST4F-710) | `lb04_repro.py` | A 전달 |
| 4 | 호텔(접수) | 체크아웃 줄을 읽기 AI 가 `lodging` 으로 내면 두 번째 숙박이 됨 → 등록 422(어제 hotel-activity-QA A 증상과 같음) | `qa_a_repro.py` | A 전달 |
| 5 | 읽기 화면(휴무) | `_FESTIVE` 의 「설」이 「시설」에도 맞아 「시설 점검일 휴관」 같은 문구가 명절 판정을 거쳐 「모름」이 됨(틀린 휴무는 아님) | 스크립트 | 기록만(P2, 활동 담당) |
| 6 | 숙소 시험 | 숙박 기간 가운데 거리 시험이 기준 판에서도 실패(3 ≠ 2) — 날짜 의존 가능성 | 기준·후보 같은 실패 | 기록만(숙소 팀) |

## 남은 일

- 부모: 14:30 이후 role-manager fast-forward 통합 여부 판단(직전 ls-remote · `_coord` 조율). 669a384c2 는 role-booking-transit 의 미병합 커밋이라, 그 브랜치를 나중에 합치면 같은 변경이 겹친다(내용 같음 — 충돌 시 그쪽 것으로).
- DB e2e(`tests/e2e/test_chat_lodging_web.py`)에 상한 초과 고르기 사례 추가 · 웹 `error-text.ts` 에 `over_price_limit` 문장(D) · x600 실화면 확인.
- TeamFlow 이슈 상태 갱신(709 · 685 → 검토)은 하지 않았다(쓰기 금지). 미해결 14건 코드 대조.
- 수집 원본: `cache/scratch/teamflow_J/ALL.json`(688건, 저장소 밖) · 전체 표: [같은 이름 .csv](2026-10-27_teamflow_버그수집_J.csv)

## 실행 명령

```bash
# TeamFlow 읽기 (토큰은 .env.teamflow, 출력 안 함)
curl -s "$TEAMFLOW_BASE_URL/api/issues?projectId=84&limit=500&type=<task|story|bug|epic>" -H "Authorization: Bearer $TEAMFLOW_API_TOKEN"
# 시험
DATE_RISK_ROOT=<트리> python -B date_risk_pytest_runner.py -p no:cacheprovider -m "booking_full or not booking_full" tests/unit/travel/booking/
DATE_RISK_ROOT=<트리> python -B date_risk_pytest_runner.py -p no:cacheprovider -m "not live and not db" tests/architecture tests/contract tests/security
```
