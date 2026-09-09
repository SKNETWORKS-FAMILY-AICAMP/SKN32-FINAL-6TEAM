---
type: policy
title: type 고르는 법
description: type 11개의 정의와 판정 규칙. 고르기 전에 문서를 쪼갤지 먼저 묻는다
status: draft
tags: [governance, documentation]
domain: neutral
---

# type 고르는 법

[front-matter.md](front-matter.md)에서 분리했다. **`type`은 front matter의 유일한 필수 필드**라 규칙이 길다.

## 목록

**10개다.** 8개로 시작했다가 [표본 검증](type-verification/index.md)에서 애매 비율 25%가 나와 2개를 추가했다.

| type | 용도 | 예 |
|---|---|---|
| `concept` | 개념·책임·구조 | Shared State, Context Broker |
| `decision` | 선택과 이유 | 결제 소유 경계 |
| `plan` | 일정·작업·DoD | 중간발표 계획, DoD 29항목 |
| `contract` | API·스키마·저장소 간 약속 | TeamResult 계약, handoff 문서 |
| `guide` | 사용법·온보딩·진입점 | quickstart, 모든 index |
| `report` | 특정 시점의 결과 | 평가 리포트, 작업 요약 |
| `research` | 조사와 비교 | GraphRAG 검토 |
| `policy` | 규칙 | 이 문서 |
| `dataset` | 데이터 의미와 제약 | 쿠팡 주문 기록 |
| **`evidence`** | **DoD·완료 기준의 재현 가능한 증명** | DoD-24 근거 대조 |
| **`runbook`** | **사고·장애 시 따라가는 절차** | unknown 상태 대응 |
| **`reference`** | **바깥에서 가져온 원문·기준값을 그대로 보관** | WBS 원본 전사, 견적 산정 기준 |

### `reference`를 왜 넣었나

`[실측]` blind 대조에서 **내가 목록에 없는 `reference`를 두 번 썼다.** 기존 10개에 딱 맞는 게 없었다.

| 문서 | 왜 안 맞았나 |
|---|---|
| `_WBS원본_2026-08-17.md` | 외부 시트 **원문 전사**. 우리가 조사한 게 아니다 |
| `ESTIMATION_BASELINE.md` | 견적 산정 **기준값**. 규칙도 조사도 아니다 |

codex도 둘 다 애매로 봤다. **두 판정자가 같은 자리에서 막혔으면 빈 자리다.**

| | `research`와 다른 점 | `policy`와 다른 점 |
|---|---|---|
| `reference` | **우리가 분석하지 않았다.** 그대로 보관 | 지키라는 게 아니라 참조하라는 것 |

**바꾸면 안 되는 것이 특징이다.** 원문이 바뀌면 다시 가져오지, 고치지 않는다.

## 예약 파일

`index.md`와 `log.md`는 `type: guide`를 쓴다.

### `README`가 계약을 정의하면

`[실측]` blind 대조에서 **둘 다 `확실`인데 갈린 유일한 건**이 이것이다.

`final_project_cs/wiki/records/handoff/README.md`(`final_project_sample/wiki/records/handoff/README.md` 도 같다) — Claude `guide`, codex `contract`.

그 문서가 폴더를 안내하면서 **동시에 그 폴더의 성격을 정의**한다.

**규칙 — 내용이 결정하지 위치가 결정하지 않는다.**

| 그 파일이 하는 일 | type |
|---|---|
| 어디로 가라고 안내 | `guide` |
| **무엇을 지켜야 하는지 정의** | `policy` 또는 `contract` |
| 둘 다 한다 | **쪼갠다** |

`index.md`도 마찬가지다. 지금 우리 `index.md`들은 안내가 중심이라 `guide`가 맞다.

### 뒤의 둘을 왜 나눴나

`[실측]` 검증에서 애매했던 11건 중 5건이 이 둘이었다.

| | `report`와 다른 점 | `guide`와 다른 점 |
|---|---|---|
| `evidence` | **재현 명령이 필수.** 시점 기록이 아니라 릴리스까지 유효한 증명 | — |
| `runbook` | — | **사고가 났을 때 읽는다.** 처음 시작할 때 읽는 게 아니다 |

`[실측]` 모집단도 크다. `cs/docs/evidence/` 35건, 장애 절차 문서 다수.

## ★ 애매는 두 종류다

`[실측]` 5차 blind에서 애매 8건의 이유가 **전부 "쪼개야 한다"**였다. type을 못 고른 게 아니었다.

| 종류 | 뜻 | 어떻게 적나 |
|---|---|---|
| **분류 애매** | type을 못 고르겠다 | `애매(분류)` — 규칙을 고쳐야 한다 |
| **분할 필요** | 문서가 여러 일을 한다 | `애매(분할)` — 이관할 때 쪼갠다 |

