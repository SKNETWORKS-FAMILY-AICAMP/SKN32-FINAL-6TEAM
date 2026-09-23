# S-UNKNOWN-OPS-SCREEN — `unknown` outbox 를 사람이 푸는 화면 + 런북

## 배경 (읽지 않아도 되는 맥락)

`wiki/records/release_checklist.md` §2 가 체크되지 않은 채 남아 있다:
> ★`unknown` 을 사람이 푸는 운영 절차(화면·런북)가 없다 — 자동 재실행을 막아 뒀으니
> 누군가 손으로 조회해 결론내야 하는데 그 경로가 비어 있다

`app/infrastructure/messaging/worker.py` 의 `OutboxWorker.process_once()` 가
publisher 호출에서 `TimeoutError`/`ConnectionError` 를 만나면 `outbox.status` 를
`'unknown'` 으로 남기고 **재시도하지 않는다** (`CLAUDE.md` §0.2 —
"provider timeout 을 성공으로 추정하지 않는다"). 지금은 이 상태가 된 행을
**아무도 볼 수도, 처리할 수도 없다.** DB 를 직접 열어야만 보인다.

★**이건 안전 관련 기능이다.** `unknown` 은 "돈이 나갔는지 모르는 상태"다
(`app/presentation/ui/theme.py` 주석 참조 — 가장 센 위험색을 쓴다). 그래서
**자동 재시도는 여기서도 만들지 않는다** — 사람이 실제 하류 시스템을 확인하고
결론을 **타이핑으로 남긴 뒤**에만 상태가 바뀐다.

## 반드시 읽을 파일

1. `app/infrastructure/messaging/worker.py` — `unknown` 이 되는 유일한 경로
2. `app/infrastructure/db/migrations/001_schema.sql`, `002_domain_customer_ops.sql`
   — `outbox` 테이블 정의와 마이그레이션 파일 명명 규칙(멱등, `IF NOT EXISTS`)
3. `app/presentation/api/cases.py` — `approve()` 엔드포인트 하나만. REST 쓰기
   엔드포인트가 `require_scope(...)` 를 어떻게 쓰는지의 스타일 참고용
4. `app/presentation/ui/routes.py` — `approvals()` GET + `approve()` POST 두
   함수만. 화면이 REST 를 내부 호출하는 패턴(`httpx.ASGITransport`)을 그대로 따른다
5. `app/presentation/security.py` — `require_scope`, `_development_key`
6. `config/guardrails.yaml` 의 `security.scopes` 섹션만

## 만들 것

### 1. 마이그레이션 `app/infrastructure/db/migrations/003_outbox_resolution.sql`
`outbox` 테이블에 컬럼 추가 (전부 nullable, 기존 행 영향 없음, `IF NOT EXISTS` 로
재실행 안전):
- `resolved_at timestamptz`
- `resolved_by text`
- `resolution_note text` — **사람이 무엇을 확인했는지 적는 자리. 필수 입력으로 강제한다**
- `resolution` text — 예: `'confirmed_delivered'` 또는 `'confirmed_not_delivered'`

### 2. REST 쓰기 엔드포인트 `POST /v1/outbox/{message_id}/resolve`
`app/presentation/api/cases.py` 의 `approve()` 와 같은 스타일로 추가한다
(다른 파일이어도 되면 `app/presentation/api/outbox.py` 신설도 괜찮다 — 다만
`app.py` 에 라우터 등록을 잊지 않는다).

- scope: **`action:approve` 재사용** — 새 scope 를 만들지 않는다. 불확실한
  side-effect 를 사람이 결론짓는 것은 승인과 같은 급의 책임이다
- 요청 바디: `{"resolution": "confirmed_delivered" | "confirmed_not_delivered" | "requeue", "note": "...", "resolved_by": "..."}`
- `note` 가 비어 있으면 **422로 거부한다** — 근거 없는 처리(RULE.md §3.2 폴백 금지와
  같은 정신: "일단 넘긴다"를 만들지 않는다)
- `resolution="confirmed_delivered"` 또는 `"confirmed_not_delivered"`:
  `status` 를 `'resolved'` 로 바꾸고 `resolved_at`/`resolved_by`/`resolution_note`/
  `resolution` 을 채운다. **재발행하지 않는다**
