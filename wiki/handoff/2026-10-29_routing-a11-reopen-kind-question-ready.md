---
type: handoff
title: A11 — 미답 기본값 수정 독립 검토 · 다시 연 화면의 종류 질문 누락 · 1안 답 뒤 등록 막힘 수정
status: draft
domain: travel
---

# 결론

기록 2026-10-29 KST, Hermes(Claude) 서브에이전트. 앞 인계는 [A11 미답 기본값 · 실제 화면 길](2026-10-29_routing-a11-unanswered-kind-default-screen-path.md)입니다. 같은 후보 트리 `C:/_proj/routingresume1029`(HEAD `d1b06357e`)를 이어 썼고 커밋하지 않았습니다. 새 clone · pip 설치 · push · 배포 · 운영 DB 쓰기는 0건이고, 지운 것도 없습니다. 보호 XML 보안 HOLD는 그대로입니다(추적 XML 336/336 해시 같음).

**앞 수정(서버 2 · 웹 1) 독립 검토:** 막는 결함은 없습니다.

- `question_kinds` · `kind_first`는 짝 없는 체크아웃 숙박 줄의 `picked`에만 영향을 줍니다. 그 줄은 종류가 `lodging`이고 체크아웃 말만 있는 줄입니다.
- 1안이 활동 · 식사이면 계산이 바뀌지 않습니다.
- `checkOrder` · `withAskSlot`의 「그 일정 앞」은 일정이 판에 있는 질문(종류 질문)에만 해당합니다. P6 줄 질문은 일정이 판 밖이라 전과 같습니다.

**인접 경로에서 실제 결함 2건을 재현하고 고쳤습니다.** 재현 환경은 실 PostgreSQL + 실제 FastAPI 앱 + Edge 화면입니다.

1. **다시 연 결과 화면에서 종류 질문이 빠짐.**
   - P6 결정 ①에 따라 끝난 검사를 다시 연 화면은 해석 질문으로 멈추지 않습니다(`useReveal`이 `asks`를 버림).
   - 그런데 종류 질문은 답하기 전 `kind_unanswered`로 등록을 막습니다.
   - 그 결과 화면은 「확인을 마쳤어요. 모두 확인했어요.」였고 ✓ 는 「서버가 아직 등록할 수 없다고 해요 · 위의 확인할 것을 먼저 고쳐 주세요」로 막혔습니다. 답할 곳은 없었습니다.
   - 증거: `shots/plain-10-reopen-day3.txt` · `plain-12-server.json`.
2. **종류 질문 1안 답 뒤에도 등록이 막힘.**
   - 1안 답은 판을 만들지 않습니다. 그래서 저장된 `review.ready`가 답 전 계산(false) 그대로 남았습니다.
   - `check.ready`는 true이고 문제는 0이며 `confirm`도 받습니다. 그런데 화면은 `review.ready`를 읽으므로 ✓ 가 계속 막혔습니다.
   - 처음 지켜본 화면에서 1안을 골라도 같습니다. 빨간 줄이 없는 일반 호텔 종류 질문에서 생깁니다.
   - 증거: `shots/plain-23-after-server.json`(review_ready false · check_ready true), e2e RED.

# 고친 것(후보 트리, CRLF 유지, 유효 설정 `git diff --check` 통과)

- 서버 `intake/pipeline.py` `view`(+6줄): 다음 조건을 모두 만족하면 `review.ready`를 참으로 **올리기만** 합니다.
  - 같은 판
  - 검사 끝(`checked`가 false가 아님)
  - `needs.total == 0`
  - 일정 있음
  - `check.ready`(등록 판정 `confirm`과 같은 지금 조립)
  - 확인 필요 · 미룬 검사 · 원문 누락 · 식당 조건이 내린 판정은 건드리지 않습니다.
