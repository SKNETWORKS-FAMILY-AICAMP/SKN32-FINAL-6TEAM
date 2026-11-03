---
type: report
title: 두 응답 계약 분리 — 일정 설명·배치 이유·답 불가 원인 안내 (격리 후보)
status: draft
domain: travel
---

# 두 응답 계약 분리 — 일정 설명·배치 이유·답 불가 원인 안내 (2026-10-29, 격리 후보)

기준: 팀 SKN · 개인 A-COP `role-manager` 원격 tip `fab3da50a`(두 원격 일치 확인). 격리 worktree `cache/scratch/schedule-explain-impl-20261029/wt`, 원본 `C:/_proj/final_workspace` 코드 무수정.
선행: 읽기 전용 조사 `cache/scratch/schedule-explain-audit-20261029/REPORT_KO.md`(원인 1~6). 이전 시도 `deleg_c39d4cd8` 은 8회 호출 뒤 중단(코드 변경 0) — 이어서 함.
계약 문서: [두 응답 계약](../../external/answer-contracts.md).

## 1. 무엇을 바꿨나

| 구역 | 전 | 후 |
|---|---|---|
| 프로그램 계약(유료·로컬 모델 호출) | 엄격 스키마·검증은 있었으나 계약으로 묶인 문서·시험 없음 | `answer_contract` 문서화 + 가짜 클라이언트 시험(엄격 스키마 요청, 산문·스키마 밖 값 거절) — 유료 실호출 0 |
| 일정 설명(fact `day`) | 「일정 N개를 확인했어요 + · 시각 제목」 목록만 | 순서·이동(바로 이웃한 곳만)·**기록된** 배치 이유(`-`)와 상태·영업 비교(`※`), 기록 없는 곳은 「지어내지 않았어요」 명시 |
| 해석 실패(`decision_failed`) | 모든 원인이 「해석 모델 응답 오류 — 잠시 뒤 다시」 | 원인 4분류(capacity · unverified · unavailable · unknown) + 다음 할 일. 진단 원문 비노출 유지, 문의함 안내는 공통 출구 1회 |
| 규정 미일치(ask_policy) | 「지어내 답하지 않았어요 + 요약 + CAN_DO」 | 같은 문장 뒤 다음 할 일(`UNMATCHED_NEXT`) |

바꾸지 않은 것: `decision_unit` SYSTEM·스키마(E4B·유료 프롬프트 바이트 동일), 공개 상태 값, DB, 권한, 웹 입력, 규칙 경로 `_day_answer`.

## 2. 검증 (실제 실행)

| 항목 | 결과 |
|---|---|
| 새 시험 RED(기준 트리 + 모듈만, 연결 전) | 5/24 실패 = 연결 결함 재현(day 설명 4 · 미일치 안내 1) |
| 새·관련 시험 GREEN(최종) | 112/112 = 100% (`test_answer_contract` · 개인정보 · read_requests · policy_rerank) |
| 변이 검출 | 15/15 = 100% (`ev/mutations_r4.json`) |
| 빠른 관문(5 shard, `-m 'not live and not db and not slow'`) | 10,993건 중 실패 1 = 기존 보안 HOLD(`test_no_infra_in_tracked_files` ← ST4F-728 증거 XML), 기준 fab3da50a 동일 실패 · **새 실패 0 · 잃은 시험 0** |
| ruff | 변경 6파일 통과 |
| Claude Opus 5.5 ↔ Codex(gpt-6.1-sol) 검토 4회 | 1차 조건부/거절 → 2차 조건부/조건부 → 3차 승인/조건부 → **4차 승인/승인** |

검토에서 실제로 고친 결함: 걸러 낸 범위에서 이웃 아닌 곳 사이 이동·여유를 지어냄, 실패 원인 부분 문자열 오분류(UUID 안 `429` 등), 넘김 이유 `content+skipped` 오분류·꼬리 파싱, `planner.fixed` 과장, `pick_reason` 무제한 노출, 영업시간의 쉬는 시간·입장 마감·자정 넘김(23:59 보정값을 등록값처럼 말함)·요일별 쉬는 시간, 문의함 안내 중복, 보호 표시를 배치 이유로 셈, 개인정보 시험 기대값 자기참조.

## 3. 비용·개인정보

- 제품 모델 호출: E4B 0 · 유료(OpenAI) 0. 시험은 모두 대역.
- 개발 도구 호출(검토): Claude 4회 합계 $1.60(0.631 + 0.374 + 0.328 + 0.269, `review/r*_claude.json`), Codex 4회 토큰 18,113 · 15,447 · 15,920 · 13,816. 보낸 것은 공개 코드·diff·합성 시험 자료뿐(고객 문장·DB·자격정보 0).

## 4. 시험 수정(contract_correction)

`tests/unit/travel/test_public_decision_failure_privacy.py`: 옛 고정 답(「해석 모델 응답 오류」) 기대값만 새 고정 문장(세 fixture 모두 검증 실패 분류)으로 바꿨다. 진단 원문·예외 이름 비노출, JSON/SSE 일치, 저장 답 일치 단언은 그대로. 옛 값은 fixture JSON 에 보존(`expected != old['answer']`).

## 5. 남은 것 · 판단 필요

1. **실모델 측정 미실시** — 「왜 이렇게 짰어」류가 E4B 에서 `day` 가 아니라 `ask_policy` 로 가는 비율은 이 후보로 바뀌지 않는다(프롬프트 무변경). 측정하려면 E4B 임대·예산 승인 필요 `[미측정]`.
2. `general_requests` 추천 이유(모델이 쓰는 일반 답)를 더 길게: 프롬프트 변경 + E4B·유료 재측정 필요(별도 승인·비용).
3. 통합: 보안 HOLD 해소가 정식 승인된 뒤 role-manager 담당이 두 원격에 ff push → x600 배포 확인. 지금 push 0 · x600 0 · 로컬 서빙 0.