- `resolution="requeue"`: 사람이 "확인해보니 전달 안 됐다, 다시 보내도 안전하다"고
  판단한 경우다. `status` 를 `'pending'` 으로, `available_at=now()` 로 되돌려서
  `OutboxWorker` 가 다시 집게 한다. `attempts` 는 건드리지 않는다(이미 있는 재시도
  횟수 로직과 별개로 사람이 승인한 재시도이므로). `resolved_*` 컬럼도 함께 채운다 —
  "누가 왜 재시도시켰는지"는 재시도 케이스에도 남아야 한다
- 대상 행이 `status != 'unknown'` 이면 409 로 거부한다 — 이미 처리됐거나 애초에
  unknown 이 아닌 행을 건드리지 못하게 막는다
- **`tenant_id` 격리를 지킨다** — principal 의 tenant 밖 행은 404 (RULE.md 의
  다른 화면들과 같은 관례, 403 아니다)

### 3. 화면 `GET /ops/outbox`
`app/presentation/ui/routes.py` 의 `approvals()` 를 본떠서 만든다:
- `status='unknown'` 인 outbox 행을 tenant 격리해서 나열 (`topic`, `payload_json`
  요약, `attempts`, `last_error`, `available_at`, 경과 시간)
- 각 행에 폼 3개(또는 select+하나의 폼): "배달 확인됨"/"배달 안 됨(재시도)"/
  "배달 안 됨(포기)" — 전부 **note 입력 필수**(브라우저 `required` + 서버도 다시 검사)
- 없으면 "unknown 상태 메시지가 없습니다" 빈 상태 표시 (기존 `theme.empty_state` 패턴)
- 상단 nav 에 이 화면 링크를 추가한다 (`theme.py` 의 nav 정의를 찾아서)

### 4. 런북 `wiki/records/manuals/2026-08-17_unknown_처리_런북.md`
사람이 `/ops/outbox` 를 열었을 때 실제로 뭘 확인해야 하는지 절차:
- 이 시스템엔 실제 결제 provider 어댑터가 없다(`wiki/records/release_checklist.md` §5-3)
  — 그러니 런북은 "무엇을 확인해야 하는지"의 **일반 절차**를 적는다: 해당
  `topic`/`payload` 가 가리키는 하류 시스템(예: 실제 배포에서는 결제 게이트웨이
  대시보드, 이메일 발송 로그 등)에서 **직접** 전달 여부를 확인하고 오는 것이
  먼저다. 이 화면 자체는 그 확인을 대신 해주지 않는다 — 결론을 **기록**하는 곳이다
- 각 resolution 선택지가 실제로 뭘 하는지(재발행 여부) 명시
- ★"잘 모르겠으면 아무 것도 누르지 말고 에스컬레이션하라"를 명시한다

## 하지 않을 것

- **자동 재시도를 만들지 않는다.** 사람이 명시적으로 `requeue` 를 선택할 때만 재발행
- `action_requests`/`ActionProposal` 쪽은 건드리지 않는다 — 이건 outbox(message broker)
  전용이다 (이 시스템에 진짜 provider 실행 경로가 없다는 사실은 안 바뀐다)
- `config/guardrails.yaml` 에 새 scope 를 추가하지 않는다 — `action:approve` 재사용
- 기존 `approvals`/`cases` 화면 로직을 리팩터링하지 않는다 — 새 화면만 추가

## 완료 기준

```powershell
python -m pytest -q   # 전체 스위트 그대로 초록 (2026-08-17 기준 326 passed 이상)
```

새 테스트를 반드시 추가한다 (`tests/integration/` 아래, 기존 outbox 테스트
파일들과 같은 스타일):
1. `status='unknown'` 행이 화면에 나타나는지
2. `note` 없이 resolve 를 호출하면 422 인지
3. `confirmed_delivered`/`confirmed_not_delivered` 후 `status='resolved'` 이고
   **재발행되지 않는지** (worker 가 다시 집지 않는지)
4. `requeue` 후 `status='pending'` 이고 worker 가 다시 집는지
5. 남의 tenant 의 unknown 행은 404 인지
6. 이미 `resolved` 인 행을 다시 resolve 하려 하면 409 인지

리포트에 재현 명령과 실제 출력을 남긴다.
