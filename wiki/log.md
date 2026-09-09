---
type: guide
title: 문서 변경 이력
description: 중앙 허브 wiki의 추가·수정 기록. 최근 무엇이 바뀌었는지 여기서 확인한다
status: draft
---

# 문서 변경 이력

최신이 위다. "최근 뭐 바뀌었어"에 답하려고 전체 wiki를 뒤지지 않게 하는 파일이다.

기록 단위는 **개념 문서**다. 오탈자 수정은 적지 않는다. 다음 중 하나면 적는다.

- 문서 추가·삭제
- 결론이나 수치가 바뀜
- `status`가 바뀜
- 소유자가 바뀜

---

## 2026-09-09 — 진입점 문서를 여행으로

도메인이 커머스 CS → 여행 CS 로 바뀐 뒤(계획서 v10, 2026-09-08) **세션이 처음 읽는 문서 다섯**을 여행으로 고쳤다. 어제 루트 `CLAUDE.md` 사실표가 쇼핑몰로 남아 모든 세션이 틀린 사실로 시작했던 것과 같은 종류의 위험이다.

| 문서 | 무엇이 바뀌었나 |
|---|---|
| [quickstart.md](quickstart.md) | 제품 정의를 여행 지속관리 CS로. 30초 요약(1순위 고객·접점 API·7주·이용권 59,000원), 승계/버린 것, 사실 충돌 순위에 v10 추가 |
| [index.md](index.md) | 「여행 판올림」 절 신설 — 낡음 실측(198문서 중 104개 53%가 커머스 낱말), 영역별 승계 여부. DoD 29 → 22, business 원가가 쇼핑몰 것이라는 표시. 미결정 표를 v10 §0-3 로 교체 |
| [product/index.md](product/index.md) | 이 영역에서 scope 만 여행이고 positioning·problem·personas 는 쇼핑몰이라는 경고 |
| [product/scope.md](product/scope.md) | **전면 개정.** 여행 MVP 7주 In/Out, 실행 경계(Pre-CS 는 우리 DB 일정 버전만·`tier=='simulated'` 게이트), Team 범위(Activity·Booking Handoff 필수), 지연 제약을 API 접점 기준으로 다시. 옛 커머스 범위는 「옛 도메인」 절로 보존 |
| [cs/wiki/index.md](../final_project_cs/wiki/index.md) | 코어는 승계·Team 페이지 다섯은 쇼핑몰이라는 표시. v10 §5-A 의 코어 변경 넷과 Trip·`trigger_source` |

**아직 안 한 것** — `positioning`·`problem`·`personas`·`glossary`·골든셋·business 숫자는 그대로 쇼핑몰이다. 여행 Team 페이지(Activity·Booking Handoff·Dining·Mobility)는 아직 0개다.

---

## 2026-09-01 (5) — 시험 구축 완료

### 위치 정리

저장소별 wiki를 **전부 `program/` 아래로 옮겼다.** 원본 저장소 4곳은 건드리지 않는다.

```
program/
├─ wiki/                       중앙 허브
├─ final_project_cs/wiki/
├─ final_project_sample/wiki/
├─ datasets/wiki/
├─ acop_dojo/wiki/
└─ scripts/  check_wiki.py · sample_docs.py
```

링크 41개를 재작성했고 검사기가 어긋난 5건을 잡아 고쳤다.

### 완료

| 저장소 | 문서 |
|---|---|
| `wiki/` (중앙 허브) | 48 |
| `final_project_cs/wiki/` | 52 |
| `final_project_sample/wiki/` | 2 |
| `datasets/wiki/` | 3 |
| `acop_dojo/wiki/` | 3 |

**모든 영역이 index + 하위 문서를 갖췄다.** 미작성 링크 0건.

### 문서 쓰면서 코드에서 찾은 것

- **`order_items.unit_cents`가 이미 있다.** 환불 계산 결함의 두 가정 중 하나는 지금 데이터로 고칠 수 있다 → [D-001](decisions/D-001-payment-ownership.md) 조치를 1-A/1-B로 분리
- **MCP 도구가 정확히 3개이고 전부 `mcp:read`.** 개수가 테스트로 고정돼 있다
- **Response Review Team이 실제로 죽어 있었다.** 테스트가 문제의 경로를 건너뛰어 발견이 늦었다
- **Context Broker가 설정 오류에 기동 시 죽는다.** 섹션 예산 합이 12,000과 다르면 예외
- **Registry가 Team을 import하지 않고 주입받는다.** docstring이 `never imports app.modules`