- 웹:
  - `from-review.ts` `asksOf`: 서버 문제 `kind_unanswered`(같은 원본 · `items[n].kind`)가 가리키는 질문에 `held: true`를 답니다.
  - `model.ts`: `PlanAsk.held`와 `heldAsks`를 추가했습니다.
  - `plan-check.tsx`:
    - 결과 화면 `cardQuestion`은 held 질문을 그 일정 카드 안에서 먼저 묻습니다. 서버 문구와 선택지를 그대로 쓰고, 답은 `cardSend`로 보냅니다. 「직접 선택」은 그 일정의 바꾸기 화면을 엽니다.
    - 화면을 멈추지는 않습니다(결정 ① 유지).
    - 요약은 「일정 종류 n곳 확인 필요」를 셉니다.
  - `result-parts.tsx` `Registration.waiting` + `intake-review.tsx`: ✓ 가 막힌 이유를 서버 `check.problems` 문구로 보입니다.
- 계약: `final_project_cs/wiki/external/rest-endpoints/web-intakes.md` 「숙박」 절에 `[2026-10-29 A11 재열기]`를 추가했습니다.
- 시험:
  - 새 e2e `tests/e2e/test_intake_kind_first_answer_ready.py` 3건(미답 막음, 1안 답 → `review.ready` · 다시 조회 · 등록 200, 대조: 짝 없는 체크아웃 1안 숙박은 올리지 않음).
  - 웹 `from-review.test.ts` +2건, `model.test.ts` +2건.
- 새 상수 · 임계값 · 고객 글 단어 맞추기는 0건입니다. 추가한 리터럴은 서버 계약 코드 `kind_unanswered`와 화면 표시 문구뿐입니다.

# 실행 결과(전용 loopback PG16.15 `:63941`, DB `a11_reopen` · `a11_reopen2` = `a11_candidate_ready` 복제, 3.12 격리 실행기, 모델 · 관광공사 · 카카오는 대역)

| 실행 | 결과 |
|---|---|
| e2e RED(서버 수정 전) | 2/3, 실패 1건이 결함 2와 같음 |
| 웹 RED | 66/69, 새 3건 실패 |
| e2e GREEN(새 파일 + 앞 종류 화면 e2e) | 6/6 |
| 회귀(앞 인계와 같은 규칙) | **1526/1526 = 100%**(live 245건은 원래 설정대로 제외) |
| 추가(식당 · 모두 지난 날짜 · `tests/unit/intake`) | 749/751, 건너뜀 2건은 git 밖 미쉐린 자료 없음 |
| 접수 e2e 전체(`test_intake_*` + trip_intake_api · reopen · planner) | **433/433 = 100%** |
| 계약 | 367/367(2회) |
| 보안 | 124/125(2회), 실패 1건은 기존 HOLD XML `st4f728-guest-logout/security-ready.xml` |
| DoD | 26/26 = 100%(MVP 18/18) |
| 웹 vitest 전체 · tsc · eslint(바꾼 7파일) | 137파일 **1233/1233** · 0 · 0 |
| `find_leaks` + 이메일 · 전화 · 키 패턴(바꾼 · 새 11파일) | 0 |

# 실제 브라우저(Edge headless, 웹 :3200 `next dev --webpack` live + 서버 :8142 실 앱, 외부 요청 차단)

- 일반 호텔 줄(「14:00 서울신라호텔」, 1안 활동)을 접수했습니다. 질문은 답하지 않고 페이지를 다시 열었습니다.
  - 수정 전: 질문 0, 「모두 확인했어요」, ✓ 막힘.
  - 수정 후: 3일차 카드에 「읽은 뜻 · 「서울신라호텔」을 어떤 일정으로 볼까요?」(활동 추천 · 숙박 · 식사 · 직접 선택)가 나오고, 요약은 「일정 종류 1곳 확인 필요」입니다. ✓ 를 누르면 「「서울신라호텔」을 숙박 · 활동 · 식사 중 어떤 일정으로 볼지 골라 주세요」가 나옵니다.
  - 「활동」을 고르면 `POST …/interpretations` 200, 판 1 그대로 `review.ready` true입니다. ✓ 를 누르면 등록되어 `confirmed`가 됩니다(DB 확인).
