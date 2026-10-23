---
type: report
title: Activity·Dining 브랜치 AI 구성과 검증 인계 조사
description: 고정 커밋의 실행 코드와 평가 원문을 대조해 LLM·RAG 사용 범위와 사람 검증 우선순위를 정리한다
status: draft
tags: [testing]
domain: travel
---

# Activity·Dining 브랜치 AI 구성과 검증 인계 조사

[조사 완료·실행 검증 전] **우선순위는 Activity의 사람 정답 검토와 Dining의 실제 모델 종단 평가다.** Activity에는 규칙과 LLM을 비교하는 섀도 구현이 있고, Dining의 핵심 판정은 원장·규칙·계산이다. 두 팀 모두 공통 접수 LLM과 정책 검색을 활용하므로, 팀 내부 LLM 유무만으로 AI 사용 여부를 판단하면 안 된다.

- 조사 기준일: 2026-10-11 KST. 아래는 고정 커밋 조사이며 Claude Code가 진행 중인 병합의 최종 결과를 판정한 문서가 아니다.
- 범위: Activity·Dining 실행 코드, 공통 접수·정책 검색, 기존 평가 JSON·실행기·최신 팀 계획. UI 구현·병합·모델 재실행은 범위 밖이다.
- 수행: Codex. 증거는 [조회·평가 원문 대조 기록](../evidence/2026-10-11_2320_Activity_Dining_AI_검증조사_근거.md).
- 상태 구분: **코드 확인** / **기존 실행 기록** / **팀 계획** / **검증 제안** / **미확인**. 기능 완료율은 분모 모름이다.

## 1. 어느 브랜치를 검증해야 하는가

| 대상 | 고정 커밋 | develop과의 관계 | 검증에서의 의미 |
|---|---|---|---|
| develop | `180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b` | 조사 기준 | 통합본의 공통 접수·RAG를 확인한 판 |
| role-activity | `662485c23aeae2a6016fb645f5c51da237c1d9f0` | tip이 develop에 포함 | 이 브랜치만 보면 최신 LLM 작업을 놓침 |
| role-activity-test | `3fe74c153ab019e88b152113eb028b3edea12c65` | 브랜치만 38커밋 / develop만 25커밋 | 최신 판정 계층·섀도·평가·멘토 반영 계획은 이쪽 |
| role-dining | `af5845370d0b79470bd681d56ff1cd975985de87` | tip이 develop에 포함 / develop만 27커밋 | dining 인스턴스와 두 평가 실행기는 기준 develop과 내용 동일 |

[코드 확인] Activity 테스트 브랜치는 새 폴더 구조 `app/domains/travel_ops/instances/activity`에서 동작한다. `team_a.py` 등 옛 경로를 현재 진입점으로 읽지 않는다. 최신 Activity 섀도가 **develop에 이미 적용됐다고 말할 수 없다.**

[미확인] 병합이 끝난 후 확정되는 SHA, 실제 서버 배포 SHA, 실행 환경변수·DB 마이그레이션·활성 모델. 최종 평가는 그 판을 다시 고정해야 한다. 커밋 수는 기능 수나 진척률이 아니다.

## 2. 실제 AI 사용 지도

| 구간 | 확인된 구현 | 모델·검색 방식 | 판정 범위와 한계 |
|---|---|---|---|
| 공통 고객 문장 분류 | `feedback.classify`: intent·issue_code·sentiment | Ollama 설정이 있으면 해당 경로, 아니면 OpenAI 설정 모델 | 식당·활동 팀에 요청을 보내기 전 분류 |
| 공통 신고·일정 해석 | `trip_intake.extract` 등 OllamaChat JSON 경로 | 설정 모델 사용. 코드 기본 Ollama 이름은 `gemma4:12b` | 늦음·휴무·재요청 등 구조화. 접수 성공이 후속 판정 성공을 뜻하지 않음 |
| 운영시간 원문 구조화 | `place_hours`가 규칙으로 읽은 뒤 필요한 경우 `chat.json` 사용 | 공통 채팅 모델 | 원문 인용·시간 표현 검사. Activity 판정용 LLM과 별도 경로 |
| Activity 판정 계층 | 5종 Judge + 현재 Team의 선택적 shadow 연결 | 기본 `gpt-5.4-nano`, effort `low`, OpenAI Responses API | 기본 rule. 실제 Team은 rule/shadow 허용. 고객 결과는 규칙이 결정 |
| Dining 핵심 실행 | 예약·장소·시간별 원장 상태, 조건 비교, 대안 계산 | Dining Team 자체 직접 LLM 호출 없음 | 고객 문장은 정해진 문구로 구성. 공통 접수·정책 검색은 별도 사용 |
| 공통 정책 검색 | PostgreSQL + pgvector, tenant·scope 제한, cosine top-8 | OpenAI 1536차원 또는 Ollama 1024차원 임베딩 | 현재 설정의 BM25·rerank는 꺼짐. 영업·재난 실시간 사실 저장소가 아님 |

