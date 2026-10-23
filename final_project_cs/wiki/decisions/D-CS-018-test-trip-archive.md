---
type: decision
title: 시험 여행은 지우기 직전에 보관함에 통째로 담는다 — 보관함 여행은 감시 · 알림 밖
description: 시험 코드로 만든 여행과 「남길 시험 여행」 표시를 단 여행은 지울 때 일정 · 대안 · 채팅까지 trip_archives 에 복사한 뒤 지운다. 표시를 단 여행은 지우기 전에도 감시 · 안내 대상에서 빠진다
status: accepted
tags: [data, retention, travel, testing]
owners: [human:미배정]
domain: travel
---

# D-CS-018 시험 여행 보관함

`[결정 2026-10-20 사용자]` 「시험 여행 보관함 만들어. 지우기 직전에 여행 전체(일정·대안·채팅)를 보관함에 복사하고, 보관함 여행은 감시·알림에서 빼」 ·
「앞으로도 남길 건 거기에 넣게 해」. 계기: 실서버 확인(x600 서버, 게스트) 뒤 시험 여행을 고객 삭제 기능으로 지우자 「텍스트라 용량도 작은데 왜 자꾸 지우나」.

## 한 문단 요약

여행 삭제(`itinerary/trip_delete.delete_trip` — 고객이 지움 · 게스트 정리 · 회원 정리가 모두 지난다)는 이제 **지우기 직전에** 그 여행이 시험 여행인지 본다.
시험 여행이면 여행 행 · 모든 일정 판 · 항목(등록 때 붙인 대안 `detail.alternates` 포함) · 바꿀 안 · 채팅 · 항로 지킴이 기록 · 감시 관측 · 이 여행의 Case 와 사건 기록 ·
알림 문장 · 접수 번호와 미리 준비한 대안을 **한 덩어리(`snapshot`)로** `trip_archives` 에 담고 나서 지운다. 담기가 실패하면 삭제도 일어나지 않는다.
보관함은 별도 표라 감시 · 안내 · 알림 반복이 읽지 않는다. 「남길 시험 여행」 표시를 단 여행은 **지우기 전에도** 감시 · 안내 대상에서 빠진다.

## 시험 여행이란

| 종류(`kind`) | 무엇 | 어떻게 정해지나 |
|---|---|---|
| `test_code` | 시험 코드(`test1` 등, `intake/test_plans.py`)로 만든 접수에서 나온 여행 | 그 여행의 접수에 `intake_test_scenarios` 줄이 있다 — 자동 |
| `marked` | 사람 · 에이전트가 「남길 시험 여행」으로 표시한 여행(실서버 확인 등) | `trip_archive.mark(...)` 로 `trip_archive_marks` 에 한 줄 — 지우기 전에 단다 |

둘 다 아니면 **지금과 같다** — 보관하지 않고 지운다(접수 원문은 기존 접수 백업 `intake_backups` 에 남는다).

## 왜 시험 여행만인가

- 실제 고객의 여행은 약관이 「여행 · 게스트 자료가 지워질 때 함께 파기」로 적는다(2026-10-07 보관 기간 결정). 채팅 · 활동 기록을 비식별로 남길지도 아직 사용자 결정 대기다.
  보관함을 모든 여행에 넓히면 그 결정을 앞질러 버린다. 넓히려면 사용자 결정이 따로 필요하다.
- 시험 여행은 고객 자료가 아니다 — 시험 코드 원문 · 우리가 넣은 실서버 확인 일정이다.

## 감시 · 알림에서 빼기

- 보관된 여행: `trips` 행이 지워지므로 감시 · 안내 · 알림 반복(`itinerary.TripStore._open_trips`)에 나오지 않는다. 바깥함의 그 여행 알림도 삭제가 지운다(보관함에는 문장만 남는다).
- 표시를 단 살아 있는 여행: 감시 대상 좁히기 자리(`itinerary/trip_scope`)에 `trip_archive.marked` 규칙을 꽂는다(`composition.wire_trip_scope`) — 표시가 있으면 감시 · 하루 시작 · 출발 안내에서 빠진다.
- ☆확인 범위: 고객이 화면에서 직접 고친 직후의 「변경」 알림처럼 감시 반복을 거치지 않는 알림 길은 이번에 막지 않았다. 표시는 보통 지우기 직전에 달기 때문이다.

## 얼마나 두나

지우지 않는다(정리 작업 없음). 시험 자료라 양이 작고, 다시 보려는 것이 목적이다. 필요하면 나중에 관리 화면 보관 일수를 더한다.

## 대가 · 한계

- 접수 원문 · 읽은 값 · 고친 값은 기존 접수 백업(`intake_backups`)에 따로 있다 — 보관함에는 접수 **번호**와 미리 준비한 대안만 담는다(두 곳을 접수 번호로 잇는다).
- 보관함은 원래 표의 행을 있는 그대로(`to_jsonb`) 담는다. 표에 칸이 늘면 자동으로 따라오지만, **새 표**가 생기면 담을 목록(`trip_archive._TABLES`)에 더해야 한다.
- 「표시」는 이 결정 이후 만든 실서버 확인부터 쓴다. 2026-10-20 09:47 에 지운 시험 여행(`ef8b8166…`)은 보관 전이라 접수 백업만 남았다.

## 구현

- 마이그레이션 [062](../../app/infrastructure/db/migrations/062_trip_archives.sql) — `trip_archives` · `trip_archive_marks`
- [trip_archive.py](../../app/domains/travel_ops/components/itinerary/trip_archive.py) — `mark` · `kind_of` · `archive` · `summary`
- [trip_delete.py](../../app/domains/travel_ops/components/itinerary/trip_delete.py) — 지우기 직전 `trip_archive.archive_if_test`
- 시험 [test_trip_archives.py](../../tests/e2e/test_trip_archives.py)
- 기록 [2026-10-20 시험 여행 보관함](../records/reports/2026-10-20_시험여행_보관함.md)
