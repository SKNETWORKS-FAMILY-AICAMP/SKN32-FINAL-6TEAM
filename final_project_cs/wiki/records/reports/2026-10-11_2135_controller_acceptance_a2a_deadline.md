---
type: report
title: Controller 인수 근거와 A2A 마감·취소 경합 수정
status: verified-local
domain: neutral
---

# Controller 인수 근거와 A2A 마감·취소 경합 수정

팀 재활성화와 실행 중 교체에서도 실제 일정은 한 번만 변경됐습니다. 원격 실행의 마감 시각과 Controller 제한시간이 겹쳐 취소가 생략되는 결함은 계약과 코드를 고친 뒤 동일 조건 30건에서 재발하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 인수 조건과 시험·로그 연결 | 확인 | 24/24 = 100% |
| 수정 전 원격 취소 누락 재현 | 확인 | 6/6 = 100% |
| 수정 후 마감·취소 반복 확인 | 통과 | 30/30 = 100% |
| 관련 회귀·추가 읽기 경계 | 통과 | 178/178 = 100% |

분모 24는 수명 관리 계획의 인수 시나리오 수입니다. 178은 아래 두 실행 로그에 나타난 고유 pytest 시험 수(168+10)입니다. 반복 확인 30건은 같은 6조건을 5회 실행한 별도 값으로 178에 더하지 않습니다. 모든 인수 조건이 통과해도 제품 전체 무결함을 보장하지 않습니다.

## 실제 일정·상태 보존

- 고객 답변 대기 상태에서 담당을 끄면 Case·이벤트·run·토큰이 변하지 않았습니다. 같은 답변으로 담당을 다시 켠 뒤 재개하고 재전송해도 실제 일정 버전은 1→2 한 번만 증가하고 점심 시각은 30분 한 번만 이동했습니다. Core 적용 장부의 succeeded도 1행입니다.
- 요청을 시작한 뒤 비활성 판을 게시하면 실행 중 요청은 옛 Team·계산 판으로 종료하고 새 요청은 거절됐습니다. 같은 요청 재전송은 멱등 응답이며 실제 일정 변경은 1회입니다. `controller_call_finished` 로그의 종료 revision도 옛 판입니다.
- 마지막 담당·capability 관문에서 불가가 발생하면 ROUTED·owner·후보 확보 쓰기를 남기지 않았습니다. 선택 Team의 import·생성 실패는 독립 Team 실행을 막지 않았습니다. 중복 capability·계약 major 불일치는 후보를 거절하고 기존 Controller·계산 표·revision을 보존했습니다.
- 독립 후보 정렬에서 유사도 신호가 없을 때는 실제 거리 순서로 정렬하고 생략 사유를 기록했습니다. Activity 업무 실행은 여전히 disabled 관문에서 거절돼 독립 정렬이 담당 업무를 대신하지 않았습니다.

## A2A 마감과 정리 예산

수정 전에는 Controller가 Team 실행을 기다리는 시간과 A2A가 task deadline을 지키는 시간이 같았습니다. A2A가 poll을 끝내고 취소할 시점에 바깥 제한시간이 먼저 실행기를 취소했습니다. 실제 Controller 재개와 로컬 개발 DB를 사용한 6조건에서 제출은 6회, 취소는 0회였습니다.

먼저 [가용성 계약](../../teams/team-contract/plugin-availability.md)에 정리 예산을 명시했습니다. A2A 실행기는 `cleanup_budget_seconds`로 기존 취소 제한시간을 알리고, Controller는 `남은 task deadline + 정리 예산 + team_cleanup_grace_seconds`를 바깥 제한시간으로 사용합니다. 기본 grace 0.1초는 이벤트 루프 정리와 결과 반환을 위한 운영 정책값으로 외부 SLA 실측이 아닙니다. 업무 자체의 deadline은 유지합니다. 선택 속성이 없는 Local 실행기의 기존 제한시간도 유지합니다. 검토 Team은 같은 실행 helper를 사용합니다.

음수·NaN·무한대·문자 예산은 실행 함수를 부르기 전에 거절했습니다. 실행 코루틴을 먼저 만들지 않으므로 잘못된 계약이 미await 코루틴을 남기지 않습니다.

반복 조건은 task deadline 0.06·0.08·0.1초와 정상 취소·멈춘 취소의 조합입니다. 정상 취소는 0.02초를 기다리고, 시험의 취소 예산은 0.25초로 두어 Windows 이벤트 루프 지연과 기능 검증을 구분했습니다. 5회 반복에서 정상 취소 15/15회가 끝났고 멈춘 취소 15/15회는 제한·실패 로그를 남겼습니다. 30/30회 모두 Core에 `remote_deadline_exceeded` 원인을 보존했습니다. 고객의 명시적 취소는 기존 CancelledError 전파를 유지합니다.

## 실행 근거와 보존

- [인수 매핑 JSON](../evidence/2026-10-11_1936_team_plugin_implementation/acceptance-mapping.json): 24조건별 현행 시험 이름·로그 행·로그 SHA256.
- [관련 회귀 168/168](../evidence/2026-10-11_1936_team_plugin_implementation/acceptance-execution-v2.log), [읽기 경계 10/10](../evidence/2026-10-11_1936_team_plugin_implementation/acceptance-read-boundaries-v1.log): 깨끗한 하위 프로세스에서 구현 import 시도·적재 0회도 확인했습니다.
- [마감 수정 전](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-before.log), [마감 수정 후](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-after-v2.log), [반복 1](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-repeat-1.log)·[2](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-repeat-2.log)·[3](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-repeat-3.log)·[4](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-repeat-4.log)·[5](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-repeat-5.log).
- [수정 코드·계약·매핑 해시](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-source-hashes.json), [린트](../evidence/2026-10-11_1936_team_plugin_implementation/controller-a2a-deadline-lint.log): 코드 3/3개 통과.
- [코드 수정 전 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_2130_a2a_controller_deadline/), [계약 수정 전 백업](../../teams/team-contract/_backup/2026-10-11_2130_a2a_deadline/), [시험 수정 전 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_acceptance/), [매핑 이전 판](../evidence/2026-10-11_1936_team_plugin_implementation/_backup/2026-10-11_2135_acceptance/).

mock 서버 시험(화면 반응): 안 했음. Python 계약·Controller 시험과 비동기 transport 대역을 사용했습니다.

실서버 확인(서버 응답): 로컬 개발 DB에 실제 Case·일정·적용 장부를 저장하고 조회했습니다. 실제 A2A 원격 기계 취소·x600 서버의 cs 프로젝트 서버 확인은 안 했으며 운영 배포·커밋·푸시는 수행하지 않았습니다.

읽기 경계 시험은 종료 시 pyreadline3 소멸자의 Windows 핸들 경고를 출력했으나 pytest 10/10과 프로세스 종료코드 0을 확인했습니다. 전체 회귀의 MCP 라이브러리 사용중단 경고 1건도 기능 실패와 구분합니다.