근거: [공통 분류 조립](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/composition.py#L61), [신고 추출 조립](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/composition.py#L182), [운영시간 LLM 추출](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/domains/travel_ops/components/places/place_hours.py#L215), [정책 검색 구현](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/infrastructure/rag/retriever.py#L106).

[주의] 위 모델명은 **추적 코드의 기본값 또는 평가 기록**이다. 개인 PC의 비공개 설정값은 이 PUBLIC 문서에 복사하지 않았다. 기본값, 로컬 파일 설정, 실제 서버에서 호출된 모델은 서로 대조해야 하며 하나로 단정할 수 없다.

## 3. Activity: 구현·계획·검증 공백

### 현재 실행 코드

[코드 확인] `check_feasible`는 이미 시작했는지 → 정원 → 시간·장소 정보 → 코어가 제공하는 재난·기상 → 정기휴무 → 운영시간 등을 검사한다. 자료가 부족하면 unknown/추가 확인으로 남기는 구조다.

- Judge 계층에는 **휴무, 운영시간, 실내외/기상 민감도, 재난 영향, 실시간 영업 여부** 다섯 종류가 있다.
- 현재 Team에 연결된 shadow 지점은 휴무·실내외·재난 영향·live_status다. 운영시간 Judge는 평가 계층에 있지만 Team은 앞 단계의 구조화된 운영시간을 사용한다.
- `judge_modes=("rule", "shadow")`. 라이브러리에 LLM-first 클래스가 있어도 Team에서 고객 결과를 LLM이 결정하는 모드가 켜진 것은 아니다.
- 기본 `activity_judge_mode="rule"`. shadow 설정과 API 키·프롬프트·DB 준비가 있어야 호출·기록이 가능하다.
- shadow는 **규칙의 고객 결과를 유지하면서** LLM 결과·불일치·실패·지연 등을 기록한다.
- 웹 검색은 `live_status`에서 사용한다. 다른 판정의 원문 해석과 분리해야 한다.
- 인용문이 실제 입력에 있는지, URL이 실제 검색 source에 있는지, 날짜가 오래됐는지 확인하는 가드가 있다. **인용 자료가 그 결론을 정말 뒷받침하는지까지 보장하지 않는다.** 날짜 없는 웹 근거는 모두 거절하지 않고 남겨 센다.
- shadow가 반대 판정을 해도 고객 결과가 바뀌지 않는 시험, 모델 오류·스키마 오류·가짜 인용 방어 시험은 존재한다. 이번 조사에서 다시 실행하지 않았다.

근거: [실행 순서](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/app/domains/travel_ops/instances/activity/team.py#L331), [shadow 연결](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/app/domains/travel_ops/instances/activity/team.py#L499), [스키마·근거 가드](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/app/domains/travel_ops/instances/activity/judge/llm.py#L109), [shadow 회귀 시험](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/tests/unit/travel/activity/test_activity_judge_shadow.py#L1).

### 최신 계획은 아직 코드와 다르다

[팀 계획] 10월 10일 정리된 팀 문서는, 전달받은 10월 8일 멘토 피드백을 근거로 **LLM이 읽기 전용 MCP 도구를 고르는 에이전트**로 가는 방향을 기록한다. 해당 문서도 에이전트 루프를 **미착수**로 표시한다. 멘토 원문은 이번 조사에서 확인하지 않았다.

| 최신 계획의 항목 | 기준 코드에서 확인되는 차이 | 필요한 검증 |
|---|---|---|
| 지역 위험형 / 야외 위험형 / 반영 안 함 / 미분류 재난 구분 | 기존 코어 안전 판정과 새 분류 기준의 차이가 팀 문서에 명시됨 | 새 분류표로 사람이 정답 재검토. 같은 구의 산사태는 blocks 기준 |
| 실내외는 처음 한 번 LLM으로 판정·저장, 이후 규칙 사용 | 현재 판정은 shadow이며 LLM 결과의 운영 저장·사용 전환과 별개 | 출처·모델·프롬프트 기록, 모르면 계획 단계에서만 질문 |
| 활동 정원을 feasibility에서 제외 | 현재 `team.py`에는 정원 검사가 있음 | 새 요구에 맞춰 회귀 기대값 확정 후 개발 담당에 전달 |
| 코어 감지 → 판정 호출 연결 | 팀 계획에서 미구현 | 사실 변경이 정확한 활동 하나로 전달되는 통합 시험 |
| 읽기 전용 MCP + 결과 검증 + 사람 확인 | 에이전트 루프 미착수 | 도구 계약·권한·횟수/시간 제한·안전 판정 유지 시험부터 정의 |

[검증 제안] 새 목표와 기존 D-CS-015의 shadow 경계를 먼저 맞춰야 한다. 지금의 높은 평가 수치를 근거로 바로 `llm` 모드를 켜는 것은 검증 결론이 아니다. 감시가 코어 소유인 점을 유지하며 이중 감시·이중 재계획을 확인한다.

근거: [최신 구현 상태와 변경 기준](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/wiki/teams/activity.md#L35), [팀의 남은 작업 목록](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/wiki/teams/activity.md#L224).

### 기존 평가 수치의 정확한 의미

[기존 실행 기록] 2026-10-06 평가: 60개 사례 중 라벨 52개, live_status 8개 무라벨. **정답 작성자는 Claude이고 사람 검토 전**이라고 manifest에 명시돼 있다.

| 지표 | 기록값 | 해석 |
|---|---:|---|
| LLM 허용 정답 집합 일치 | **154/156 = 98.7%**, 95% CI 96.2–100% | 52개 × 3회. 독립 사례 156개가 아님 |
| 당시 규칙 판정 일치 | **24/52 = 46.2%** | 옛 규칙 기준. 현재 규칙의 성능으로 인용하면 안 됨 |
| 휴무 LLM 일치 | **46/48 = 95.8%** | closure-06에서 위험한 확정 2/48 = 4.2% |
| 라벨 사례 반복 일관성 | **48/52 = 92.3%** | 같은 사례 3회가 모두 같은 판정인 비율 |
| live_status 재실행 호출 성공 | **16/24 = 66.7%** | 8/24 = 33.3% 호출 실패, 보고서는 429로 설명 |
| live_status 반복 일관성 | **3/8 = 37.5%** | 정답 정확도가 아님 |
| live_status unknown | **15/24 = 62.5%** | 호출 실패 포함. 자료 부족과 장애를 분리해야 함 |
| 날짜 없는 live_status 인용 | **13/20 = 65.0%** | 유효 URL만으로 현재 영업을 확정하면 안 됨 |

- `metrics.outcome`는 결과가 `acceptable` 집합 안이면 맞다고 센다. 허용 집합에 unknown이 들어갈 수 있으므로 98.7%를 “확정 답변 정확도”로 바꾸어 부르지 않는다.
- 최신 팀 문서에는 develop 규칙을 다시 잰 **26/52 = 50.0%**도 있다. 이는 이번에 실행한 값이 아니며, 위 24/52와 서로 다른 규칙 판이다.
- closure-06은 공휴일 조건이 문제다. 입력 정보로 정말 판단 가능한지 먼저 확인하고, 부족한 사실을 프롬프트 추측으로 메우지 않는다.
- 재난 기대값 자체가 최신 기준에서 변경 대상이다. 기존 **36/36 = 100%**를 새 재난 기준의 성능으로 볼 수 없다.
- live_status는 정답 라벨이 없어 정확도를 계산할 수 없다. 성공한 16회 기준 p50 15.7초, p95 40.7초다.
- 실행기는 고정 사례를 반복하며 별도 holdout을 나누지 않는다. 사람이 검토한 정답과 모델 출력을 보지 않은 새 평가 세트가 필요하다.
- CI는 case 단위 bootstrap 10,000회, seed 7로 계산한 기록이다. 동일 사례 반복을 독립 표본처럼 세지 않은 점은 유지한다.

근거: [평가 manifest](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/eval/activity_judge/manifest.json#L1), [원문 summary](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/eval/reports/activity_judge/20261006T091508Z/summary.json#L1), [live_status 재실행 원문](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/eval/reports/activity_judge/20261006T091915Z/summary.json#L1), [정답 집합 채점](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/3fe74c153ab019e88b152113eb028b3edea12c65/final_project_cs/eval/activity_judge/metrics.py#L22).

## 4. Dining: 핵심은 원장 정확도와 전체 흐름 검증

### 무엇이 이미 있고, 무엇이 계획인가

[코드 확인] Dining Team은 예약 → 장소 → 방문 시각의 원장 상태를 읽고, 영업 여부·방문 조건을 계산해 답한다. 채식·할랄 같은 조건은 충족·불충족·모름을 구분한다. 할랄 정보가 없다는 이유로 충족으로 처리하지 않도록 한 수정도 포함돼 있다.

[팀 계획] `dining-agent-design.md`의 넓은 LLM 에이전트 구상만 보면 오해하기 쉽다. 후속 `dining-mcp-boundary.md`는 **기존 코드가 해결하지 못하는 자유 문의(Q)에 한정**하고, 먼저 Q 비율을 측정한 뒤 도입을 결정하도록 범위를 좁혔다.

- 성공한 요청, 원장의 “모름”, 입력이 없는 요청을 무조건 LLM으로 보내는 계획이 아니다.
- Q 비율 집계와 실제 모델 종단 평가는 팀 문서에 남은 일로 기록돼 있다.
- 해당 Dining MCP 서버·에이전트는 기준 트리에서 구현된 것으로 확인되지 않았다.
- “5% 이상이면 도입”, “10초 상한”은 문서의 **제안**이며 합의된 검증 통과 기준으로 취급하지 않는다.
- `tick.py`의 방문 60분·20분 전 점검 함수는 있지만, 코드 검색으로 그 함수의 운영 호출 배선을 확인하지 못했다. 파일 존재를 활성 스케줄러·알림 발송의 증거로 삼지 않는다. 공통 코어의 다른 감시 경로와도 구분해야 한다.

근거: [Dining 실행](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/app/domains/travel_ops/instances/dining/team.py#L149), [조건 충족 검사](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/app/domains/travel_ops/instances/dining/team.py#L243), [도입 결정과 남은 검증](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/wiki/teams/dining-mcp-boundary.md#L196).

### 기존 평가: 장소 찾기와 대안 계산을 분리해서 읽기

[기존 실행 기록] 2026-10-08 v3-domains, 코드 `d76ecad`. 장소 찾기는 DB 원장 영업 중 1,888곳, Kakao 실호출, **LLM off·TourAPI off** 조건이다.

| 시험 | 개발 세트 | 별도 확인 세트 | 제한 |
|---|---:|---:|---|
| 장소 찾기 채점 통과 | **31/34 = 91.2%** | **9/12 = 75.0%** | 올바른 보류·확인 요청도 정답에 포함. 전부 자동 확정한 비율이 아님 |
| 틀린 장소를 확정 | **0/34 = 0%** | **0/12 = 0%** | 소표본이며 향후 오류가 없다는 보증이 아님 |
| 대체 식당 채점 통과 | **19/19 = 100%** | **8/8 = 100%** | 합성 장소·시간·좌표 기반 계산 평가 |
| 대체 동선 위반 | **0/19 = 0%** | **0/8 = 0%** | 실제 원장/API/LLM을 통과한 전체 여행의 위반률이 아님 |

- 대체 평가의 5회 반복은 **장소 ID 순서 의존을 확인하는 seed 변경**이다. LLM 5회 반복 실험이 아니다.
- 고정·예약 일정의 보호와 사람에게 묻는 단계는 실행기 설명상 평가 범위 밖이다.
- 장소 찾기의 근처 국밥집·근처 칼국수집 실패는 이전 관광지 좌표가 원장 조회로 전달되지 않는 문제로 기존 보고서에 기록돼 있다. 기준 코드에서도 `places.resolve(near=...)` → `_tour(dining,...)` → `find(name, area_code=...)`에 near가 전달되지 않고, 원장 lookup은 별도 ctx에 의존하는 구조를 확인했다. 이번에는 동적으로 재현하지 않았다.
- `Gwangjang Market` 실패는 TourAPI를 끈 평가 조건 영향이 있어 실제 운영 성능과 분리해야 한다.
- 10월 6일 실제 모델 종단 실행은 Ollama 연결 끊김으로 팀 문서에서 무효 처리했다. 위 91.2%·100%를 자연어 분류·추출까지 검증한 수치로 인용하지 않는다.
- 별도 확인 세트의 정답·거리 기준을 실패 결과에 맞춰 바꾸지 않는다. 같은 유형의 새 개발 사례로 수정하고 확인 세트는 유지한다.

근거: [장소 개발 결과](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/eval/reports/2026-10-08_place_lookup_v3-domains.json#L1), [장소 확인 결과](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/eval/reports/2026-10-08_place_lookup_holdout_v3-domains.json#L1), [대체 개발 결과](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/eval/reports/2026-10-08_dining_alternatives_v3-domains.json#L1), [대체 확인 결과](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/eval/reports/2026-10-08_dining_alternatives_holdout_v3-domains.json#L1), [대체 평가의 실제 범위](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/af5845370d0b79470bd681d56ff1cd975985de87/final_project_cs/eval/runners/dining_alternatives.py#L6).

## 5. RAG는 무엇을 검색하며 무엇을 검증해야 하나

[코드 확인] 저장소 여행 지식은 **12문서·130개 절**이다. manifest와 실제 Markdown의 `##` 개수를 대조했다. DB에 현재 130청크가 적재돼 있다는 뜻은 아니다.

- 내용은 활동 취소·운영 제한, 날씨, 식당 예약 조정·대안, 이동, 취소 인계, 동행·접근 조건 등 **서비스 정책**이다.
- Activity scope: travel_activity / travel_weather / travel_cancellation / travel_access.
- Dining scope: travel_dining / travel_cancellation / travel_access.
- 검색은 tenant·허용 scope를 먼저 제한하고 임베딩 cosine 유사도로 top-8을 읽는다. 제공자의 벡터 칸이 비어 있으면 오류로 처리한다.
- 현재 공통 `question_answer`는 검색한 절에 연결된 **고객용 문구 상위 2개와 구조화된 예약 조건**을 조합한다. 이 경로의 마지막 문장을 생성 LLM이 새로 쓰는 구조는 아니다.
- 음식점의 오늘 영업·할랄 제공 여부·현재 재난은 해당 사실 소스에서 확인해야 한다. 일반 규정 검색 결과가 사실 확인을 대체하지 않는다.
- 여행 RAG 통합 시험은 적재량, 네 가지 대표 질의, scope·tenant 격리 등을 검사한다. 시험 코드의 존재와 현재 DB에서 통과한 결과는 다르다.

[검증 제안] 질의마다 관련 문서·절을 사람이 지정하고 Recall@8, MRR, 근거 없는 질문에서의 보류, 최종 문구와 근거의 일치, 숫자 조건의 정확성, 타 tenant·scope 유출을 따로 잰다. 이번에 확인한 자료만으로 독립 여행 질의 세트의 검색 품질을 확정할 수 없다.

근거: [여행 corpus manifest](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/knowledge/travel/manifest.json#L1), [retriever](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/infrastructure/rag/retriever.py#L106), [고객 문구 구성](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/app/domains/travel_ops/instances/_shared/itinerary_team.py#L439), [여행 RAG 시험](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/blob/180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b/final_project_cs/tests/integration/rag/test_travel_corpus_retrieval.py#L30).

## 6. 사용자가 도와주면 효과가 큰 부분

[검증 제안] 코드보다 먼저 **무엇을 정답으로 볼지** 사람이 결정해야 하는 영역이다. 모델 답을 보고 거기에 정답을 맞추지 않는다.

| 우선 | 사람이 검토할 것 | 구체적인 판단 예 | Codex가 이어서 맡을 것 |
|---|---|---|---|
| 1 | Activity 52개 기존 라벨 + 새 위험 사례 | 공휴일 예외, 혼합 실내외, 같은 구 산사태, 방문 시점이 먼 재난, 자료 없을 때 unknown 허용 | 라벨 근거·버전 고정, 개발/최종 세트 분리, 현재 규칙·shadow 비교와 오답 분류 |
| 2 | Dining 자연어 요청의 기대 처리 | “예약 그대로 두고”, “할랄 아니면 안 돼”, “30분 늦어”, “아까 그 지점 말고” | 분류→추출→대상 식당→원장→대안→상태·안내까지 같은 case_id로 추적 |
| 3 | 실제 가게 정보의 근거 | 영업시간·휴게시간·라스트오더·지점 주소·식이 조건의 공식/확인 가능한 자료와 확인 시각 | 원장·API와 대조, 신선도·충돌·미확인 처리 확인 |
| 4 | RAG 질의별 맞는 규정 | 취소 가능과 환불 확정 구분, 업체 예약 인계, 정책에 답이 없는 질문 | 문서/절 gold 작성 보조, 검색 지표와 최종 안내 근거 평가 |
| 5 | 사람 확인이 필요한 경계 | 예약·고정 일정은 누가 바꾸는가, 안전 신호는 언제 해제 가능한가 | 승인 누락·중복 요청·오래된 결과 적용·다른 여행 접근 회귀 |

[제안] 사람 검토 기록의 최소 칸: `case_id / 입력 / 기대 상태·행동 / 허용 unknown / 근거 원문·시각 / 위험도 / 검토자 / 라벨 버전`. 의견이 갈리면 즉시 다수결 수치로 덮지 말고 불일치와 합의 근거를 보존한다.

## 7. 병합 뒤 우리가 진행할 검증 순서

1. **판 고정**: 최종 커밋, 활성 분기·모드, 프롬프트 버전/해시, 실제 모델, 데이터셋 해시, DB 마이그레이션·corpus 적재량을 기록한다.
2. **기존 계약·회귀 시험**: shadow 비개입, 모델/검색 장애, tenant·trip 격리, 예약·고정 일정 보호, 재요청 멱등성부터 확인한다.
3. **Activity 사람 라벨 재검토**: 새 재난 기준을 먼저 확정한다. 현재 규칙을 동일 세트에서 다시 재고, LLM은 최소 3회 반복·case 단위 CI로 비교한다.
4. **Dining 실제 모델 종단 평가**: 기존 `eval.runners.travel_scenarios --llm live`를 활용하되 모델 연결·외부 소스·원장 스냅숏을 기록한다. 장소·대안 평가와 점수를 섞지 않는다.
5. **RAG 분리 평가**: 실제 활성 임베딩의 적재·차원, 질문→관련 절, 근거→안내를 별도로 확인한다. 여행 데이터만 쓴다.
6. **변경·감시 통합 평가**: 근처 좌표 전달, 코어 감지→정확한 Team 호출, 알림 outbox·중복 억제, 사람 확인 후 한 번만 반영, 장애 후 상태 유지.
7. **도입 판정 자료**: 위험한 확정 오류율, 적절한 보류율, 답변 가능 범위, 반복 일관성, timeout·429·스키마 오류, p50/p95, 호출량·비용을 분자/분모와 조건으로 보고한다.

[주의] Activity `eval.activity_judge.run`은 실제 API·DB 프롬프트를 사용한다. `--no-db`도 shadow sink만 끄며 LLM 호출·감사 기록까지 없는 오프라인 모드가 아니다. 병합 중인 폴더에서 임의로 실행하지 않았다.

[미정] 실제 운영 허용 오류율·시간·비용, Dining Q 도입 임계값, Activity LLM 고객 판정 전환 승인은 이 조사에서 새로 정하지 않았다.

## 8. 이번 작업의 검증과 산출물

- 완료: 고정 Git 소스 비교, 기존 평가 JSON 직접 확인, 채점 코드의 분모·범위 검토, 문서상의 미래 계획과 현재 구현 분리.
- 미실행: 새 pytest/모델/API 평가, 실제 DB 조회·변경, 서버 동작·배포 검증.
- 변경: 이 보고서와 근거 문서, wiki 로그 링크만 추가. 애플리케이션 코드·브랜치·인덱스는 변경하지 않았다.
- 이 문서는 로컬 작성본이다. 커밋·푸시·팀 외부 전송을 수행하지 않았다.

