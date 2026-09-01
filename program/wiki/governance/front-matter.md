---
type: policy
title: front matter 규격
description: 문서 머리에 붙이는 YAML 메타데이터. type만 필수이고 stable로 올릴 때 나머지가 필수가 된다
status: draft
tags: [governance, documentation]
---

# front matter 규격

문서 맨 위에 YAML로 붙인다. 에이전트가 **본문을 읽기 전에** 이 파일이 필요한지 판단하는 재료다.

```markdown
---
type: concept
title: Shared State
description: Customer Case의 공식 상태. 버전을 가지며 모든 갱신은 CAS를 거친다
tags: [runtime, state, concurrency]
status: stable
owners: [human:서유현]
---

# Shared State
```

## 필수와 선택

**항상 필수인 것은 `type` 하나다.** OKF v0.2가 그렇게 정했고 우리도 따른다. 초안을 빨리 쓸 수 있어야 해서다.

`status: stable`로 올릴 때 나머지가 필수가 된다.

| 필드 | draft | stable |
|---|---|---|
| `type` | **필수** | **필수** |
| `title` | 권장 | **필수** |
| `description` | 권장 | **필수** |
| `status` | 선택 | **필수** |
| `owners` | 선택 | **필수** |
| `tags` | 선택 | 권장 |
| `sources` | 선택 | 권장 |
| `automation` | 생성물이면 필수 | 생성물이면 필수 |

## `type` 목록

8개로 시작한다. 늘리기는 쉽고 줄이기는 어려워서 작게 잡았다.

| type | 용도 | 예 |
|---|---|---|
| `concept` | 개념·책임·구조 | Shared State, Context Broker |
| `decision` | 선택과 이유 | 결제 소유 경계 |
| `plan` | 일정·작업·DoD | 중간발표 계획, DoD 29항목 |
| `contract` | API·스키마·저장소 간 약속 | TeamResult 계약 |
| `guide` | 사용법·온보딩·진입점 | quickstart, 모든 index |
| `report` | 특정 시점의 결과 | 평가 리포트, 사업성 분석 |
| `research` | 조사와 비교 | GraphRAG 검토 |
| `policy` | 규칙 | 이 문서 |
| `dataset` | 데이터 의미와 제약 | 쿠팡 주문 기록 |

`index.md`와 `log.md`는 `type: guide`를 쓴다.

**애매하면 이렇게 판단한다.**

| 헷갈리는 쌍 | 가르는 기준 |
|---|---|
| `concept` vs `policy` | 사람이 지켜야 할 규칙이면 policy. 시스템 구조 설명이면 concept |
| `report` vs `research` | 우리가 측정한 결과면 report. 남이 만든 자료 조사면 research |
| `decision` vs `concept` | 되돌리려면 근거가 필요하면 decision |
| `plan` vs `decision` | 앞으로 할 일이면 plan. 이미 정한 선택이면 decision |

여기서 계속 헷갈리는 사례가 나오면 [document-standard.md](document-standard.md)에 기록하고 목록을 고친다.

## 필드 규칙

### `title`
한국어 표시명. 파일명과 달라도 된다.

### `description`
**한 문장.** `index.md`가 이 문장을 그대로 재사용한다. 제목보다 중요하다.

```yaml
❌ description: Controller 설명
⭕ description: Case를 Team으로 라우팅하고 재시도·재계획과 WAIT/RESUME을 통제한다
```

나쁜 예에는 정보가 없다. 에이전트가 이 파일을 열지 말지 판단할 수 없다.

### `tags`
영어 소문자 kebab-case. 통제 목록에서 고른다.

```text
agent  api  architecture  contract  cost  customer-operations
data  evaluation  gpu  release  security  state  testing  ui
```

**영역명이나 type을 태그로 반복하지 않는다.** `runtime/` 폴더의 문서에 `runtime` 태그는 불필요하다.

목록에 없는 태그가 필요하면 이 문서를 고치고 추가한다. 아무나 새 태그를 만들면 검색이 안 된다.

### `status`

| 값 | 뜻 |
|---|---|
| `draft` | 작성 중이거나 검토 전 |
| `stable` | 사람이 확인함. 믿고 인용해도 됨 |
| `deprecated` | 더 이상 유효하지 않음. 대체 문서를 링크 |

**이관해 온 문서는 기본 `draft`다.** 옛 문서가 새 구조에 들어왔다는 이유로 권위가 생기면 안 된다.

### `owners`
유지 책임자. 1명이 원칙이고 공동은 최대 2명.

```yaml
owners: [human:서유현]
```

사람은 `human:<이름>`, 자동 프로세스는 `process:<이름>`.

### `sources`
문서가 파생된 자료. 근거 등급과 함께 쓴다. 상세는 [evidence-grades.md](evidence-grades.md).

```yaml
sources:
  - id: S1
    title: 2026-08-31 문서 실측
    resource: ../../governance/migration.md
```

### `size_exempt`
300줄 규칙에서 제외되는 목록형 문서에만 붙인다. **이유가 없으면 CI가 실패시킨다.**

```yaml
size_exempt: true
size_exempt_reason: 용어 카탈로그. 검색 대상이므로 한 파일로 유지
```

분할 규칙은 [document-standard.md](document-standard.md)의 "문서가 커질 때"에 있다.

### `automation`
자동 생성 문서에만 붙인다.

```yaml
automation:
  command: python dojo.py report
  owner: process:dojo-report
  manual_edit: false
```

`manual_edit: false`면 손으로 고치지 않는다. CI가 검사한다.

## CI가 검사하는 것

```text
1. front matter에 type이 있는가
2. type이 허용 목록에 있는가
3. status: stable인데 title/description/owners가 없는가
4. tags가 통제 목록에 있는가
5. automation.manual_edit: false 문서가 수동 수정됐는가
```

## 관계

- [document-standard.md](document-standard.md) — 문서 본문 규칙
- [evidence-grades.md](evidence-grades.md) — `sources`와 근거 등급의 연결
- [review-policy.md](review-policy.md) — draft에서 stable로 올리는 절차
