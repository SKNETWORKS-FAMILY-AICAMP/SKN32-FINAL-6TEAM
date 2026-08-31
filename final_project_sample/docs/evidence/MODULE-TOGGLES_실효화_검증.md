# 모듈 토글 실효화 — 검증 로그 (cs 에서 이식)

- 실행일: 2026-08-31
- 커밋: 8fe2a5d (변경 적용 후, 커밋 전 작업트리)
- 원본 작업: ../final_project_cs/docs/evidence/MODULE-TOGGLES_실효화_검증.md

## 1. 선언을 실제로 바꿔 가며 확인

```
python -m scripts.verify_module_toggles
```

```

===== VOC 켬 — 화면과 메뉴가 있다   (voc: true)
GET /ops/voc -> 200
상단 메뉴에 VOC 링크 -> True

===== VOC 끔 — 기동 자체가 거부된다   (voc: false)
기동 -> ProjectConfigError | module 'voc' is disabled; cannot assemble inline classifier

===== graph_store 켬 — 어댑터가 만들어진다   (graph_store: true)
build_graph_store -> SqlGraphAdapter

===== graph_store 끔 — 조립이 거부된다   (graph_store: false)
build_graph_store -> ProjectConfigError | module 'graph_store' is disabled; cannot assemble GraphStore adapter

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
........                                                                 [100%]
8 passed in 1.81s
```

## 3. 전체 테스트 (회귀 확인)

```
python -m pytest -q -m "not live"
```

```
.....................................                                    [100%]
469 passed, 1 deselected in 45.77s
```

## 4. VOC 화면과 메뉴가 함께 사라지는지

`voc: false` 로는 앱이 기동하지 않으므로(§5 참고) 서버를 띄워서는 이 상태를 볼 수 없다.
`mount_ui()` 를 직접 불러 확인했다.

```
voc: true   GET /ops/voc -> 200
   메뉴: ['/ops/cases', '/ops/approvals', '/ops/outbox', '/ops/voc']
voc: false  GET /ops/voc -> 404
   메뉴: ['/ops/cases', '/ops/approvals', '/ops/outbox']
```

화면과 메뉴가 같이 빠진다. 메뉴에만 남아 눌렀을 때 404 가 나는 상태가 아니다.

## 5. 실제 브라우저 확인

`CLAUDE.md` §4 — 백엔드 테스트 통과만으로 완료라 하지 않는다. 화면을 열었다.

```
python -m uvicorn acop_basement.presentation.api.app:app --port 8051
```

`--reload` 없이 띄웠다. 모듈 조립은 기동 때 한 번만 일어나므로 선언을 바꾸면
프로세스를 다시 띄워야 하고, reload 자식 프로세스가 남아 옛 코드를 서빙한 적이 있다.

기본 선언(voc 켬)에서 `http://127.0.0.1:8051/ops/voc` 를 브라우저로 열어 읽은 값이다.

```
제목: VOC 일일 리포트
메뉴: /ops/cases, /ops/approvals, /ops/outbox, /ops/voc
본문: 오늘 건수 0 · 직전 7일 2건 · 부정 비율 0% · 집계 기간 2026-08-11 ~ ...
```

경로 상태 코드:

```
/health        200
/ops/cases     200
/ops/voc       200
```

`config/project.yaml` 은 원본 그대로다(`git diff --stat` 출력 없음).

## 판정

통과. 여섯 모듈 전부가 선언에 따라 실제로 코드를 가른다.

미해결로 남긴 것은 `docs/reports/2026-08-31_모듈토글_실효화_리포트.md` §6 에 적었다.
