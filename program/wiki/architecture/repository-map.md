---
type: concept
title: 저장소 지도
description: 저장소 6개가 무엇을 소유하고 어떻게 참조하는가
status: draft
tags: [architecture]
owners: [human:미배정]
---

# 저장소 지도

## 6개

| 저장소 | 역할 | 소유하는 것 |
|---|---|---|
| `program` | 중앙 허브 | 계획·결정·평가 기준·사업성 |
| `final_project_cs` | **릴리스 대상** | Core·Team 구현, 계약, 불변식, 평가 하네스 |
| `final_project_sample` | 참고 구현체 | 계약 선검증. cs로 이식하는 관계 |
| `acop_dojo` | 학습 도장 | cs 구조를 실행 증거로 배우는 프로그램 |
| `datasets` | 데이터 | 데이터셋과 스키마, REPORT |
| `gPUteer` | 사설 GPU 풀 | **별도 워크스페이스.** 개발 인프라 |

## sample과 cs의 관계

**sample에서 먼저 만든 것을 cs로 이식한다.**

```
final_project_sample          final_project_cs
  Composer 쓰기채널     ──→     이식
  Core/Team 계약        ──→     이식
  예시 Team (Billing 등)  ✗     이식 안 함
```

**sample의 예시 Team과 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.** 이걸 혼동하면 "다 됐다"고 착각한다.

## gPUteer의 위치

**A-COP 제품의 일부가 아니다.** 개발·학습 인프라 비용을 낮추는 별도 프로젝트다.

| gPUteer가 푸는 것 | 못 푸는 것 |
|---|---|
| GPU 유휴 시간 (가동률) | **12GB VRAM 천장** |
| 노드 장애 시 작업 유실 | |
| 이질 장비 혼용 | |

gPUteer 문서가 스스로 **"GPU 메모리를 물리적으로 합치는 기술이 아니다"**라고 명시한다. VRAM 문제는 다른 수단으로 푼다. → [../business/infrastructure-cost.md](../business/infrastructure-cost.md)

**A-COP 사업성 계산에는 gPUteer를 개발 단계 비용 절감 요인으로만 넣는다.** 고객사의 자체호스팅 문제를 푸는 제품이 아니다. 섞어 설명하면 심사에서 혼선이 생긴다.

## 문서를 어디에 두는가

주제가 아니라 **무엇이 이 문서를 틀리게 만드는가**로 정한다.

| 질문 | 배치 |
|---|---|
| 특정 저장소의 코드·스키마가 바뀌면 틀려지는가 | 그 저장소 `wiki/` |
| 둘 이상의 저장소가 동등한 당사자인가 | 중앙 `program/wiki/` |
| 특정 커밋에 안 묶이는가 | 중앙 |

상세는 [../governance/structure-guide.md](../governance/structure-guide.md) §2.

## 저장소 간 링크

**상대경로를 쓴다.** 워크스페이스 안에 나란히 있다.

```markdown
[cs의 계약](../final_project_cs/wiki/teams/team-contract.md)
```

**예외는 gPUteer 하나다.** 별도 워크스페이스라 상대경로가 안정적이지 않다. GitHub 절대 URL을 쓴다.

## 정본 우선순위

사실이 충돌할 때.

1. 실행되는 테스트 결과
2. 해당 저장소 `CLAUDE.md`의 기준 사실 표
3. `status: stable` 문서
4. 중앙 허브 문서
5. `status: draft` 문서

**하위 폴더 `CLAUDE.md`가 상위보다 우선한다.** 단 그 폴더 범위 안에서만이다.

## 관계

- [system-context.md](system-context.md) — 시스템 경계
- [../governance/structure-guide.md](../governance/structure-guide.md) — 배치 기준
- [../governance/migration.md](../governance/migration.md) — 저장소별 이관 범위
