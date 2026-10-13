# 오라클 ARM 서버 develop 자동 배포 — 덧씌움 충돌로 멈춤 · 축소해 재개 (Claude, 2026-10-13)

오라클 ARM 서버의 develop 자동 배포가 10-13 develop `ea4eba89`(팀원 PR #49)부터 매 5분 실패했다. 고장이 아니라 10-12 에 넣은 서버 전용 덧씌움의 안전 검사(「develop 원본이 바뀌면 옛 수정본으로 덮지 않는다」)가 멈춘 것이다. Codex 와 실무 기준으로 2회차에 합의해 덧씌움을 줄이고 재개했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 원인 확인 | 끝 | 1/1 |
| Codex 합의(실무 기준) | 2회차 합의 | 1/1 |
| 같은 실패 반복 막기(배포 스크립트) | 실서버 확인 | 1/1 |
| 덧씌움 축소(코드 11 → 2 · 지식 문서 10 유지) | 미리 적용 · 실서버 반영 | 1/1 |
| 새 develop 반영 | `ea4eba89` 기동 · healthy | 1/1 |
| develop 으로 올릴 수정 3가지 | 사용자 · commit 세션 몫 | 0/1 |

## 원인

- 오라클 서버는 빌드 전 `control/prepare_search_release.py` 가 `control/search-overlay.json`(10-12 서버 수정: 코드 11파일 + 지식 문서 10개, 파일 통째)을 덧씌운다. develop 쪽 원본 해시가 10-12 와 다르면 `RuntimeError: source changed; review overlay` 로 멈춘다.
- `ea4eba89` 에서 덧씌움 대상 9파일의 develop 원본이 바뀌었다. 덧씌움 수정 6가지 중 3가지는 develop 이 이미 자체 방식으로 고쳤다(아래 표). 옛 수정본으로 덮으면 develop 의 새 수정(예: 식사 요청에 관광지가 걸리면 그 안·근처 식당을 찾는 10-13 방식)을 지운다.
- 실패 SHA 를 기록하지 않는 위치(try 밖)에서 예외가 나 5분마다 같은 실패가 반복됐다.

| 10-12 덧씌움 수정 | develop `ea4eba89` | role-manager | 처리 |
|---|---|---|---|
| 식사 요청에 관광지 확정 차단 | 있음(다른 방식) | 있음 | 덧씌움에서 뺌 |
| 질문 분류(장소 선택 기준 = 규정 질문) | 있음 | 있음 | 뺌 |
| 일정 목록 · 변경 가능 조회 | 있음(같은 이름 파일 자체 작성) | 있음 | 뺌 |
| 정확한 이름 우선 정렬(`candidates.py` 3줄) | **없음** | 있음 | 유지(깨끗이 합쳐짐) |
| 지식 문서 current-travel 적재(`itinerary_team.py` 3줄 + 문서) | **없음** | 있음 | 유지(깨끗이 합쳐짐) |
| 하루 요약 날짜 전달(summary_day, API · 웹 6파일) | **없음** | 있음 | 뺌(5파일 충돌) — develop 에 올 때까지 오라클 서버에서 빠짐 |

## 한 일

1. 배포 스크립트: 덧씌움 충돌이면 그 SHA 를 `state.json` 의 `overlay_blocked_sha` 로 남기고 다음 회차부터 받기 · 빌드를 건너뛴다(새 develop SHA 가 오면 다시 시도). 저장소 판에 서버에만 있던 두 줄(`knowledge` 경로 · 덧씌움 호출)도 맞췄다 — [deploy.py](../../../deploy/arm/deploy.py), 시험 [test_deploy.py](../../../deploy/arm/test_deploy.py) `test_overlay_conflict_blocks_sha_once_and_keeps_app` 추가 → Linux(오라클 서버 /tmp)에서 3/3 통과. 실서버에서 12:37 에 차단 기록 확인.
2. 덧씌움 축소: 정렬 · 지식 문서 적재 2파일만 새 develop 기준 3-way 병합(손으로 푼 충돌 0곳, develop 과 같은 CRLF)으로 다시 만들고 기대 해시를 갱신했다. 새 릴리스 사본에 미리 적용해 검사 통과 · 정렬 수정 · 문서 6개 · develop 식사 처리 유지를 확인한 뒤 반영.
3. 차단 기록을 풀고 배포 → 12:48 `ea4eba89` 반영(api · web healthy, `/health` 200, 웹 200, 이전 판 `6866c596` 은 previous 로 보존). 컨테이너 안에서 정렬 수정 · develop 식사 처리 · 문서 적재 확인, 최근 5분 로그 오류 없음. 디스크 17GB 남음.

## 백업

- 오라클 서버 `control/_backup/2026-10-13_2150_deploy_before_overlay_block/deploy.py`
- 오라클 서버 `control/_backup/2026-10-13_2200_overlay_shrink/`(옛 `search-overlay.json` · `state.json`)
- 저장소 [deploy/arm/_backup/2026-10-13_2140_deploy_before_overlay_block/](../../../deploy/arm/_backup/2026-10-13_2140_deploy_before_overlay_block/)(고치기 전 로컬판 · 서버판 · 시험)

## 남은 일

- **develop 으로 올릴 3가지**(정확한 이름 정렬 · 지식 문서 적재 · 하루 요약 날짜 전달) — 모두 role-manager 에 있다. develop 반영은 사용자 요청 + commit 세션 몫. 반영되면 오라클 서버 덧씌움의 코드 항목을 지우고 develop 을 그대로 배포한다.
- 남은 덧씌움 2파일은 develop 이 그 파일을 또 바꾸면 다시 멈춘다(이번엔 한 번만 실패로 남고 반복하지 않는다).
- 실제 질의(채팅 · 검색) 확인은 오라클 서버의 상시 HTTP 검사 대기열이 다음 회차에 돈다 — 이 기록 시점에는 결과를 보지 않았다.

## 합의 기록

Codex main 계정(gpt-6-sol) 2회. 1회차: 둘 다 「멈춰 두고 develop 반영 뒤 덧씌움 제거」. 2회차: 새 사실(3가지는 develop 에 이미 있음, 2가지는 충돌 없음)로 「덧씌움 축소 후 재개」에 합의. Codex 반박 수용 — 「충돌 0곳 ≠ 위험 0」이라 미리 적용 · 빌드 · 동작 확인을 조건으로 뒀다. alt 계정은 로그인 만료로 불참. 기계 검토이며 사람이 본 것이 아니다.

## 확인 범위

mock 서버 시험(화면 반응): 해당 없음.
실서버 확인(서버 응답): 했음 — 오라클 서버에서 배포 · 건강 검사 · `/health` 200 · 웹 200 · 컨테이너 안 코드 확인. 고객 채팅 · 검색 응답은 확인 안 함.
