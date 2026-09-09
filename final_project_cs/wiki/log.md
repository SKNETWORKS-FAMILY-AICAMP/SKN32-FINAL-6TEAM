---
type: guide
title: 문서 변경 이력 (cs)
description: 이 저장소 wiki의 추가·수정 기록
status: draft
domain: neutral
domain_note: 작업 로그다. 무엇을 했는지의 기록이라 도메인이 섞인다
---

# 문서 변경 이력 (cs)

최신이 위다. 기록 기준은 [중앙 허브 표준](../../wiki/governance/review-policy.md)을 따른다.

오탈자는 적지 않는다. **문서 추가·삭제, 결론·수치 변경, `status` 변경, 소유자 변경**만 적는다.

---

## 2026-09-01 (2) — 역방향 표식 완료. 양방향 잠김

cs 프로젝트가 테스트에 `# invariant:` 표식을 넣었다.

```python
# invariant: INV-CS-ARCH-001
def test_basement_layers_do_not_know_the_business_domain(): ...
```

`[실측]` 검사기 대조 결과.

| | 값 |
|---|---|
| 코드 표식 | **48개** |
| 문서 불변식 | 51개 |
| 코드에만 있는 ID | **0개** |
| 문서에만 있는 ID | 3개 |

**문서에만 있는 3개는 정상이다.** `INV-CS-TEAM-003·004·005`는 판정이 `review`라 대응 테스트가 없다.

### 이제 무엇이 잠겼나

```
문서 → 테스트   경로와 함수 실재를 검사기가 확인   117개
테스트 → 문서   표식 ID 가 카탈로그에 있는지 확인   48개
```

**한쪽만 고치면 CI가 잡는다.** 테스트를 지우면 문서가 가리키는 곳이 사라지고, 표식만 남기면 카탈로그에 없는 ID가 된다.

### 남은 것

`[미확보]` **Team 경계 3개의 자동화.** import 검사로 가능해 보인다.

```
INV-CS-TEAM-003  side effect 를 실행하지 않는다
INV-CS-TEAM-004  read 도구를 직접 호출하지 않는다
INV-CS-TEAM-005  다른 Team 을 직접 호출하지 않는다
```

`tests/architecture/test_basement_is_domain_free.py`가 이미 import 검사를 하므로 같은 방식을 쓸 수 있다.

**자동화되면 사람 판정이 3개 → 0개가 된다.**

---

## 2026-09-01 — wiki 신설

### 추가

`final_project_cs/wiki/` 를 만들었다. 기존 `docs/` 는 그대로 두고 이관하지 않았다.

| 영역 | 상태 |
|---|---|
| `runtime/` | index만 |
| `teams/` | index만 |
| `context/` | index만 |
| `actions/` | index만 |
| `external/` | index만 |
| `data/` | index만 |
| `quality/` | index + **invariants.md** |
| `operations/` | index만 |
| `decisions/` | index만 |

전부 `status: draft`다.

### 불변식 카탈로그 작성

[quality/invariants.md](quality/invariants.md) 에 **33개**를 정리했다. 실제 테스트 함수와 대조했다.

| 영역 | 총 | automated | 사람 판정 |
|---|---|---|---|
| 아키텍처 | 6 | 6 | 0 |
| Team 계약 | 5 | 2 | 3 |
| Action | 3 | 3 | 0 |
| 보안 | 8 | 8 | 0 |
| 도메인 검증 | 7 | 7 | 0 |
| Runtime | 4 | 0 | **4** |

### 작성하면서 드러난 것

**하나 — Runtime 불변식 4개가 자동 판정이 아니다.** Case 상태가 제품의 중심인데 테스트로 강제되지 않는다. 카탈로그의 가장 큰 구멍이다.

**둘 — Team 경계 3개도 자동 판정이 아니다.** side effect 금지, read 도구 직접 호출 금지, Team 간 직접 호출 금지. 설계의 핵심인데 사람 리뷰에 의존한다.

**셋 — `INV-CS-VER-002`가 환불 계산 결함을 못 잡는다.** "환불 ≤ 주문 총액"만 보는데 총액 자체가 잘못된 기준이면 통과한다. 쿠폰 5,000원 사례에서 15,000 ≤ 30,000이라 통과하지만 실제 환불은 12,500원이다.

**넷 — 코드에 `# invariant:` 역방향 표식이 아직 없다.** 넣어야 CI가 양방향 검사를 할 수 있다.

---

## 이관 예정

`docs/` 하위 문서 중 이관 대상 선별이 필요하다. 범위 산정은 [중앙 허브](../../wiki/governance/migration.md).

| 원본 | 판정 |
|---|---|
| `wiki/records/reports/` 151개 | 시점 기록. **제외** |
| `wiki/records/handoff/` 128개 | 완료분 제외, 진행 중만 |
| `wiki/records/history/` 43개 | git으로 복원 가능. 결정만 추출 |
| `wiki/records/plans/` | 선별 이관 |
| `wiki/records/evidence/` | 선별 이관 |
