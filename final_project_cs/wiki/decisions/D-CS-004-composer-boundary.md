---
type: contract
title: Composer 가 바꿀 수 있는 것
description: 모듈 7종·Port 3종은 바꾸고 Core 9종은 못 끈다. 저장은 원자적이다
status: draft
tags: [architecture, contract, ui]
owners: [human:미배정]
domain: neutral
---

# Composer 가 바꿀 수 있는 것

`[실측]` `wiki/records/handoff/09_Composer_GUI_계약.md`에서 이관. **원본은 그대로 있다.**

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

## ★ [2026-09-06] 구현이 이 저장소에서 나갔다 — v9 §8-D

`[실측]` 코드 세션 커밋 `f2319aa`. 이 페이지가 설명하던 `app/presentation/api/composer.py`(157줄)·`app/application/composer_service.py`(167줄)·`app/presentation/composer_auth.py`(76줄)는 **sample 것을 손으로 베낀 사본이었고 지워졌다.** 구현은 `acop_composer` 패키지에 하나만 있다.

**사본이 실제로 망가뜨리고 있던 것.** sample이 `/catalog`·`/changes`·`/revisions`·`/restore`를 갖는 동안 cs는 `/current`·`/validate`·`/apply`·`/toggle` 넷에 머물렀다. `final_project_ui`는 `/composer/catalog`·`/composer/changes`를 부르므로 **콘솔의 카탈로그·변경 카드가 cs 대상에서는 404**였다. 그리고 `create_app()`이 Composer 라우터를 무조건 붙여 **쓰기 채널이 고객 릴리즈에 그대로 실려** 있었다 — 방어는 scope 하나뿐.

| 이제 | 어디 |
|---|---|
| 이 제품이 패키지에 넘기는 것 — 스키마·등록표(`KNOWN_IMPLEMENTATION_REFS`)·저장소·인증 정책·경로 | `app/composer_host.py` (호스트 어댑터). JWT `aud`는 sample과 **다른 값** — 남의 발급자 토큰이 통하면 안 된다 |
| 파일 저장소 3종 — 선언·이력·감사 | `app/core/composer_stores.py`. **파일만 있다** — cs는 direct(pip) 방식이라 선언이 로컬 파일이다. 중앙을 쓰게 되면 그때 Postgres 구현을 더한다 |
| 선언을 파일 없이 검증 | `app/core/project_config.py` `config_from_declaration()` |
| 관리용 빌드 진입점 | `app/entrypoint.py` — `create_composer_router(host)`·`create_auth_router(host)`를 `create_app()`에 주입. uvicorn 대상 `app.entrypoint:app`. **이때만 `acop_composer`가 설치돼 있으면 된다** |
| 고객 릴리즈 | `app.presentation.api.app:app` 그대로. 라우터를 안 주면 `/composer/*`가 **존재하지 않는다** |
| scope | `composer:admin` 추가(전체 교체 `/apply`·복원 `/restore`). 지금 12종 |
| 게이트 | `tests/architecture/test_composer_stays_out_of_this_repo.py` — `acop_composer`를 알아도 되는 곳은 `app/composer_host.py`·`app/entrypoint.py` 둘뿐이고, 지운 사본 셋이 다시 생기면 실패한다. "사람 눈으로는 막을 수 없다 — 파일 하나 더 만드는 것이 문법적으로 아무 때나 가능하기 때문" |

위 "모듈 7종·Port 3종·끌 수 없는 Core 9종·저장은 원자적이다"는 **계약으로는 그대로다** — 이제 그 계약을 패키지가 이 어댑터를 통해 지킨다. 실제 저장 경로·revision 충돌·이력·복원의 동작은 [sample/composer/write-channel.md](../../../final_project_sample/wiki/composer/write-channel.md)가 정본이다.

## 관계

- [D-CS-001](D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [D-CS-003](D-CS-003-composer-scope.md) — 세 층 구분
- [../../../wiki/decisions/D-006-composer-ownership.md](../../../wiki/decisions/D-006-composer-ownership.md) — 소유권
- [../../../wiki/decisions/D-007-central-config-store.md](../../../wiki/decisions/D-007-central-config-store.md) — 중앙 저장소
- [../../../wiki/architecture/tech-stack.md](../../../wiki/architecture/tech-stack.md) — Port 구현 상태
