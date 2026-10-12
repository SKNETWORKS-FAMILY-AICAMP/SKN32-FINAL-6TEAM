# 운영자 콘솔 목업

## 직접 체험하는 단일 HTML

**[admin-scenario.html](admin-scenario.html)** — 2026-09-29. 이 파일 하나를 전달해 브라우저로 연다. 앱과 같은 React 소스로 생성한 동작 시연이며 인터넷·별도 서버·설치가 필요 없다. 문의 → 예외 한도 → 답변 → 공지 → 발송 확인 → 운영 기록을 「시연 가이드」로 따라갈 수 있다. 검색·필터·설정·모달도 동작한다.

모든 데이터와 변경 결과는 가상 데이터이며 메모리에만 유지된다. 실제 인증·API·저장은 없다. 새로고침 또는 「데모 초기화」로 처음 상태로 돌아간다. 소스 변경 후 앱 폴더에서 `npm run export:html`로 다시 만든다. 자세한 [실행·시연 안내](../README.md)를 참고한다.

백엔드 구현을 검토할 때는 [운영 앱 API 협의](../../../../wiki/external/admin-screen-api.md)를 함께 읽는다. 이 HTML의 데이터·정책은 데모 예시이며, 다음 단계는 화면 요구와 기존 API를 대조한 계약 합의다.

## 화면 구성 참고용 정적 와이어프레임

운영자 콘솔 화면 구성을 팀이 검토하고, 구현할 때 참고하는 정적 HTML이다. 실행 앱이 아니며 데이터·API와 연결되지 않는다.

화면별 목적·표시·행동과 개발 계획은 [SCREEN_PLAN.md](../SCREEN_PLAN.md)가 정본이다. 이 목업과 기획서가 다르면 기획서를 따르고 차이를 알린다.

## 현재 기준안

**[wireframe-v1.2](wireframe-v1.2/index.html)** — 2026-09-29. 브라우저로 `index.html`을 열고 왼쪽 메뉴·링크로 화면 사이를 이동한다.

| 화면 ID | 파일 | 화면 |
|---|---|---|
| S-01 | [s01-login.html](wireframe-v1.2/s01-login.html) | 로그인 |
| S-02 | [s02-home.html](wireframe-v1.2/s02-home.html) | 홈 · 오늘 처리할 일 |
| S-03 | [s03-users.html](wireframe-v1.2/s03-users.html) | 사용자 목록 |
| S-04 | [s04-user-detail.html](wireframe-v1.2/s04-user-detail.html) | 사용자 상세 |
| S-05 | [s05-limits.html](wireframe-v1.2/s05-limits.html) | 한도 · 감시 조절 |
| S-06 | [s06-usage.html](wireframe-v1.2/s06-usage.html) | 사용량 |
| S-07 | [s07-server.html](wireframe-v1.2/s07-server.html) | 서버 상태 |
| S-08 | [s08-inquiries.html](wireframe-v1.2/s08-inquiries.html) | 문의함 |
| S-09 | [s09-notices.html](wireframe-v1.2/s09-notices.html) | 공지 · 점검 |
| S-10 | [s10-audit.html](wireframe-v1.2/s10-audit.html) | 운영 기록 |
| S-11 | [s11-ops.html](wireframe-v1.2/s11-ops.html) | 예약 승인 · 위임 · 발송 확인 (임시) |

## 보는 법과 한계

- 값은 모두 자리표시다. `N` = 숫자 자리, `[ ]` = 아직 정하지 않은 값이나 문구. 표의 API 이름·경로·상한 규칙처럼 실제 코드에서 옮긴 것은 기획서 §4·§7에 근거가 있다.
- 정적 사본이라 버튼·탭·입력은 동작하지 않는다. 탭과 기간 선택은 첫 항목이 고른 상태로 고정돼 있다.
- 화면 폭은 1440px 고정이다(PC 기준). 좁은 창에서는 가로로 스크롤된다.
- 글꼴은 Google Fonts(IBM Plex Sans KR · IBM Plex Mono)를 불러온다. 오프라인이면 기본 글꼴로 보인다.
- 「팀과 정할 것」은 기획서 §9에 모았다.

## 구현할 때

- 이 HTML을 앱 코드로 복사하지 않는다. 배치·구성·문구를 참고하고, 앱은 기획서 §5의 구조(CSS Modules · 공통 부품 · 데이터 경계)로 새로 쓴다.
- 색·간격은 이 목업의 값을 디자인 토큰의 출발점으로 쓸 수 있다: 바탕 `#F4F3EF` · 패널 `#FFFFFF` · 선 `#D9D6CE` · 글자 `#1F1E1B`/`#5B5953` · 강조 `#1F4E8C` · 경고 `#A64B0A`.

## 판 관리

- 편집 원본은 팀 공유 디자인 캔버스다. 이 폴더의 `wireframe-v*`는 캔버스를 판마다 정적 HTML로 내보낸 사본이다.
- 캔버스를 고치면 새 폴더(`wireframe-v1.3` 등)로 다시 내보내고 위 「현재 기준안」과 표를 바꾼다. 이전 판은 지우지 않는다.

| 판 | 날짜 | 바뀐 것 |
|---|---|---|
| v1.2 | 2026-09-29 | Codex 1차 검토 반영: 모든 화면에 데모 표시 · 로그인 「데모로 들어가기 — 인증하지 않음」 · 운영 상한과 공급자 무료 제공량 구분 · API별 계측 상태 · 차단과 키 폐기 구분 · 발송 결과 미확인은 전달 확인/미전달 확인 · 상태만 바꾸는 문의와 점검 전환에 사유 칸 |
| v1.1 | 2026-09-29 | [wireframe-v1.1](wireframe-v1.1/index.html) 보존. 외부 API는 서비스 전체로만 집계 · 사용자별 한도는 ② 채팅 · ③ 웹 · 감시 조절은 API별 외부 API 예산 기준 |
| v1 | 2026-09-29 | 첫 판(보존하지 않음 — 같은 날 v1.1로 고침) |
