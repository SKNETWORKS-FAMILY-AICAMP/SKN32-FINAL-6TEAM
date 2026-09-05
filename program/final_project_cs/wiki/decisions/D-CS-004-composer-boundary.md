---
type: contract
title: Composer 가 바꿀 수 있는 것
description: 모듈 7종·Port 3종은 바꾸고 Core 9종은 못 끈다. 저장은 원자적이다
status: draft
tags: [architecture, contract, ui]
owners: [human:미배정]
---

# Composer 가 바꿀 수 있는 것

`[실측]` `docs/handoff/09_Composer_GUI_계약.md`에서 이관. **원본은 그대로 있다.**

## 모듈 7종 — 켜고 끈다

| 모듈 | 끄면 |
|---|---|
| `vector_rag` | 정책 검색이 없다. **평가에서 grounding 3.98 → 0.00** |
| `graph_store` | 관계 조회 없음 |
| `a2a_executor` | Team 을 원격으로 실행 못 함 |
| `mcp` | 개인 AI 접속 경로 없음 |
| `voc` | 일일 배치·급증 탐지 없음 |
| `ops_ui` | 운영 화면 4종이 404 |
| `composer_ui` | **이 화면 자신이 404** |

**`vector_rag` 행이 ablation 실측값이다.** 끄면 grounding 이 0이 된다. **RAG 없이는 근거가 없다.**

### `composer_ui` 는 자기 자신을 끌 수 있다

**의도한 설계다.** GUI 도 필요 없으면 빠질 수 있어야 한다.

**다만 끄면 GUI 로는 되돌릴 수 없다.** `config/project.yaml` 을 손으로 고쳐야 한다.

→ 체크박스 옆에 **경고를 띄운다.**

## Port 3종 — 구현을 갈아 끼운다

| Port | 선택지 | 상태 |
|---|---|---|
| `team_executor` | `local` · `a2a` | **둘 다 구현** |
| `message_broker` | `outbox` · ~~`redis_streams`~~ | outbox 만 |
| `graph_store` | `sql` · ~~`age`~~ · ~~`neo4j`~~ | sql 만 |

**선택지가 있다고 다 구현된 게 아니다.** 취소선이 미구현이다.

## 끌 수 없는 Core 9종

`[미확보]` 원본에 목록이 있다. **빼면 시스템이 아니다.**

**모듈과 컴포넌트를 나누는 기준이 이것이다.**

| | |
|---|---|
| **컴포넌트** | 선택 불가. 빼면 시스템이 아니다 |
| **모듈** | 선택 가능. 켜고 끌 수 있다 |

## ★ 저장은 원자적이다

`[실측]` 저장 절차 4단계.

```
① 임시 파일에 쓴다
② 정식 loader 로 검증한다      ← 여기서 걸리면 중단
③ 원본을 백업한다
④ 원자적으로 교체한다
```

**실패하면 원본이 보존된다.** 반쯤 쓰인 설정으로 기동하는 일이 없다.

**②가 핵심이다.** 저장 전에 **실제 loader** 로 읽어 본다. 스키마 검사만으로는 부족하다.

## 브라우저 실측

`[실측]` 실제로 눌러 확인한 것.

```
A2A 활성화 · Port 교체 · Team 추가·제거
잘못된 implementation_ref 거부
```

**마지막이 중요하다.** `KNOWN_IMPLEMENTATION_REFS` allowlist 로 막는다. 임의 Python 경로를 못 넣는다.

`[실측]` **이 allowlist는 처음부터 있던 게 아니다.** cs에는 없었고, `composer:write`만 있으면 임의 모듈을 import시킬 수 있었다 — JWT 시크릿 fail-open과 결합하면 인증 없이 도달 가능한 체인이었다(2026-08-24 sample 대조로 발견, allowlist를 sample에서 이식). → [../external/auth-boundary.md](../external/auth-boundary.md)

## 한계

`[실측]` 아직 안 되는 것.

| 한계 | |
|---|---|
| 재기동 | GUI 에서 못 한다 |
| 스캐폴딩 | 새 Team 골격 생성 없음 |
| 백업 | **1단계만** |
| 자기 비활성화 복구 | 파일을 손으로 고쳐야 함 |
| manifest 편집 | 불가 |

## 관계

- [D-CS-001](D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [D-CS-003](D-CS-003-composer-scope.md) — 세 층 구분
- [../../../wiki/decisions/D-006-composer-ownership.md](../../../wiki/decisions/D-006-composer-ownership.md) — 소유권
- [../../../wiki/decisions/D-007-central-config-store.md](../../../wiki/decisions/D-007-central-config-store.md) — 중앙 저장소
- [../../../wiki/architecture/tech-stack.md](../../../wiki/architecture/tech-stack.md) — Port 구현 상태
