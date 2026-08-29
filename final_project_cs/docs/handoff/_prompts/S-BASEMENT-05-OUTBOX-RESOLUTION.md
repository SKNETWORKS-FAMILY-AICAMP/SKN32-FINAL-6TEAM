# S-BASEMENT-05-OUTBOX-RESOLUTION — unknown 메시지 사람 해결 워크플로 전체 이식 (migration 005)

## 0. 배경 — 이 프로젝트 핵심 안전원칙의 실행 경로가 통째로 없다

`CLAUDE.md` §0.2: "provider timeout 을 성공으로 추정하지 않는다.
`unknown` 으로 남기고 자동 재실행하지 않는다." — 이 원칙 자체는 지켜지고
있지만(`worker.py` 가 timeout 시 `unknown` 으로 남김), **그 다음 —
사람이 실제로 그 unknown 을 어떻게 결론짓는가 — 의 실행 경로가 cs 에
아예 없다.**

`final_project_sample/acop_basement/` (참고용, **절대 수정 금지**) 대조로
확인된 것:
- `infrastructure/db/migrations/003_outbox_resolution.sql` — `outbox`
  테이블에 `resolved_at`/`resolved_by`/`resolution_note`/`resolution`
  컬럼 추가. **cs 에 없음.**
- `presentation/api/outbox.py` — `POST /v1/outbox/{id}/resolve` REST
  라우트. **cs 에 없음.**
- `presentation/ui/routes.py` 의 `/ops/outbox` 화면(목록 + 해결 폼) —
  **sample 엔 있고 cs 는 삭제된 채 대체가 없다**(cs 의 새
  `/ui/admin` 은 읽기 전용이라 "여기서는 아무것도 바꾸지 않는다"는
  안내가 코드 주석에 있다).
- `infrastructure/messaging/worker.py` 의 stale lock 회수(worker 가
  claim 만 하고 죽으면 그 행이 영원히 `processing` 에 갇히는 걸 막는
  로직) — **cs 에 없음.**

★오늘 세션에서 이미 `docs/manuals/운영_unknown상태_대응절차.md`(2026-08-20
작성)에 "전용 조회 화면·API 가 없다"고 정직하게 적어둔 바로 그 갭이다 —
이번 작업이 그 갭을 실제로 메운다. **작업 완료 후 그 문서도 갱신해라**
(§4 참고).

## 1. 할 일

1. `app/infrastructure/db/migrations/005_outbox_resolution.sql` 신규 —
   sample 의 마이그레이션을 참고해서 cs 의 `outbox` 테이블 스키마에
   컬럼을 추가해라(정확한 기존 컬럼명은 cs 의 `001_schema.sql` 을 봐라).
2. `app/presentation/api/outbox.py` 신규 — `POST /v1/outbox/{id}/resolve`
   구현. sample 을 참고하되 cs 의 인증/scope 패턴(다른 REST 라우트들이
   `require_scope()` 를 쓰는 방식)을 따라라. 이 엔드포인트는 **사람이
   확인한 결과를 기록하는 것**이지 outbox 를 자동으로 재처리하는 게
   아니다 — `docs/manuals/운영_unknown상태_대응절차.md` §4 가 이미 설명한
   수동 확인 절차와 일치해야 한다.
3. `app/presentation/api/app.py` 에 새 라우터 등록.
4. `app/presentation/ui/routes.py` 에 `/ops/outbox` 화면(목록 + 해결
   폼)을 복원해라. sample 참고하되, cs 의 기존 UI 디자인시스템(테마·
   상태색 등, `app/presentation/ui/theme.py`)과 일관되게 만들어라 —
   sample 그대로 복사하지 마라, cs 스타일에 맞춰라. 네비게이션에도
   추가해라.
5. `app/infrastructure/messaging/worker.py` 에 stale-lock 회수 로직을
   추가해라 — sample 의 `_reclaim_stale_processing()` 류를 참고해서,
   일정 시간 이상 `processing` 상태로 멈춰있는 행을 `unknown` 으로
   되돌려라(자동 재실행이 아니라 "사람이 볼 수 있는 상태로 되돌리는
   것"이다 — `unknown` 은 여전히 자동 재실행 안 되는 상태다).

## 2. 검증

- `POST /v1/outbox/{id}/resolve` 통합테스트: 인증 없으면 거부, scope
  없으면 거부, 정상 호출 시 `resolved_at`/`resolved_by`/`resolution`
  이 실제로 기록되는지, **`outbox.status` 자체나 `case` 상태를 이
  엔드포인트가 직접 바꾸지 않는지**(기록만 하는 것과 실제 재처리하는
  건 다르다 — 운영절차서 §4 원칙과 일치해야 한다) 확인해라.
- stale-lock 회수 재현 테스트: 일부러 `processing` 상태로 오래
  멈춰있는 행을 만들고, worker 사이클 이후 `unknown` 으로 바뀌는지
  확인해라.
- `/ops/outbox` UI 화면을 실제로 렌더링하는 e2e 테스트를 추가해라
  (기존 `tests/e2e/` 패턴을 따라라).
- `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라(359 passed
  기준 변화 명시).

## 3. 쓰기 대상

- `app/infrastructure/db/migrations/005_outbox_resolution.sql` (신규)
- `app/presentation/api/outbox.py` (신규)
- `app/presentation/api/app.py`
- `app/presentation/ui/routes.py`
- `app/infrastructure/messaging/worker.py`
- 관련 테스트 파일들
- `docs/manuals/운영_unknown상태_대응절차.md` (§4 근처에 "이제
  `/ops/outbox` 화면·API 가 실제로 있다"고 갱신 — 없다고 적힌 문장을
  고쳐라, 다른 내용은 건드리지 마라)
- `docs/reports/2026-08-24_S-BASEMENT-05-OUTBOX-RESOLUTION_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- 마이그레이션 번호 005 는 이 작업 전용이다 — 003, 004(다른 작업)와
  안 겹친다, 그대로 005 를 써라
- 이 엔드포인트가 outbox 를 자동으로 재발행/재처리하게 만들지 마라 —
  기록만 한다(자동 재실행 금지 원칙)