**둘을 섞어 세면 규칙이 나쁜 건지 문서가 나쁜 건지 모른다.**

5차 기준 분류 애매는 1~2건(3.4~6.9%), 나머지 6건은 분할 필요였다.

## ★ type을 고르기 전에 먼저 묻는다

`[실측]` 독립 판정 3회에서 **같은 실패가 세 번 나왔다.** "답하는 질문으로 가른다"는 규칙을 두 번 썼는데 두 번 다 안 먹혔다.

**분류로 풀 문제가 아니었다.** 순서를 바꾼다.

```text
① 이 문서가 한 가지만 하는가?
     아니오 → 쪼갠다. type 은 그 다음이다
     예     → ②
② type 을 고른다
```

### 한 가지만 하는지 어떻게 아나

다음이 **한 문서에 둘 이상 있으면 쪼갠다.**

| 있으면 | type |
|---|---|
| 무엇을 골랐나 + 왜 | `decision` |
| 언제 무엇을 할까 | `plan` |
| 무슨 일이 있었나 | `report` |
| 어떤 선택지가 있나 | `research` |
| 개념·구조 설명 | `concept` |
| 지켜야 할 규칙 | `policy` |

`[실측]` 실제로 걸린 것들.

```
A-COP_예제Team모듈_확충설계   결론 + 설계 + 구현 순서      → decision + plan
DoD28-FT-RAG통합_설계         결론 + 설계 + 리스크 + 후속   → decision + plan
TODO_VISION                   도입 후보 + 폐기 결정         → decision + plan
A-COP_남은작업_인수인계        완료 상태 + 남은 작업         → report + plan
datasets/**/REPORT.md         데이터 의미 + 전처리 현황     → dataset + report
```

**마지막 두 줄이 특히 흔하다.** "지금까지"와 "앞으로"를 한 파일에 적는 습관이다.

### 왜 이 순서가 맞나

`[실측]` blind 대조에서 **둘 다 `확실`이라고 한 15건은 93.3% 일치**했다. 불일치는 거의 전부 애매 구간에서 나왔다.

**분류 체계는 작동한다. 문제는 여러 일을 하는 문서를 억지로 하나로 분류하려 한 것이다.**

## 애매하면 이렇게 판단한다

| 헷갈리는 쌍 | 가르는 기준 |
|---|---|
| `concept` vs `policy` | 사람이 지켜야 할 규칙이면 policy. 시스템 구조 설명이면 concept |
| `report` vs `research` | 우리가 측정한 결과면 report. 남이 만든 자료 조사면 research |
| `report` vs `evidence` | **재현 명령이 있고 완료 판정이 목적이면 evidence** |
| `research` vs `reference` | **판단이 섞였으면 research, 옮기기만 했으면 reference** |
| `guide` vs `runbook` | **사고 났을 때 따라가면 runbook** |
| `dataset` vs `report` | **안 변하면 dataset, 계속 변하면 report** (아래) |
| `decision` vs `concept` | 되돌리려면 근거가 필요하면 decision |
| `plan` vs `decision` | 앞으로 할 일이면 plan. 이미 정한 선택이면 decision |

### 데이터셋 문서는 둘로 갈린다

`[실측]` 독립 판정자(codex)가 잡은 것이다. **내가 못 봤다.**

datasets의 `REPORT.md` 대부분이 두 가지를 한 파일에 담고 있다.

```
데이터가 무엇인가·출처·범위·제약   → dataset   안 변한다
지금 전처리가 어디까지인가        → report    계속 변한다
```

**변경 주기가 다르므로 분할 트리거에 걸린다.** → [document-standard.md](document-standard.md)

`datasets/README.md`의 "VOC 전처리 현황 (2026-08-31 실측)" 절도 같은 구조다.

**이관할 때 쪼갠다.** 데이터 의미는 `dataset`, 진행 상황은 `report`로.

### "지금 안 한다"도 decision이다

`[실측]` vision 문서(`VISION-05`·`VISION-07`)가 검증에서 애매했다. 결정한 게 아니라 **미룬 것**이라서다.

**미루는 것도 결정이다.** `decision`으로 두고 도입 트리거를 재검토 조건으로 적는다.

### "설계"·"검토"·"해소안"이 애매하면 문서가 큰 것이다

`[실측]` 검증에서 애매했던 4건이 전부 161~216줄이었다.

**type이 애매한 게 아니라 한 문서가 여러 일을 하고 있다.** 문서가 답하는 질문으로 가른다.

```text
"무엇을 고를까"       → decision
"어떤 선택지가 있나"   → research
"언제 무엇을 할까"     → plan

셋을 다 하면 → 쪼갠다
```

→ [document-standard.md](document-standard.md)의 분할 트리거

여기서 계속 헷갈리는 사례가 나오면 [type-verification/index.md](type-verification/index.md)에 기록하고 목록을 다시 본다.

