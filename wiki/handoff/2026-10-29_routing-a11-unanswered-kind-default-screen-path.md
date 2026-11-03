---
type: handoff
title: A11 — 체크아웃 줄 종류 질문의 미답 기본값(1안) 계약 맞춤 · 실제 확인 화면 길 실측
status: draft
domain: travel
---

# 결론

기록 2026-10-29 KST, Hermes(Claude) 서브에이전트. 앞 인계는 [A11 P2 독립 검증](2026-10-29_routing-a11-checkout-choice-independent-verify.md)입니다. 같은 후보 트리 `C:/_proj/routingresume1029`(HEAD `d1b06357e`)를 이어 썼고 커밋하지 않았습니다. 새 clone · pip 설치 · push · 배포 · 운영 DB 쓰기는 모두 0건입니다. 삭제한 것도 없습니다. 보호 XML 보안 HOLD는 그대로입니다(앞 manifest 118/118 = 100% 해시 같음).

계약 정본은 `web-intakes.md` 「호텔 줄 — 종류 확인 질문」입니다. 1안은 읽은 종류이고, **답하기 전에는 1안으로 계산하되 등록은 막습니다.** 또 1안을 고르면 판을 만들지 않습니다(`interpretations.answer`). 그래서 그 판에 저장된 검사(`review`)는 다시 계산되지 않습니다. 둘을 합치면 답하기 전 계산이 1안과 같아야 합니다. 그래야 화면과 등록 판단이 갈라지지 않습니다.

**실측한 결함(실제 PostgreSQL + 실제 HTTP 앱):** 종류 질문이 붙은 짝 없는 체크아웃 줄이 있었습니다(「11:00 서울신라호텔 체크아웃 후 라운지 브런치」, 1안 「숙박」).

- 답하기 전부터 A11 규칙이 이 줄을 활동으로 계산했습니다.
- 1안 「숙박」을 고르면 판 1은 그대로입니다. 화면(`review`)도 활동 · 「들르는 일정으로 두었어요」(filled) 그대로였습니다.
- 반면 `check`는 `stay_without_check_in`을 냈고 등록은 422 `intake_incomplete`였습니다. 화면에는 막힌 이유가 보이지 않았습니다.
- 증거: `probe_before_fix.json`.

# 고친 것(후보 트리, CRLF 유지, `git diff --check` 통과)

1. `intake/interpretations.py`: `question_kinds()`를 새로 두었습니다. 답한 질문은 `(답의 종류, True)`, 아직 답하지 않은 질문은 `(1안의 종류, False)`를 냅니다. `answered_kinds`는 이 함수를 감싸도록 바꿨고 `__all__`도 갱신했습니다.
2. `intake/assemble.py`:
   - `collect`가 각 줄에 `kind_answer` / `kind_first`(미답 1안)를 답니다.
   - `_stays.picked`는 `kind_first == "lodging"`인 줄도 덮지 않습니다. 그 줄은 숙박 그대로 · 끝 없음 · `stay_without_check_in`이 되고, `kind_unanswered`와 함께 등록을 막습니다.
   - 문구는 이렇게 나눴습니다. 확인 화면에서 직접 숙박으로 고친 줄(`customer`)만 「숙박으로 고르셨지만」입니다. 질문 길(답 전 · 1안 답 뒤가 같은 판 · 같은 저장 검사)은 「숙박으로 두면 짝이 되는 체크인 일정이 없어 … 들르는 일정(활동)으로 바꿔 주세요」입니다.
   - 1안이 활동 · 식사면 계산도 그 종류입니다.
3. `frontend/apps/web/src/features/plan-check/model.ts`:
   - `checkOrder`와 `withAskSlot`은 질문이 가리키는 일정(`ask.itemId`)이 판에 있으면 그 일정 **앞**에서 묻습니다. 판에 없으면 전처럼 시각 순서입니다.
   - 실제 브라우저에서 확인한 문제 때문입니다. 1안 계산으로 그 일정에 빨간 줄이 생기면, 같은 시각의 질문 자리보다 일정이 먼저 「이 일정을 먼저 고쳐 주세요」로 멈췄습니다. 그래서 종류 질문 카드가 나오지 않았습니다.
