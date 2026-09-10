---
type: reference
title: 다이어그램 8종
description: 무엇을 그렸고 근거가 어디인가. 재생성 절차 포함
status: draft
tags: [architecture, documentation]
owners: [human:미배정]
domain: travel
---

# 다이어그램 8종

`[실측]` `program/plan/diagram/_다이어그램_근거.md`에서 이관. **원본과 SVG·puml 파일은 그대로 있다.**

## 재생성

```bash
python program/plan/diagram/render_all.py
```

```bash
python program/plan/diagram/build_showcase.py
```

**둘 다 PlantUML 서버 접속이 필요하다.** 오프라인에서는 안 된다.

결과는 `A-COP_다이어그램_모음.html`이다.

## 8종과 근거

| 다이어그램 | 무엇을 그리나 |
|---|---|
| **유스케이스** | 외부 주체와 업무 기능 범위. Core·CS Pack·Commerce Pack·MCP·A2A·승인 경계·운영자 ★**낡음** |
| **클래스** | 핵심 계약, `TeamExecutorPort`, `TeamResult`, `ActionProposal` 경계 |
| **시퀀스** | Case 생성 → WAIT/RESUME → 승인 → 결과 반환 |
| **상태** | 상태 전이 단일 진입점, 충돌, resume token, TTL 만료 |
| **ERD** | 테이블·ENUM·FK·이벤트 소싱·중복 방지·`vector(1536)` |
| **컴포넌트** | Core 8개 구성과 **두 Broker 분리**, 책임 경계 |
| **A2A 시퀀스** | Agent Card → Task → input-required → Artifact. Catalog Remote 후보 선정 ★**낡음** |
| **배포** | 3개 배포 단위와 **고객용 Composer 배제** 원칙 |

## ★ 상태 다이어그램의 라벨 두 종류

`[실측]` **범례에 이 구분을 표시한다.**

| 라벨 | 무엇 |
|---|---|
| **영문** | 실제 **이벤트명**. 계약에 있는 것 |
| **한글** | 이벤트명이 없는 전이에 붙인 **설명용** |

**섞어 읽으면 없는 이벤트를 찾게 된다.**

→ [`case-lifecycle.md`](../../final_project_cs/wiki/runtime/case-lifecycle.md) · [sample](../../final_project_sample/wiki/runtime/case-lifecycle.md)

## archive 로 옮긴 것

`[실측]` 이유와 함께 기록돼 있다.

| 파일 | 왜 |
|---|---|
| `A-COP_UML_다이어그램_v2.html` | 초기 3종만 담아서 8종판으로 대체 |
| `render_new.py` · `render_new2.py` | 일부만 렌더링. `render_all.py`로 통합 |
| `acop_plan_basis_v2.txt` | 초기 3종 근거 보고서. 핵심 사실을 흡수 |

**대체할 때 이유를 적는 게 규칙이다.** 안 적으면 나중에 왜 없어졌는지 모른다.

## 다이어그램이 낡는 조건

**계약이 바뀌면 다시 그려야 한다.**

| 바뀌면 | 다시 그릴 것 |
|---|---|
| `TeamResult` 필드 | 클래스 |
| Case 상태 전이표 | 상태 |
| 테이블·ENUM | ERD |
| Core 구성요소 | 컴포넌트 |
| 배포 단위 | 배포 |
| **도메인** | 유스케이스 · A2A 시퀀스 |

★**[2026-09-09 실측] 그림 여덟 중 둘이 이미 낡았다.** 2026-09-08 도메인 판올림을 안 반영했다.

| 그림 | 무엇이 낡았나 |
|---|---|
| 유스케이스 | `CS Pack`·`Commerce Pack` 구획. v10 은 여행 Team 다섯이다 |
| A2A 시퀀스 | Remote 후보가 `Catalog & Verification`. v11 §5 에 그 Team 이 없다 — **여행 쪽 대응 `Place Verification` 이 2026-09-10 에 생겼다**(`travel_remote_agent.py`). 그림만 안 고쳤다 |

나머지 여섯(클래스·시퀀스·상태·ERD·컴포넌트·배포)은 **도메인 무관이라 안 낡았다.** 계약을 안 바꿨기 때문이다(v11 §0-2).

`[미확보]` **다시 그리지 않았다.** PlantUML 서버 접속이 필요하다. 여행 Team 은 2026-09-09 에 코드에 붙었으므로 유스케이스를 그릴 재료는 생겼다.

`[미확보]` **자동 검사가 없다.** 계약이 바뀌어도, 도메인이 바뀌어도 다이어그램은 조용히 낡는다.

## 관계

- [core-design.md](core-design.md) — Core 8개 구성요소
- [system-context.md](system-context.md) — 외부 경계
- [`case-lifecycle.md`](../../final_project_cs/wiki/runtime/case-lifecycle.md) · [sample](../../final_project_sample/wiki/runtime/case-lifecycle.md) — 상태 전이
- [`data/schema/index.md`](../../final_project_cs/wiki/data/schema/index.md) · [sample](../../final_project_sample/wiki/runtime/index.md) — ERD 근거