- 짝 없는 체크아웃 줄(1안 숙박)을 다시 열었습니다.
  - 카드에 종류 질문이 빨간 시간 줄보다 먼저 나오고, 요약은 「장소 1곳 · 일정 종류 1곳 확인 필요」입니다.
  - 「활동」을 고르면 판 2가 되고 `review.ready` true입니다.
- 두 번째 일반 접수의 등록은 403이었습니다. 게스트 여행 1개 한도로, 제품 규칙대로입니다.

# 남은 것

| # | 문제 | 분류 |
|---|---|---|
| 1 | 보호 XML 보안 HOLD | 정식 처리 전 통합 · push 금지 |
| 2 | 이번 변경(서버 1 · 웹 5)의 독립 검토 | 필요 |
| 3 | 짝 없는 체크아웃 줄의 종류 질문 「숙박」 effect 문구(「체크인 시각 · 체크아웃 날은 … 규칙으로 채우고」)가 실제와 다름(기간을 채우지 않고 막음). 다시 연 화면에서 이제 보이므로 더 눈에 띔 | 문구 결정. 바꾸려면 질문 view가 조립 결과(짝 여부)를 알아야 함 |
| 4 | 실시간 진행 `done` 이벤트의 `ready`는 저장값 그대로(조회만 올림) | 답 뒤에는 화면이 조회하므로 영향 없음. 확인만 |
| 5 | 수정 모드(등록한 여행 고치기)의 종류 질문 막힘 | 이번 범위 밖(`resultAsks`는 `!edit`), 확인 안 함 |
| 6 | 질문 없는 「…체크아웃」 줄 숙박 UI 없음 · 좌표 167 m 같은 호텔 · 장소 줄 이름 겹침 | 앞 인계와 같음(설계 · 별도 요구) |
| 7 | 실제 모델 · 운영 서버 · 지도 타일 | 확인 안 함 |

# 증거 · 자원(`C:/_proj/routinga11reopen1029_evidence`, 약 5.5 MB)

- `before/`(수정 전 사본 + sha256), `apply_fix.py` · `apply_server_fix.py` · `apply_contract.py` · `add_tests.py`(정확히 1회 치환), `this-session.patch`(234줄).
- `run.py` · `gates.py` · `dod_run.py` · `regression-files.json`.
- 실행별 폴더: `red_e2e/` · `green_e2e/` · `gate_regression/` · `gate_extra/` · `gate_e2e/` · `gate_contract(_A)/` · `gate_security(_A)/` · `gate_dod/`.
- 웹 로그: `front_red.log` · `front_green.log` · `front_all.log` · `tsc.log` · `eslint.log`. 검사 결과: `leak_scan.json` · `xml-preservation-check.json`.
- 브라우저: `serve.py`(시나리오 `A11R_SCENARIO`) · `serve_run.py` · `screen.cjs` · `look.cjs` · `probe_reg.cjs` · `register.cjs` · `shots/`(png + 본문 txt + server json) · `serve*.log` · `next-dev.log`.

이 세션이 만들고 지우지 않은 것:

- DB `a11_reopen` · `a11_reopen2`(PG `C:/_proj/routinga11verify1029/pgdata` 안, pgdata 163 → 194 MB, 정지).
- 후보 트리의 untracked `frontend/apps/web/a11-reopen.vitest.config.mts`. 시험 캐시는 증거 폴더에 둡니다.
- 새 e2e 파일.
- 후보 웹 `.next`(195 MB, 앞 세션 것을 이어 씀).
- `node_modules` 연결점은 그대로 썼습니다. 지울 때는 `rmdir`로 연결점만 지웁니다(재귀 삭제 금지).
- 서버 · 웹 · PG는 모두 정지했습니다. C: 여유 약 119 GB로 목표 400 GB 아래입니다(이 세션 증가 약 37 MB).
