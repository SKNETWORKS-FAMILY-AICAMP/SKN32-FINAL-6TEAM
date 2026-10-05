---
type: decision
title: 업무 도메인 폴더는 app/domains/<도메인>/ 아래 다섯 칸으로 나눈다
description: 여행 코드 69개가 한 폴더에 섞여 있던 것을 모듈·인스턴스·컴포넌트·Port·입구 칸으로 나눈다. 옛 app/domain 은 Case 상태 규칙이라 app/core/case_lifecycle 로 옮겼다
status: accepted
tags: [architecture, composition]
domain: neutral
domain_note: 폴더 구조 규칙은 도메인 무관이다. 지금 도메인이 여행이라 예시로 travel_ops 가 나온다
---

# D-CS-013 업무 도메인 폴더 구조

`[2026-10-06 사용자 결정]` 구조와 칸 이름은 사용자가 정했고, 바깥 폴더 이름은 Codex 와 2회차에 합의했다(기록: 아래 「근거」).

## 맥락

`app/modules/travel_ops/` 바로 아래에 파이썬 파일 **69개**가 하위 폴더 없이 있었다(2026-10-05 실측, 전체 130개 · 39,116줄).
웹 로그인 · 고객 채팅 · 감시 루프 · 일정 계산 · 팀이 한 줄로 나란히 있어 무엇이 필수 부품이고 무엇이 끌 수 있는 기능인지 이름으로 알 수 없었다.
지난 7일 동안 이 폴더를 건드린 커밋이 77개라 늦출수록 옮길 때 충돌이 는다.

## 결정

> **업무 도메인 코드는 `app/domains/<도메인>/` 에만 둔다. 그 안을 프로젝트의 구성 단위([../teams/composition.md](../teams/composition.md))대로 나눈다.**

```
app/
├─ core/
│  ├─ transition.py          Case 상태를 바꾸는 유일한 문
│  └─ case_lifecycle/        Case 상태 규칙(이벤트 종류 · 허용 전이표 · 리듀서) ← 옛 app/domain/
└─ domains/                  업무 도메인 자리 — 경계 시험이 지키는 울타리 (지금 이름 app/modules/)
   └─ travel_ops/
      ├─ __init__.py         팀 등록 — 설정 파일이 가리키는 이름을 다시 내보냄
      ├─ modules/            모듈 — 꺼도 나머지가 돈다 (웹 계정 · 개인 AI 입구 · 실시간 진행)
      ├─ instances/          인스턴스 — 에이전트 팀. 팀 하나 = 폴더 하나 (+ _shared 공용 부품)
      ├─ components/         컴포넌트 — 빼면 안 돈다 (일정 · 계획 · 장소 · 접수 · 대화 · 적용기 · 예약 · 감시 · 코어에 꽂는 여행 어휘)
      ├─ ports/              Port — 구현을 바꿔 끼우는 자리 (알림 채널 · 외부 데이터 소스)
      ├─ entry/              고객 입구 — HTTP 경로
      └─ scenarios/          시연 · 하루 대조 시험용 조립
```

파일 단위 배치표는 0단계에서 실제 import 관계로 다시 확인한 뒤 이 문서에 붙인다(지금은 각 파일 첫 설명 줄로 나눈 초안 — 리포트 참조).

## 이름 — 선택지와 이유

| 자리 | 채택 | 버린 것과 이유 |
|---|---|---|
| 바깥 울타리 | **`domains/`** | `modules`(프로젝트 안에서 「모듈 = 끌 수 있는 기능」이라 안쪽 칸과 겹침) · `packs`(ContextPack 과 겹침, 현행 계획서에 없는 옛 용어) · `contexts`(Context Broker · ContextPack 과 겹침, 코드 179회) · `services`(case_service 등 124회) · `plugins`(필수 부품까지 들어 있어 「덧붙이는 것」과 안 맞음) |
| 옛 `app/domain/` | **`app/core/case_lifecycle/`** | 내용이 업무 도메인이 아니라 Case 상태 규칙 두 파일이다. 구성 문서가 이미 「Case lifecycle」이라 부르고, 유일한 상태 변경 문 `app/core/transition.py` 옆이다. 그대로 두면 `domain`·`domains` 가 한 글자 차이로 함께 있게 된다(사용자 거부) |
| 팀 칸 | **`instances/`** | `agents`(프로젝트 구성 단위 이름이 「인스턴스」) |
| 모듈 칸 | **`modules/`** | `features`(바깥이 `domains` 가 되면 겹침이 사라져 바꿀 이유가 없다) |

