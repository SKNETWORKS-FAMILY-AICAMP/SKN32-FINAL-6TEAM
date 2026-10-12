# 작업 — final_project_sample 의 composer 문서 3건을 쓴다

## 배경 (읽고 지켜야 할 전제)

`final_project_cs` 가 릴리스로 나가더라도 `final_project_sample` 은 **혼자 정확히
굴러가야 한다.** sample 은 cs 에 부품을 대주고 버려지는 발판이 아니라 Core/Team
계약의 참조 구현이고, cs 가 떠난 뒤에도 그 자리에 남는다.

그래서 sample 의 내부 구현 설명이 필요하다. 지금은 그게 없다.

## ★ 절대 하지 말 것

1. **`final_project_cs/` 아래 파일을 열지 마라.** 같은 이름의 문서가 거기 있는데,
   그걸 보면 경로만 바꾼 사본이 나온다. 그러면 이 작업이 무의미해진다.
2. **`program/` 아래 wiki 문서도 열지 마라.** 같은 이유다.
3. **없는 것을 있다고 쓰지 마라.** 디렉터리를 언급하기 전에 `ls` 로 파일이
   실제로 있는지 확인해라. 과거에 빈 패키지를 문서화해서 17건이 틀렸다.
4. **추측을 실측처럼 쓰지 마라.** 코드에서 확인한 것만 단정한다.
5. **`build/`·`dist/`·`__pycache__` 아래는 사본이다. 읽지 마라.**

## 읽어야 할 것 (여기만)

```
final_project_sample/acop_composer/api.py
final_project_sample/acop_composer/auth.py
final_project_sample/acop_composer/catalog.py
final_project_sample/acop_composer/service.py
final_project_sample/acop_composer/service_app.py
final_project_sample/tests/e2e/test_composer_write_channel.py
final_project_sample/tests/e2e/test_composer_catalog_changes.py
final_project_sample/tests/e2e/test_composer_ui_client_contract.py
final_project_sample/tests/architecture/test_composer_ui_package_boundary.py
```

## 만들 문서 3건

| 파일 | 답해야 할 질문 |
|---|---|
| `write-channel.md` | 설정을 바꾸는 경로가 왜 하나인가. 그 경로가 무엇을 검사하나 |
| `auth-scope.md` | 누가 무엇을 바꿀 수 있나. scope 를 어떻게 판정하나 |
| `ui-boundary.md` | UI 가 넘으면 안 되는 선이 무엇이고 무엇이 그걸 막나 |

## 형식 (반드시 지킨다)

각 파일 맨 앞에 front matter 를 넣는다.

```yaml
---
type: concept
title: <한 줄 제목>
description: <한 문장. 이 문서가 답하는 질문>
status: draft
tags: [architecture, api, security]
---
```

- `tags` 는 이 목록에서만 고른다:
  `architecture`, `state`, `contract`, `api`, `testing`, `security`, `data`, `agent`
- 본문은 **한국어**. 문서 하나가 **한 가지만** 다룬다.
- 각 문서 **300줄을 넘기지 않는다.**
- 마지막에 `## 관계` 절을 두고 형제 문서를 상대경로로 링크한다.

## 문체

- 결론 먼저, 근거 나중.
- 부제·훈계조 금지. 볼드는 정말 중요한 곳에만.
- 코드에서 확인한 값에는 [실측], 확인 못 한 것은 [미확보] 를 붙인다.
- 파일과 줄 번호를 근거로 댄다. 예: `core/registry.py:88`
- **모르는 것은 모른다고 적는다.** 빈 칸을 그럴듯한 문장으로 메우지 마라.

## 출력 형식

3개 문서를 하나의 응답에 이어서 낸다. 각 문서 앞에 구분선을 넣는다.

```
===== FILE: <파일명>.md =====
---
type: concept
...
```

다른 설명이나 요약은 붙이지 마라. 파일 내용만 낸다.
