---
type: handoff
title: 2026-10-20 오라클 모델 순서 · x600 통로 세션 인계
description: 오라클 api·worker 의 x600 경유 줄, x600 통로 재기동, 런팟 끊김 시험 보류, 점검 공지 미완을 넘긴다
status: draft
domain: travel
---

# 2026-10-20 오라클 모델 순서 · x600 통로 세션 인계

상세 기록: [2026-10-20_oracle-x600-fallback-and-failover-test](../records/reports/2026-10-20_oracle-x600-fallback-and-failover-test.md)

## 한 일 목록

- 오라클 `.env.apikeys` 에 `ACOP_OLLAMA_FALLBACK_BASE_URLS=http://127.0.0.1:11438` 한 줄 추가(백업 있음), api·worker 재생성, 새 값 확인.
- x600 역방향 통로 재기동, 오라클 `127.0.0.1:11438` 응답 200 확인.
- 런팟 11436 · x600 11438 에 짧은 질문을 보내 두 경로 모두 답함 확인(실제 고객 경로 아님).
- develop `ae6f4236` 이 원격에 있고 `502da503` 을 포함함을 확인.
- 점검 모드 경로가 떠 있는 api 안에 있음을 확인(`POST /admin/api/commands`, `maintenance`).
- Codex 읽기 전용 교차 검증 다섯 건. 호출 순서의 로컬 판정은 로컬 뒤처짐 때문에 틀림으로 나왔다. 위키 점검 기록 없다는 주장은 틀렸고 정정했다.

## 남은 일

- 런팟 끊김 → x600 전환 시험(운영 터널을 끊는 작업이라 사용자 결정 또는 직접 실행 필요).
- 관리 콘솔에서 점검 공지 켜기(관리자 자격은 이 세션이 다루지 않음). 시험 뒤 끄기.
- 내장 올라마 18312 주소 확인(현재 404).
- 디스크 여유 기준 재측정(commit 세션 10.00GiB, 이 세션 56G 불일치).
- commit 세션 몫: 밀린 커밋 1189건, 오라클 `manual_overlay` 해제 여부 확인.
- 아마존(EKS) 확인은 kubectl 접속 설정 후.