### 남은 것

| 할 일 | 소유 |
|---|---|
| 코드 역방향 표식 `# invariant:` | **cs 프로젝트에 의뢰함** |
| 다른 사람 1명의 독립 분류 15건 | `[미확보]` 이관 전 필수 |
| 실제 이관 250~380건 | 게이트 통과 후 |

---

## 2026-09-01 (4) — type 재검증. 기준 통과

같은 표본 45건을 고친 정의로 다시 분류했다. → [governance/type-verification.md](governance/type-verification/index.md)

| 지표 | 1차 | 2차 |
|---|---|---|
| 애매 비율 | 25% | **4.5%** |

11건 중 9건이 풀렸다. `evidence`·`runbook` 추가가 5건, 판정 규칙이 4건을 해소했다.

**남은 2건은 분류 실패가 아니다.** `decision`과 `plan`이 한 문서에 있는 것이라 **이관할 때 쪼개면 된다.** 표본 비율로 보면 이관 대상 중 10~17건이 분할 대상일 수 있다. `[추정]`

### ★ 이 재검증의 한계를 적어 둔다

**혼자 했고, 규칙을 내가 방금 썼다.** 규칙을 만든 사람이 적용하면 맞을 수밖에 없다.

**4.5%를 액면 그대로 믿으면 안 된다.** 다른 사람 1명이 15건을 독립 분류해 일치율을 봐야 한다. 30분이면 되고, **이관 전 마지막 게이트다.**

---

## 2026-09-01 (3) — ★ type 분류 검증. 기준 미달로 목록 수정

실제 문서 45건을 `type`에 대입했다. → [governance/type-verification.md](governance/type-verification/index.md)

| 지표 | 기준 | 실측 | 판정 |
|---|---|---|---|
| 애매 비율 | 15% 이하 | **25%** (11/44) | **미달** |
| 일치율 | 80% 이상 | 측정 못 함 (혼자 분류) | — |

### 무엇이 애매했나

| 패턴 | 건수 | 해소 |
|---|---|---|
| DoD 증거 (재현 명령 + 판정) | 4 | **`evidence` 추가** |
| 장애 대응 절차 | 1 | **`runbook` 추가** |
| vision ("지금 안 하는 이유") | 2 | `decision`으로 두고 판정 규칙 추가 |
| 설계·검토·해소안 | 4 | **문서가 큰 것.** 분할 트리거로 처리 |

### 결론

**`type` 8개 → 10개.** `evidence`·`runbook`을 추가했다.

**둘 다 codex 초안의 13개 목록에 있었고 내가 8개로 줄일 때 뺀 것이다.** 검증이 codex 쪽 손을 들어줬다.

남은 4건(설계·검토·해소안)은 type 추가로 안 풀린다. 전부 161~216줄이라 **type이 애매한 게 아니라 한 문서가 여러 일을 하고 있다.** 분할 트리거로 처리한다.

### 반영

- [governance/front-matter.md](governance/front-matter.md) — type 목록, 판정 규칙 3개 추가
- `program/scripts/check_wiki.py` — 허용 type 갱신
- `program/scripts/sample_docs.py` — 표본 추출을 재현 가능하게 스크립트화 (seed 고정, md5 동일 확인)

### 남은 것

`[미확보]` **두 사람 독립 판정으로 일치율을 못 냈다.** 혼자 분류하면 자기 기준에 맞춰 읽게 된다.

`[미확보]` **재검증.** 정의를 고쳤으니 같은 표본에 다시 대봐야 15% 아래인지 안다.

---

## 2026-09-01 (2) — ★ 검증에서 낡은 수치 발견·정정

`program/scripts/check_wiki.py` 를 만들어 표준을 실제로 검사했다. 그 과정에서 **인용한 평가 수치가 무효 데이터였음**을 발견했다.

### 무엇이 틀렸나