## 옮기는 순서

다른 세션과 덜 부딪히는 칸부터 한 칸씩. 칸마다 — 옮기기 → 옛 주소에 한 줄짜리 안내 파일 → 시험(묶음으로 나눠) → 내 경로만 커밋 → 다른 세션에 새 주소 알림.

| 단계 | 내용 | 상태 |
|---|---|---|
| 0 | 옛 `app/domain` → `app/core/case_lifecycle` · 잔재 정리 · 이 결정 문서 | **끝 (2026-10-06)** |
| 1 | 울타리 이름 `app/modules` → `app/domains` + 경계 시험 · Composer 허용 목록 · 설정 주소 | 시작 전 |
| 2 | 모듈 칸(웹 계정 · 개인 AI 입구 · 실시간 진행)과 Port 칸 | 시작 전 |
| 3 | 고객 입구 칸 | 시작 전 |
| 4 | 컴포넌트 칸 | 시작 전 |
| 5 | 인스턴스(팀) 칸 — 다른 세션이 가장 많이 고치는 곳이라 마지막 | 시작 전 |
| 6 | 옛 주소 안내 파일 철거 · 문서 갱신 | 시작 전 |

칸끼리의 규칙(팀끼리 직접 부르지 않는다 · 입구가 팀 속을 직접 부르지 않는다 · 컴포넌트가 끌 수 있는 모듈을 부르지 않는다)은 **처음 칸이 생기는 1~2단계에 시험으로** 넣는다. 처음에는 어기는 곳의 수만 세고, 옮기면서 0으로 줄인다.

## 울타리 밖에서 들어올 후보

| 지금 자리 | 무엇 | 들어갈 칸 | 비고 |
|---|---|---|---|
| `app/infrastructure/travel/` (파일 28) | 관광공사 · 기상청 · 재난문자 · 교통 · 구글 장소 등 **여행 외부 데이터 소스** | `ports/` | ★지금 코어 층에 있는데 경계 시험이 못 잡는다 — 시험의 업무 단어 목록(booking · itinerary · lodging …)에 날씨 · 교통 같은 말이 없다. 부르는 곳은 조립 파일 · 여행 코드 · `app/tools` 뿐이라 옮길 수 있다 |
| `app/presentation/a2a/travel_remote_agent.py` | 원격 에이전트 왕복 검증용 상대역 | `scenarios/` | 옮기면 경계 시험 예외 목록이 하나 준다 |
| 여행 마이그레이션 · `config/` · `eval/` | DB 표 · 설정 · 평가 자료 | 옮기지 않음 | 마이그레이션은 실행 순서가 경로에 묶여 있고, 설정 · 평가는 이미 울타리로 인정되거나 앱 밖이다 |

## 결과

- 이 결정으로 기능은 바뀌지 않는다. 파일 자리와 가져다 쓰는 주소만 바뀐다.
- 못 하게 되는 것: 여행 코드를 `app/domains/` 밖(코어 층)에 두는 것. 1단계부터 경계 시험이 막는다.

## 근거

- 0단계 리포트: [2026-10-06_0030_폴더정리_0단계_리포트.md](../records/reports/2026-10-06_0030_폴더정리_0단계_리포트.md)
- 이름 합의(Codex 본계정 2회): 1회차 Claude `packs` · Codex `domains` → Claude 가 입장을 바꿈. 사용자가 `domain`·`domains` 공존을 거부 → 2회차 둘 다 「옛 domain 을 core/case_lifecycle 로 옮기고 바깥은 domains」. 검토자는 기계다.
- 실무 관례: 업무 영역 하나를 `modules/` 로 묶는 방식(NestJS · FastAPI 모듈러 모놀리스)이 가장 흔하다. 루비 진영은 `packs/`(Shopify · Gusto packwerk), Phoenix 는 `contexts/`, Django 는 `apps/`, Nx 는 업무 영역별 묶음 폴더를 쓴다.
