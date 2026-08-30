# 모듈 토글 실효화 — 검증 로그

- 실행일: 2026-08-30
- 커밋: 538ff06 (변경 적용 후, 커밋 전 작업트리)
- DB: PostgreSQL 127.0.0.1:5433 acop (기동 중)
- 계약: docs/handoff/08_모듈_컴포넌트_목록.md §2, §6-4

## 1. 선언을 실제로 바꿔 가며 확인

```
python -m scripts.verify_module_toggles
```

```

===== VOC 켬 — 화면과 메뉴가 있다   (voc: true)
GET /ui/voc -> 200
상단 메뉴에 VOC 링크 -> True

===== VOC 끔 — 기동 자체가 거부된다   (voc: false)
기동 -> ProjectConfigError | module 'voc' is disabled; cannot assemble inline classifier

===== graph_store 켬 — 어댑터 이름이 뜬다   (graph_store: true)
관리자 화면 GraphStorePort 줄 -> SqlGraphAdapter

===== graph_store 끔 — 껐다고 적는다   (graph_store: false)
관리자 화면 GraphStorePort 줄 -> 모듈 꺼짐 (graph_store)

===== mcp 켬 — tool 이 동작 경로로 간다   (mcp: true)
tool 호출 -> 통과 (DB 조회까지 감)

===== mcp 끔 — tool 이 거부된다   (mcp: false)
tool 호출 -> ProjectConfigError | module 'mcp' is disabled; cannot assemble MCP tool surface

원복 확인: 5 개가 켜져 있다
```

## 2. 계약 테스트

```
python -m pytest tests/contract/test_module_toggles.py -q
```

```
.........                                                                [100%]
9 passed in 1.62s
```

## 3. 전체 테스트 (회귀 확인)

```
python -m pytest -q -m "not live"
```

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
424 passed, 4 deselected, 36 warnings in 32.66s
```

## 4. 실제 브라우저 확인

`CLAUDE.md` §4 — 백엔드 테스트 통과만으로 완료라 하지 않는다. 화면을 실제로 열었다.

```
python -m uvicorn app.presentation.api.app:app --port 8042
```

`--reload` 를 쓰지 않았다. 모듈 조립은 기동 때 한 번만 일어나므로 선언을 바꾸면
프로세스를 다시 띄워야 하고, reload 자식 프로세스가 남아 옛 코드를 서빙한 적이 있다.

### graph_store: true (기본)

`http://127.0.0.1:8042/ui/admin` 의 Ports 표를 브라우저에서 읽은 값이다.

```
TeamExecutorPort     LocalTeamExecutor
MessageBrokerPort    OutboxBrokerAdapter
GraphStorePort       SqlGraphAdapter
```

상단 메뉴(`/ui/cases`)의 실제 HTML:

```html
<nav><a href='/ui/cases' aria-current=page>Cases</a><a href='/ui/approvals'>Approvals</a><a href='/ui/voc'>VOC</a><a href='/ui/admin'>Admin</a></nav>
```

### graph_store: false 로 바꾸고 재기동

같은 화면, 같은 방법으로 읽은 값이다.

```
TeamExecutorPort     LocalTeamExecutor
MessageBrokerPort    OutboxBrokerAdapter
GraphStorePort       모듈 꺼짐 (graph_store)
```

빈칸으로 두지 않았다. 빈칸은 "껐다"와 "고장났다"를 구별해 주지 못한다.

### 원복 후 재기동

```
GraphStorePort       SqlGraphAdapter
```

`config/project.yaml` 은 원본 그대로다.

## 판정

통과. 여섯 모듈 전부가 선언에 따라 실제로 코드를 가른다.

미해결로 남긴 것은 `docs/reports/2026-08-30_2300_모듈토글_실효화_리포트.md` §5 에 적었다.