초판이 인용한 `eval/reports/raw_proposed.jsonl`·`raw_baseline_a.jsonl`·`raw_baseline_b.jsonl`은 **2026-08-13 측정이고 `case_id`가 `g-billing-*`인 옛 구독 도메인** 데이터다.

`final_project_cs/CLAUDE.md`가 2026-08-17에 이 측정을 무효로 선언했다. 코퍼스와 golden/holdout이 쇼핑몰 도메인으로 교체됐기 때문이다.

| 항목 | 초판 (무효) | 정정 |
|---|---|---|
| 건당 LLM 비용 | 4.06원 | **3.03원** |
| p50 지연 | 33.9초 | **20.0초** |
| p95 지연 | 50.6초 | **32.2초** |
| Baseline A / B | 0.35 / 0.92원 | **새 도메인 재측정본 없음** |
| 온프레미스 손익분기 | 28,100건 (32명) | **37,600건 (43명)** |
| 자체호스팅 배수 | 2.7~10.5배 | **3.6~14배** |
| 건당 총계 (A-COP 병행) | 1,133원 | **1,132원** |
| LLM 비중 | 0.36% | **0.27%** |

### 결론은 바뀌었나

**방향은 안 바뀌었다.** LLM 비용은 여전히 사람 대비 무시할 수준이고, 지연은 여전히 실시간 채팅에 부적합하다.

**두 가지가 바뀌었다.**

1. **손익분기가 올라갔다.** API가 싸질수록 자체호스팅이 불리해진다. 32명 → 43명
2. **Baseline 비교를 못 한다.** "단순 LLM보다 몇 배 비싸다"를 지금은 말할 수 없다. 중간발표 전 재측정 필요

### 고친 문서

`business/` 4건, `product/` 2건, `evaluation/` 3건, `delivery/` 2건, `decisions/` 1건, `governance/` 2건, `final_project_cs/wiki/context/` 1건.

### 배운 것

**`[실측]` 표기만으로는 부족하다.** 그 측정이 **아직 유효한지**를 함께 봐야 한다. 데이터 파일이 존재한다고 그 숫자가 현재를 대표하지 않는다.

`sources` 필드에 측정 시점과 도메인을 적는 것을 [governance/evidence-grades.md](governance/evidence-grades.md)에 반영해야 한다. `[미확보]`

---

## 2026-09-01 — wiki 신설

### 추가

`wiki/` 중앙 허브를 만들었다. 기존 `program/plan/`·`program/research/`의 문서는 아직 이관하지 않았다.

| 영역 | 상태 |
|---|---|
| `product/` | 초안 작성 |
| `business/` | 초안 작성 |
| `architecture/` | 초안 작성 |
| `delivery/` | 초안 작성 |
| `evaluation/` | 초안 작성 |
| `research/` | index만 |
| `decisions/` | D-001 작성, 나머지 index만 |
| `governance/` | 초안 작성 |

전부 `status: draft`다. 이관 문서는 기본 draft로 두고, 사람이 확인한 뒤에만 `stable`로 올린다.

### 결정 기록

- [D-001 결제 소유 경계](decisions/D-001-payment-ownership.md) — 결제 실행은 검증 쇼핑몰이 소유한다

### 미결정으로 올린 것

- 가격 정책, 자체호스팅 채택, 검토·승인 소요시간, 음성 채널 원가

---

## 이관 예정

아래는 아직 `program/plan/`에 있고 이 wiki로 옮겨야 한다.

| 원본 | 목표 | 판정 |
|---|---|---|
| `A-COP_구현계획서_v8.md` (1,466줄) | 여러 영역으로 분할 | 분할 |
| `A-COP_사업성_단위경제.md` | `business/` 4개 문서 | 분할 |
| `A-COP_페인포인트_페르소나_설계.md` | `product/` 2~3개 문서 | 분할 |
| `A-COP_결제소유_경계.md` | `decisions/D-001` | 이관 완료 |
| `A-COP_문서구조_v1.md` | `governance/document-standard.md` | 분할 |
| `A-COP_문서표준_설계_codex초안.md` | 참고자료. 이관 안 함 | 제외 |

전체 범위 산정은 [governance/migration.md](governance/migration.md).
