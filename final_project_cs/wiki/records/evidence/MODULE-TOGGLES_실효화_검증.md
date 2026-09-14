# 모듈 토글 실효화 — 검증 로그

## ★2026-09-06 재실행 — 이 로그가 **결함을 정상으로 승인**했었다

2026-08-30 판정은 「통과. 여섯 모듈 전부가 선언에 따라 실제로 코드를 가른다」
였다. 그중 한 줄이 이것이었다.

```
===== VOC 끔 — 기동 자체가 거부된다   (voc: false)
기동 -> ProjectConfigError | module 'voc' is disabled; cannot assemble inline classifier
```

**이틀 뒤 v8 재판정(2026-09-01)이 바로 이 동작을 결함(높음)으로 뒤집었다.**
인라인 분류는 v9 §3-A 가 요구하는 **필수 기능**이라 선택 플래그에 매달면
안 된다 — "끌 수 있는 모듈" 이라 선언해 놓고 끄면 제품이 안 뜨는 건 결함이다.

★**검증 로그가 물은 질문 자체는 맞았다.** "선언대로 동작하는가" 를 물었고
답은 맞았다. **선언이 틀렸다는 건 이 로그가 물을 수 있는 질문이 아니었다.**
그래서 당시 판정을 틀렸다고 하지 않는다 — 다만 **이 로그를 근거로 "voc
토글은 검증됐다" 고 읽으면 안 된다.**

### 재실행 결과 (2026-09-06)

```
===== VOC 끔 — 화면만 사라지고 분류는 계속 돈다   (voc: false)
기동 -> 성공 (인라인 분류는 필수라 voc 플래그에 안 매달린다)
GET /ui/voc -> 404 (404 면 화면이 사라진 것)
상단 메뉴에 VOC 링크 -> False
인라인 분류 조립 -> 성공

===== graph_store 켬/끔     SqlGraphAdapter  /  모듈 꺼짐 (graph_store)
===== mcp 켬/끔             통과 (DB 조회까지 감)  /  ProjectConfigError
원복 확인: 5 개가 켜져 있다        (6 선언 중 a2a_executor 만 꺼짐)
```

`voc` 를 뺀 나머지(graph_store·mcp 토글)는 **2026-08-30 과 같다.**
대조 기록이 「재실행하지 않았다」로 남겨 둔 부분을 여기서 닫는다.

### ★스크립트가 라벨과 정반대를 출력하고 있었다

수정이 들어간 뒤에도 `scripts/verify_module_toggles.py` 는 **"VOC 끔 — 기동
자체가 거부된다"** 라는 라벨을 그대로 달고 **"기동 -> 성공"** 을 출력하고
있었다. 라벨만 읽고 넘기면 아직 막히는 줄 안다 — 오류·라벨이 사실을 잘못
전하지 않게 한다(`CLAUDE.md` §3).

라벨을 고치고, 지금 계약이 요구하는 것을 **실제로 확인하게** 프로브를 바꿨다.

| 지금 계약 | 프로브가 보는 것 |
|---|---|
| 기동은 된다 | `create_app()` 성공 |
| 화면·메뉴는 사라진다 | `/ui/voc` → 404, 메뉴 링크 False |
| **분류는 계속 돈다** | `build_classifier()` 성공 |

셋 중 하나라도 어긋나면 「★회귀다」를 함께 찍는다. 회귀를 **막는** 것은
`tests/contract/test_module_toggles.py` **9 passed** 다 — 그중
`test_inline_classification_is_not_gated_by_voc` 와
`test_the_aggregation_batch_is_not_gated_by_voc` 가 이 계약을 고정한다.

---

## 아래는 2026-08-30 당시 기록 — `voc` 줄은 지금 사실이 아니다

- 실행일: 2026-08-30
- 커밋: 538ff06 (변경 적용 후, 커밋 전 작업트리)
- DB: PostgreSQL 127.0.0.1:5433 acop (기동 중)
- 계약: wiki/records/handoff/08_모듈_컴포넌트_목록.md §2, §6-4

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

미해결로 남긴 것은 `wiki/records/reports/2026-08-30_2300_모듈토글_실효화_리포트.md` §5 에 적었다.
