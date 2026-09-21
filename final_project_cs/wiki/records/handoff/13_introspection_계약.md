# Introspection 계약 — `GET /introspection`

`ops:introspect` scope 로 보호되는 **read-only** JSON API다. 응답은
`app.introspection.contract.snapshot()` 의 조립 메타데이터다.

**현재 `contract_version` = `1.1`** (2026-09-06).

응답에는 활성 모듈과 Port 선언, Team manifest/선언, 실제 Port 구현 이름,
guardrails, LLM provider/model 및 마스킹된 `api_key` 가 들어간다. API key 원문과
tenant 운영 데이터(document/chunk/case/outbox 카운트)는 **넣지 않는다.**

---

## 1.0 → 1.1 — 실행 중인 조립과 저장된 선언을 구분한다

### 왜 올렸나

1.0 은 요청마다 선언을 **다시 읽어서** `config_revision` 을 계산했다. 그래서
Composer 로 선언을 바꾸면:

- 대상은 아직 **옛 조립**으로 요청을 처리하는데
- 화면에는 **새 revision** 이 이미 반영된 것처럼 보였다

저장과 반영은 다르다. 이 둘을 한 필드로 뭉개면 그게 **조용한 성공 위장**이다
(`CLAUDE.md` §0.1).

### 늘어난 필드 넷

| 필드 | 뜻 |
|---|---|
| `active_revision` | 지금 요청을 처리하는 Controller 를 **실제로 만든** 선언. 모르면 `null` |
| `desired_revision` | 저장소에 지금 들어 있는 선언 |
| `reload_state` | `active` · `stale` · `reload_failed` · `unknown` |
| `reload_error` | 마지막 반영 실패 사유. 없으면 `null` |

### `config_revision` 은 남는다 (하위호환)

옛 콘솔은 이 필드만 읽는다. 그래서 **실행 중인 것을 우선** 낸다 —
`active_revision or desired_revision`. 모르면 desired 로 떨어지므로, 정확히
보려면 위 두 필드를 읽는다.

### `unknown` 을 따로 두는 이유

한쪽 revision 을 모르면 `active` 도 `stale` 도 아니다.

- `stale` 로 적으면 **없는 사실을 만든** 것이고
- `active` 로 적으면 **반영 안 된 상태를 정상으로 감춘** 것이다

`snapshot()` 에 `runtime` 을 안 주면(라우터를 직접 붙여 쓰는 테스트 등)
`active_revision` 은 `null`, `reload_state` 는 `unknown` 이다. 저장소에서 읽은
값을 실행 중인 것으로 적지 않는다.

---

## `POST /admin/reload` — 재기동 없이 반영시킨다

**scope `ops:reload`.** 2026-09-06 에 `final_project_sample` 에서 이식했다.

### 왜 별도 scope 인가

`composer:write`(항목 저장) · `composer:admin`(전체 교체)와 **분리한다.**
저장은 되돌릴 수 있지만 **반영은 그 순간 트래픽이 받는 것을 바꾼다.** 저장하는
사람과 반영 시점을 정하는 사람이 같아야 할 이유도 없다.

세 scope 전부 이 엔드포인트에서 403 이다(`tests/e2e/test_reload_endpoint.py`).

### 계약

```
POST /admin/reload          Authorization: Bearer <ops:reload>

200  {"reload_state": "active",
      "active_revision": "...", "desired_revision": "..."}

409  {"error": {"code": "reload_failed",
                "message": "새 선언으로 조립하지 못했다",
                "reload_state": "reload_failed",
                "active_revision": "...",      ← 옛 조립이 그대로 살아 있다
                "desired_revision": "..."}}
```

### 지키는 성질

- **새 조립이 전부 성공한 뒤에만 갈아 낀다.** 실패하면 옛 조립을 그대로 쓰고
  `reload_failed` 를 드러낸다 — 실패를 200 뒤에 숨기지 않는다
- **선언을 못 읽어도 교체하지 않는다.** 빈 조립으로 갈아 끼우면 그 순간 서비스가
  죽는다. 조립 실패와 읽기 실패는 원인이 다르지만 결과는 같다 — 옛 것이 산다
- **router 는 프록시를 붙잡는다**(`ControllerProxy`). 조립 시점의 Controller 를
  붙잡고 있으면 교체해도 옛 것을 계속 쓴다. 교체는 참조 하나를 바꾸는 것이라
  요청이 반쯤 옛것·반쯤 새것을 보는 일이 없다
- **`active` 는 관찰로 계산하지 않는다.** 조립할 때 받아 적는다. 그래서
  `composition.build_controller(config=...)` 가 있다 — 읽은 선언 **그대로**
  조립해야 "읽었던 revision 을 실행 중인 것으로 적는다" 가 성립한다. 조립 뒤에
  다시 읽으면 그 사이 바뀐 선언의 revision 을 실행 중인 것으로 잘못 적는다
- **`pending_reload` 라는 상태를 만들지 않는다.** 이 런타임은 스스로 폴링하지
  않으므로, 아무도 reload 를 부르지 않으면 영원히 pending 이다. 기다리면 되는
  것처럼 보이는 이름을 붙이지 않는다

### 실측 (2026-09-06, 살아 있는 프로세스)

```
[1] 시작       active=6cca23ee13b8 desired=6cca23ee13b8 state=active 계약=1.1
[2] 토글       200 · a2a_executor False → True
[3] 토글 직후  active=6cca23ee13b8 desired=2b89b5f40370 state=stale   ← ★이게 없던 것
[4] reload     200 {active: 2b89b5f40370, state: active}
[5] reload 후  active=2b89b5f40370 state=active · a2a_executor 실제로 True
[6] 복구       active=6cca23ee13b8 state=active a2a=False
```

★`[3]` 이 핵심이다. 계약 1.0 은 여기서 `active` 라고 답했다.

---

## 콘솔(`final_project_ui`) 쪽

- `CONSOLE_CONTRACT_VERSIONS` 기본값이 `1.0,1.1` 이라 그대로 붙는다
- Composer 화면 맨 위에 반영 상태를 적고, **어긋났을 때만** [반영] 버튼을 낸다
- 반영에는 `CONSOLE_RELOAD_TOKEN` 이 필요하다 — ★`CONSOLE_INTROSPECTION_TOKEN`
  (조회)과 **다른 토큰**이다. 대상이 scope 를 나눠 뒀기 때문이다
- 토큰이 없으면 **버튼 대신 왜 없는지**를 적는다. 버튼만 지우면 운영자는
  "이 대상은 반영 기능이 없나 보다" 로 잘못 읽는다

---

## 하지 않은 것

- **폴링** — 대상이 스스로 저장소를 들여다보게 하는 것. 여러 인스턴스의 수렴·
  감시 주기·실패 표시가 따라붙는다. 트리거가 아직 아니다
- **여러 인스턴스** — 지금 계약은 프로세스 **하나**의 active 를 말한다. 같은
  대상을 여러 프로세스로 띄우면 각자의 active 를 따로 물어야 한다
- **분류기 교체** — reload 는 Controller 만 갈아 끼운다
