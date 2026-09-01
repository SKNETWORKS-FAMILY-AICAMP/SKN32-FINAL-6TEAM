---
type: policy
title: 문서 구조 짜는 법
description: 폴더와 파일을 어떻게 배치하고 언제 쪼개는가. 파일이 폴더로 승격되는 규칙 포함
status: draft
tags: [governance, documentation]
---

# 문서 구조 짜는 법

[document-standard.md](document-standard.md)가 **문서 하나를 어떻게 쓰는가**라면, 이 문서는 **문서들을 어떻게 배치하는가**다.

## 1. 계층 모델

5단계다. 각 단계는 다음 단계로 가는 **길만 알려주고 지식은 담지 않는다.**

```text
Level 0   CLAUDE.md              어느 wiki를 볼지
   ↓
Level 1   wiki/quickstart.md     지금 하려는 일이 무엇인지 묻고 영역으로 보낸다
   ↓
Level 2   wiki/index.md          영역 지도
   ↓
Level 3   영역/index.md          그 영역의 문서 지도 + 읽기 순서
   ↓
Level 4   개념 문서              실제 지식
   ↓
Level 5   소스 코드              구현
```

**각 단계에서 다음으로 갈 판단이 서야 한다.** Level 2를 읽고 어느 영역인지 모르면 Level 2가 잘못 쓰인 것이다.

에이전트가 "환불 계산을 고쳐줘"를 받으면 이렇게 움직인다.

```text
CLAUDE.md          → "코드 수정은 final_project_cs/wiki"
quickstart.md      → "쓰기 동작 추가 → actions/"
actions/index.md   → "action-proposal.md와 evidence-check.md"
개념 문서 2개       → 규칙과 불변식 파악
코드                → 수정
```

**전체를 읽지 않는다.** 이게 목적이다.

## 2. 어디에 두는가 — 중앙 vs 로컬

주제로 정하지 않는다. **무엇이 이 문서를 틀리게 만드는가**로 정한다.

| 질문 | 배치 |
|---|---|
| 특정 저장소의 코드·스키마가 바뀌면 틀려지는가 | 그 저장소 `wiki/` |
| 코드와 같은 PR에서 리뷰해야 하는가 | 그 저장소 `wiki/` |
| 둘 이상의 저장소가 동등한 당사자인가 | 중앙 `program/wiki/` |
| 특정 커밋에 귀속되지 않는가 (일정·포지셔닝·사업성) | 중앙 |

애매하면 이 순서로 판단한다.

1. 이 문서를 틀리게 만드는 변경이 **어디서 일어나는가**
2. 그 변경과 **같은 PR로 고칠 수 있으면** 그 저장소
3. 원인이 둘 이상이면 **중앙**
4. 중앙 문서는 관계와 이유만 쓰고 **세부는 로컬로 링크**

### 예시

| 문서 | 배치 | 왜 |
|---|---|---|
| TeamResult 계약 | `final_project_cs/wiki/teams/` | 코드가 바뀌면 계약도 바뀐다 |
| 결제 소유 경계 | `program/wiki/decisions/` | cs와 검증 쇼핑몰 둘 다 당사자 |
| 건당 원가 | `program/wiki/business/` | 특정 커밋에 안 묶인다 |
| Shared State 불변식 | `final_project_cs/wiki/runtime/` | 테스트가 강제한다 |
| DoD 29항목 | `program/wiki/delivery/` | 여러 저장소에 걸친다 |

## 3. 영역을 새로 만들 때

영역(최상위 폴더)은 함부로 늘리지 않는다. **6~8개가 상한**이다. 그 이상이면 Level 2에서 판단이 안 선다.

새 영역이 정당한 조건 셋.

1. 기존 어느 영역에도 안 들어간다
2. 문서가 **최소 3개**는 될 것이다
3. 소유자가 명확하다

문서 1~2개짜리 영역은 만들지 않는다. 가장 가까운 기존 영역에 넣는다.

**빈 폴더를 미리 만들지 않는다.** 필요할 때 만든다.

## 4. ★ 파일 → 폴더 승격

이 구조에서 가장 자주 쓸 규칙이다.

### 언제

[document-standard.md](document-standard.md)의 분할 트리거에 걸렸을 때. 요약하면 이렇다.

| 신호 | |
|---|---|
| 소유자가 둘로 갈린다 | 자른다 |
| 변경 주기가 다르다 | 자른다 |
| 독립적으로 링크하고 싶은 절이 생긴다 | 자른다 |
| `type`이 섞인다 | 자른다 |
| 목차를 봐야 원하는 절을 찾는다 | 자른다 |
| 300줄 초과 | 검토. 500줄 초과면 자른다 |

### 어떻게

```text
business/unit-economics.md          600줄
        ↓
business/unit-economics/
   ├─ index.md          ← 결론과 지도
   ├─ human-cost.md     ← 사람 원가
   ├─ acop-cost.md      ← A-COP 원가
   └─ comparison.md     ← 비교
```

**index.md에 결론이 남아야 한다.** 이게 승격의 성패를 가른다.

```markdown
❌ # 단위경제
   ## 문서
   - human-cost.md
   - acop-cost.md
   - comparison.md
```

목차만 있으면 읽는 사람이 3개를 다 열어야 한다. 쪼개기 전보다 나빠졌다.