4. 계약: `final_project_cs/wiki/external/rest-endpoints/web-intakes.md` 「숙박」 절에 `[2026-10-29 A11 미답 기본값]`을 추가했습니다.
5. 시험:
   - `tests/unit/travel/test_intake_stay_checkout_answer_path.py` +3건(미답 = 1안 숙박, 1안 답 전후 같은 줄 · 시간 줄, 1안 활동이면 활동).
   - 새 e2e `tests/e2e/test_intake_stay_checkout_kind_screen_path.py` 3건(실제 앱 · DB: 미답 화면 숙박, 1안 답 같은 판 · 같은 화면 · 등록 422, 활동 답 새 판 · 막음 해제).
   - `model.test.ts` +1건.

새 상수 · 임계값 · 시각 값 · 숙박 기간은 하나도 만들지 않았습니다. 규칙 대체도 추가하지 않았습니다.

# 실행 결과

실행 환경: 전용 loopback PG16.15 `:63941`, DB `a11_kindpath`(`a11_candidate_ready` 복제). 비loopback 연결은 막았습니다. 모델 · 관광공사 · 카카오는 대역이고, 3.12 격리 실행기를 썼습니다.

| 실행 | 결과 |
|---|---|
| e2e RED(수정 전) | 1/3 통과. 실패 2건은 결함과 같습니다(화면 활동) |
| unit RED(수정 전 모듈) | 8/10 통과. 새 2건 실패 |
| e2e · unit GREEN | 3/3 · 10/10 = 100% |
| 숙박 · 접수 · 예약 · 항공 · 아키텍처 회귀(앞 실DB 목록과 같은 규칙) | **1526/1526 = 100%**, live 245건은 원래 설정대로 선택 제외 |
| 접수 e2e 5파일(새 파일 · 해석 질문 · 숙소 후보 등) | 24/24 = 100% |
| 계약 | 367/367 = 100% |
| 보안 | 124/125 = 99.2%. 실패 1건은 기존 HOLD XML(`st4f728-guest-logout/security-ready.xml`)로 기준과 같습니다 |
| DoD | 26/26 = 100%(MVP 18/18) |
| 웹 vitest 전체 · 새 시험 RED | 137파일 **1229/1229 = 100%** · 수정 전 model.ts로는 새 1건 실패 |
| `tsc --noEmit` · `find_leaks`(바꾼 파일 7개) | 0 · 0 |

첫 회귀 실행에서는 13건이 실패했습니다(`test_travel_approval_proposal_reaches_waiting.py`). 실행기가 `TIKTOKEN_CACHE_DIR`를 빈 폴더로 가리킨 하네스 오류였고, 기존 `%LOCALAPPDATA%/Temp/data-gym-cache`로 고친 뒤 전체 목록을 다시 1회 돌렸습니다. 그 결과가 위의 1526입니다. 첫 실행 로그 `gate_regression/`도 보존했습니다.

# 실제 브라우저 화면(Edge headless, loopback 웹 :3200 + loopback 서버 :8142, 외부 요청 차단)

- 서버는 실제 FastAPI 앱 + 실 DB입니다. 읽기 모델 · 장소 조회만 e2e와 같은 대역입니다(`serve.py`).
- 웹은 후보 트리 `next dev --webpack`이고 `NEXT_PUBLIC_DATA_MODE=live`입니다.
- 게스트 필수 동의만 체크했고 선택 동의는 거절했습니다.

화면 흐름:

1. 계획을 보내고 읽기를 지켜봅니다(`07-ask`). 3일차 서울신라호텔 앞에서 「「서울신라호텔」을 어떤 일정으로 볼까요?」가 나오고, 1안은 「숙박(추천)」입니다.
2. 「숙박」을 고릅니다(`08-answered`). `POST …/interpretations`는 200이고 판은 1 그대로입니다. 카드는 숙박 아이콘이고 시간 줄은 「고쳐야 함」입니다. 문구는 「숙박으로 두면 … 「서울신라호텔 체크인」 일정을 넣거나 들르는 일정(활동)으로 바꿔 주세요」이고, 「직접 수정 / 삭제」가 보입니다.
3. 새 접수에서 「활동」을 고르면 판 2가 됩니다(`activity/08-answered`). 「모두 확인했어요 · 5초 뒤에 여행을 등록해요」가 뜹니다.

