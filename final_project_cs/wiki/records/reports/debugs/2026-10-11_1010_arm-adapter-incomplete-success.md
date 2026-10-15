---
type: report
title: Oracle ARM 연결기의 불완전 답변 성공 처리
description: 빈 문자열과 잘린 모델 출력을 성공으로 전달하는 로컬 코드 결함
status: draft
domain: travel
tags: [arm, llm, defect]
---

# 불완전 답을 성공으로 전달하는 연결기

## 부분 해결 — 로컬 검증 완료, 운영 미반영

2026-10-11: 빈 답·비정상 종료·잘못된 JSON과 upstream 형식 오류를502로 구분합니다. 기존 계약11개와 보호 시험7개가 통과했고 기존240응답을 재생했습니다. 실제 Oracle ARM 앱 실패 해결과 배포는 미완료입니다. [결과·백업·재개](../2026-10-11_1030_daily-response-completion-research.md).

## 수정 전 근거

2026-10-11 확인: `deploy/arm/ollama_adapter.py`의 `/api/chat`는 content가 문자열인지만 검사합니다. 빈 문자열·잘린 JSON·출력 한도 종료도 HTTP200으로 전달하고 종료 이유를 버립니다. 기존 실제 합성 여행 진단의 빈 답과 앱의 잘린 JSON 근거는 [08시 보고](../2026-10-11_0800_six-hour-gpu-arm-report.md)에 있습니다.

재현: `content=""` 또는 `content='{"action":'`, `finish_reason="length"`인 upstream 응답을 연결기에 전달합니다. 기대 결과는 모델 응답 실패502이며 고객 입력 오류400이나 성공200으로 표시해서는 안 됩니다. 전체 스키마와 업무 의미는 앱 검증 책임입니다.

위험: 접속·HTTP 성공 수치가 실제 답변 성공처럼 보일 수 있습니다. 자동 재시도나 JSON 임의 보완으로 실패를 감추지 않습니다. [고정 검증 조건](../../../../../program/research/daily_rag_slm/2026-10-11_response_guard_prereg_v1.json)에 따라 로컬 수정·원본 재생·실제 운영 검증을 분리합니다.
