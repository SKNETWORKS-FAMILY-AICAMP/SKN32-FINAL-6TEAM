---
type: guide
title: 문서 변경 이력 (cs)
description: 이 저장소 wiki의 추가·수정 기록
status: draft
---

# 문서 변경 이력 (cs)

최신이 위다. 기록 기준은 [중앙 허브 표준](../../wiki/governance/review-policy.md)을 따른다.

오탈자는 적지 않는다. **문서 추가·삭제, 결론·수치 변경, `status` 변경, 소유자 변경**만 적는다.

---

## 2026-09-01

### 추가 — wiki 신설

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
| `docs/reports/` 151개 | 시점 기록. **제외** |
| `docs/handoff/` 128개 | 완료분 제외, 진행 중만 |
| `docs/history/` 43개 | git으로 복원 가능. 결정만 추출 |
| `docs/plans/` | 선별 이관 |
| `docs/evidence/` | 선별 이관 |