```markdown
⭕ # 단위경제

   사람 1건 4,100~4,846원. A-COP 병행 1,132원. 그중 LLM은 3.03원.
   **비용의 99.7%는 여전히 사람이다.**

   | 문서 | 답하는 질문 |
   |---|---|
   | [human-cost.md](human-cost.md) | 상담원 1인 실비가 얼마인가 |
   | [acop-cost.md](acop-cost.md) | A-COP이 건당 얼마 쓰는가 |
   | [comparison.md](comparison.md) | 합치면 얼마가 되는가 |
```

**결론은 index에, 근거는 하위 문서에.**

### 승격 절차

```text
1. 하위 문서로 내용을 나눈다
2. index.md를 쓴다 — 결론 + 지도
3. 원본 파일을 지운다
4. 이 파일을 참조하던 링크를 전부 고친다     ← CI가 잡아준다
5. log.md에 적는다
```

4번을 빠뜨리면 남의 문서에서 링크가 깨진다. 승격 전에 미리 알린다.

### 역방향 — 폴더를 파일로 되돌리기

하위 문서가 2개 이하로 줄고 각각 100줄 미만이면 되돌린다. 폴더가 얇으면 탐색만 늘어난다.

## 5. 폴더 안에 몇 개까지

| 개수 | 판정 |
|---|---|
| ~12개 | 정상 |
| 12~20개 | 하위 그룹화 검토 |
| 20개~ | 하위 폴더로 나눈다 |

20개가 기준인 이유는 `index.md`의 표가 그 이상이면 훑기 어려워지기 때문이다.

나눌 때는 **`index.md`의 "읽기 순서"에서 자연히 갈리는 지점**을 찾는다. 억지로 절반씩 자르지 않는다.

```text
teams/                      (11개 — 정상이지만 성격이 갈린다)
├─ index.md
├─ team-contract.md         ┐
├─ team-registry.md         │ 계약·구조
├─ team-boundary.md         ┘
├─ voc-store-manager.md     ┐
├─ response-review.md       │ 개별 Team
├─ return-refund.md         ┘
...
        ↓ 20개를 넘으면
teams/
├─ index.md
├─ contract/                ← 계약·구조
└─ modules/                 ← 개별 Team
```

## 6. 이름 짓기

| 대상 | 규칙 | 예 |
|---|---|---|
| 폴더 | 영어 소문자, 복수형 명사 | `teams/`, `decisions/` |
| 파일 | 영어 소문자 kebab-case | `shared-state.md` |
| 결정 문서 | `D-<번호>-<주제>.md` | `D-001-payment-ownership.md` |
| 예약 파일 | `index.md`, `log.md`, `quickstart.md` | |

**파일명은 개념 이름이다.** 파일 이름이 아니다.

```text
❌ controller-py.md          코드 파일을 따라감
❌ 2026-09-01-회의.md         시점을 따라감
⭕ agentic-controller.md     개념
⭕ conflict-retry.md         개념
```

시점이 이름에 들어가는 건 `report`와 마일스톤뿐이다.

```text
⭕ delivery/milestones/midterm-2026-09-15.md
```

## 7. 새 문서를 추가하는 절차

```text
1. 어느 저장소인가        → §2 배치 기준
2. 어느 영역인가          → 없으면 §3으로 새 영역 검토
3. index.md에 먼저 등록   → 제목 + description만
4. 문서를 쓴다            → document-standard.md 골격
5. 인접 문서에서 링크를 건다
6. log.md에 적는다        → 새 개념 문서면
```

**3번을 먼저 하는 이유**는 다른 사람이 같은 문서를 중복 작성하지 않게 하려고다.

## 8. 안티패턴

| 안티패턴 | 왜 나쁜가 | 대신 |
|---|---|---|
| 숫자 접두사 폴더 (`01-product/`) | 순서가 고정돼 삽입이 어렵다 | `index.md`가 읽기 순서를 담당 |
| 깊이 4단계 이상 | 경로가 길어지고 상대링크가 지저분해진다 | 3단계까지. 넘으면 영역을 다시 본다 |
| `misc/`, `etc/`, `기타/` | 여기 들어간 건 아무도 안 찾는다 | 안 맞으면 영역 정의를 고친다 |
| 파일 1개짜리 폴더 | 탐색만 늘어난다 | 상위에 파일로 둔다 |
| `index.md` 없는 폴더 | 탐색이 끊긴다 | CI가 검사한다 |
| 코드 구조를 그대로 미러링 | 작업은 파일이 아니라 개념 단위로 일어난다 | 개념으로 자른다 |
| 문서 안에 목차(TOC) | 문서가 크다는 신호다 | 쪼갠다 |

마지막 줄이 중요하다. **문서에 목차를 넣고 싶어지면 그 문서는 이미 크다.**

## 9. 구조가 잘 됐는지 보는 법

3개월 뒤 이걸 확인한다.

| 질문 | 잘 됐다면 |
|---|---|
| 새 사람이 quickstart만 보고 첫 문서를 찾는가 | 찾는다 |
| 에이전트가 3~4개 문서만 읽고 작업하는가 | 그렇다 |
| 300줄 넘는 문서가 몇 개인가 | 목록형 예외 말고는 없다 |
| `index.md`를 읽고 하위를 안 열어도 되는 경우가 있는가 | 있다 (결론이 index에 있어서) |
| 같은 사실이 두 곳에 적혀 있는가 | 없다 |
| 링크가 깨진 곳이 있는가 | 없다 (CI가 막는다) |

## 관계

- [document-standard.md](document-standard.md) — 문서 하나를 쓰는 법
- [front-matter.md](front-matter.md) — `size_exempt` 등 메타데이터
- [review-policy.md](review-policy.md) — 승격·분할 시 리뷰
- [migration.md](migration.md) — 기존 문서를 이 구조로 옮기는 계획