model.ts를 고치기 전에는 같은 흐름에서 질문 카드가 없었습니다. 서버 수정만 들어간 상태에서 「이 일정을 먼저 고쳐 주세요」에서 멈췄습니다(`ask visible false`). 이것이 위 3번 수정의 근거입니다. 그 회차 스크린샷은 뒤 회차가 같은 이름으로 덮어써 보존되지 않았습니다. 같은 순서 결함은 웹 RED(`front_red.log`)로 재현됩니다.

# 남은 것(분류)

| # | 문제 | 분류 |
|---|---|---|
| 1 | 보호 XML 보안 HOLD | 정식 처리 전 통합 · push 금지(변함없음) |
| 2 | 이번 변경(서버 2 · 웹 1)의 독립 검토 | 필요 |
| 3 | 종류 질문 「숙박」 선택지 effect 문구(「체크인 시각 · 체크아웃 날은 … 규칙으로 채우고」)가 짝 없는 체크아웃 줄에는 맞지 않음(기간을 채우지 않음) | 문구 결정 — 고치지 않음 |
| 4 | 끝난 검사를 다시 연 화면은 해석 · 종류 질문을 묻지 않음(P6 결정 「검사가 멈추는 곳에서만」). 이때 `kind_unanswered`의 이유가 화면에 직접 보이지 않음. 이 줄은 빨간 줄 + 「직접 수정」으로 풀 길이 있지만, 일반 종류 질문 줄에서 막힘 이유가 보이는지는 확인하지 않음 | 기존 UI 설계 · 사용자 결정 거리, 확인 필요 |
| 5 | 질문이 없는 「…체크아웃」만 적힌 줄은 확인 화면에서 숙박으로 고를 UI가 없음 · 「일정 추가」 폼에 숙박 종류 없음 | 프런트 설계 결정(앞 인계와 같음) |
| 6 | 좌표 차이 167 m인 같은 호텔(독립 검토 P2) | 같은 장소 판정 기준이 필요한 별도 요구. 임계값을 지어내지 않음 |
| 7 | 장소 줄 문구가 「「서울신라호텔」은 확인이 필요해요 — 「서울신라호텔」 — …」로 이름이 겹침(`.kind` 문제가 장소 줄 · 시간 줄 두 곳에 보임) | 표시 다듬기(기존 P2부터) |
| 8 | 실제 모델 · 운영 서버 · 실제 장소 조회 · 지도 타일 | 확인 안 함(대역 · 차단) |

# 증거 · 자원(`C:/_proj/routinga11kindpath1029_evidence`, 약 2.3 MB)

- `before/` · `after/`(수정 전후 사본), `apply_fix.py`(정확히 1회 치환), `this-session.patch`.
- `run.py`(실DB 실행기), `gates.py`, `dod_run.py`.
- 실행별 폴더: `red_e2e*/`, `red_unit/`, `green_*/`, `gate_*/`(pytest.xml · log · exit_code), `gate_dod/`.
- `probe_screen_vs_check.py`, `probe_before_fix.json`, `probe_after_fix.json`.
- `front_red.log` · `front_green.log` · `front_all.log` · `tsc.log`, `xml-preservation-check.json`.
- 브라우저: `serve.py` · `serve_run.py` · `screen.cjs` · `shots/`(png + 본문 txt) · `serve.log` · `next-dev*.log`.

이 세션이 만든 것 중 지우지 않은 것:

- DB `a11_kindpath`(PG `C:/_proj/routinga11verify1029/pgdata` 안, 정지 상태).
- 후보 웹 `frontend/apps/web/.next`(186 MB, gitignore 대상 `next dev` 캐시).
- 기존 `node_modules` 연결점은 그대로 썼습니다. 연결점을 지울 때는 `rmdir`로 연결점만 지웁니다(대상 재귀 삭제 금지).
- 서버 · 웹 · PG는 모두 정지했습니다.
