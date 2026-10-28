---
type: report
title: 라우팅 전수검사 7건 · TeamFlow ST4F-574 · 714 · A13 role-manager 통합
status: draft
domain: travel
---

# 라우팅 전수검사 7건 · TeamFlow ST4F-574 · 714 · A13 — role-manager 통합 (2026-10-29, S2)

## 결론
- 기준: 팀 · 개인 role-manager 둘 다 `c52fb5c69`(R 릴리스 PR #107 · EKS main `20c296e77` 완료 뒤, 23:13 · 00:3x ls-remote 두 번).
- 올린 것(`c52fb5c69` 위 5커밋, 빨리 감기):
  1. `7fb47617a` 전수검사 미결 7건(E-D3 · A17 · A15 · C18 · C20 · C21 · C22) — 앞 작업자 후보, 이번에 diff 를 다시 읽고 검토했다(아래).
  2. `87081891e` 그 보고서.
  3. `d6c3a67c7` TeamFlow 후보 `010f9deeb` cherry-pick(ST4F-574 장소 갱신이 공통 공공데이터 키 · ST4F-714 project.yaml 팀 블록 중복 칸). 충돌 0.
  4. `5d7054edb` ST4F-574 후속: `getattr(settings, "public_data_key", None)` + `callable` 대체를 없애고 `Settings.public_data_key()` 를 바로 부른다. 시험 대역 때문에 넣은 숨은 대체였다 — 대역에 같은 메서드를 넣었다.
  5. `cb284d301` 전수검사 A13 수정(아래).
- ST4F-710(`e6e754f27`)은 이미 role-manager 에 `e6e02f4c7` 로 들어가 있어 따로 넣지 않았다.
- 전수검사 미결: 29 → **28**(A13 고침). 7건 · A13 은 x600 배포 확인 전까지 「고침(배포 미확인)」.

## A13 — 해 없는 날짜에 모델이 붙인 해
- 결함(재현 RED): 읽기 에이전트가 「10월 30일」을 `2027-10-30` 으로 돌려주면 인용에 숫자가 있다는 이유로 `date_guessed=False` → 규칙 쪽 `resolve_dates` 가 `written` 으로 받아 **확인 표시 없이** 확인 화면에 갔다. 규칙 읽기의 같은 날짜(`--10-30`)는 `year_filled` 로 확인 표시가 붙는다.
- 수정: 모델이 고른 해(`2027`)가 날짜 인용에 그대로 적혀 있지 않으면(`2027` 독립 숫자 · `27년` 둘 다 없음) 값은 두고 `needs_review=True`, `how=agent_year`, 안내 「해가 적혀 있지 않아 읽기 에이전트가 2027년으로 두었어요 — 다르면 고쳐 주세요」.
  - 값을 바꾸지 않는 이유: 해가 머리줄 등 인용 밖에 있을 수 있고, 값을 규칙 해로 바꾸면 「전부 과거」 가드 판정이 달라진다. 이번 범위는 표시만.
- Codex read-only 검토 1차 blocker: 처음 정규식 `\d{4}` 가 「1230 출발」 · 예약번호 · 다른 해(「1027년」)를 해로 봤다 → 「모델이 고른 해가 인용에 있나」로 바꾸고 그 4가지를 회귀 시험에 넣었다.
- 시험: `tests/unit/travel/test_intake_agent_yearless_date.py` 9건(확인 표시 4 · 해 적힌 인용 5), RED 1 → GREEN 9/9.

## 앞 작업자 7건 독립 검토 메모
- E-D3: 카카오 서울 밖 조회는 서울에서 못 찾고 · 후보 없음 · 막힘 아님일 때만 한 번. 상태는 `unresolved` 그대로(범위 안 넓힘). 응답에 `_outside_area` 안 싣는 것 확인(`public`).
- A17: 확인 화면 전환 UPDATE 0행이면 `_Abandoned` — 같은 트랜잭션에 다른 쓰기 없음(롤백 영향 0).
- A15: 실패 확정 시 모든 판의 비고객 claim 삭제 — 고객 수정 보존.
- C18: `or 60.0` 제거, 설정(`config/guardrails.yaml` `reliability.outbox_retry_seconds: 60`) 없으면 ValueError — 숨은 기본값 제거 방향, 설정 존재 확인.
- C20 · C21 · C22: 500자 자르기 · 경고 기록만. 문제 없음.

## 검증
| 관문 | 결과 |
|---|---|
| 빠른 관문(격리 5 shard, `cb284d301`) | 10,766 통과 · 실패 2 · 건너뜀 173 — 실패 2는 `test_human_review_adapters`(sparse 로 뺀 program/ HTML, 기준과 같음) |
| 격리 PG 55573 DB 묶음(`5d7054edb`, 59파일) | 2회: 555/555 · 554/555 — 실패 1 `test_intake_test_plans[29]` 은 실행이 KST 자정을 넘어 「여행 첫날」 기대 날짜가 하루 밀린 것(앞 회차 통과) |
| 격리 PG 접수 DB 8파일(`cb284d301`, A13 뒤) | 110/110 통과 |
| ruff · `git diff --check` | 통과 |

- 시험 환경 주의: 이 터미널 셸의 환경 변수가 다른 작업자와 섞였다(`TMPDIR` 이 다른 작업자 scratch, DB 스크립트의 `ACOP_*` 가 남음) → tiktoken 캐시 못 찾아 6건 · CORS 1건 거짓 실패. `TIKTOKEN_CACHE_DIR` 명시 · `ACOP_*` 해제 후 통과. 관문 스크립트를 쓰는 작업자는 실행 전 환경을 직접 정할 것.

## 운영 상태
- x600: SSH `192.168.0.8:22` 연결 시간 초과, 공개 `tripilot.devroro.click/health` 523 → **role-manager push 의 x600 자동 배포는 확인 불가(대기)**. x600 이 돌아오면 board `deploy:<sha>` phase done · deploy.log 「반영 완료」 · /health 확인 뒤 7건 · A13 을 「고침」 확정.
- EKS `guguroute.devroro.click/health` 200(main 경로, role-manager push 영향 없음).

## 남은 미결 28 — 다음 순서
- 재현 시험으로 닫을 것: A09(뒤 묶음 정정) · B10 · B11.
- 결정 대기: A05 시한 · A06 화면 · C15 고착 회수 · C14 응답 계약 · 웹 5 늦춤 · C17 fail-open(사용자) · E-D6 DB 쓰기(사용자 승인).
