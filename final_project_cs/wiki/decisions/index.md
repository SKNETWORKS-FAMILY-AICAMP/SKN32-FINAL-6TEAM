---
type: guide
title: Decisions (cs)
description: 이 저장소에만 영향을 주는 결정. 여러 저장소에 걸친 것은 중앙 허브에 있다
status: draft
domain: neutral
---

# Decisions (cs)

**이 저장소 안에서 끝나는 결정**만 여기 둔다.

여러 저장소가 당사자인 결정은 [중앙 허브](../../../wiki/decisions/index.md)에 있다.

## 어디에 두는가

| 질문 | 배치 |
|---|---|
| 이 저장소 코드만 바뀌면 되는가 | 여기 |
| 다른 저장소도 고쳐야 하는가 | 중앙 허브 |
| 제품·사업 판단인가 | 중앙 허브 |

## 목록

| ID | 결정 | 상태 | 영향 |
|---|---|---|---|
| [D-CS-001](D-CS-001-composer-ui-removal.md) | `/ui/composer` 폐기 | draft | 인증 경계 |
| [D-CS-002](D-CS-002-finetuned-model-not-adopted.md) | **파인튜닝 모델 채택 안 함** | draft | 평가·자체호스팅 |
| [D-CS-003](D-CS-003-composer-scope.md) | **Composer 범위 — 세 층** | draft | Composer·UI |
| [D-CS-004](D-CS-004-composer-boundary.md) | 모듈 **6종**·Port 3종·Core 9종 경계 `[정정 2026-09-10]` 7종이었다 — `composer_ui` 가 빠졌다 | draft | Composer |
| [D-CS-007](D-CS-007-ui-operator-login.md) | **운영 화면은 로그인한 운영자만** — 화면이 scope 키를 스스로 만들어 `/ui` 에 닿으면 누구나 승인할 수 있었다. 운영자 계정·서명 쿠키·scope 검사, 승인자를 실제 운영자 id 로 | draft | 인증 경계 |
| [D-CS-008](D-CS-008-ops-console-separate-app.md) | **운영자 콘솔은 다른 프로세스·127.0.0.1 만**(1단계) — 운영 화면·관리 API·시나리오를 고객 API 앱에서 빼 운영 앱(8070)으로. 고객 API 는 실제 HTTP·키는 운영 앱 설정에만·폼 위조 방지. 2단계(다른 기계) 전엔 「물리 분리 완료」 아님 | accepted | 인증 경계 |
| [D-CS-013](D-CS-013-domain-folder-layout.md) | **업무 도메인 폴더는 `app/domains/<도메인>/` 아래 다섯 칸** `[2026-10-06 사용자 · Codex 2회차 합의]` — modules · instances · components · ports · entry(+ scenarios). 옛 `app/domain/`(Case 상태 규칙)은 `app/core/case_lifecycle/` 로 옮겨 `domain`·`domains` 겹침을 없앴다. **옮기기 끝(2026-10-06)** — 여행 외부 데이터 소스도 `ports/data_sources` 로. 칸끼리 규칙 시험(팀 → 다른 팀 0) | accepted | 폴더 구조 · 경계 시험 |
| [D-CS-012](D-CS-012-agent-auth-claude-style.md) | **에이전트 연결은 클로드 · 클로드 코드 방식** `[2026-10-04 사용자]` — 쿠키는 브라우저 전용이라 에이전트는 키/토큰. 1단계 이름 · 만료 · 개별 폐기 · 권한 범위가 있는 에이전트 키(회원만 · 계정 관리 못 함), 2단계 MCP OAuth(인가 코드 + PKCE · SDK 사용) | accepted | 에이전트 · MCP |
| [D-CS-011](D-CS-011-browser-session-cookie.md) | **브라우저 세션은 HttpOnly 쿠키 · 로그인 안 한 게스트는 마지막 사용 7일 뒤 삭제** `[2026-10-04 사용자]` — 키를 저장소에 두지 않는다(쿠키보다 나은 방식은 오늘 기준 없다 — DBSC 는 나중에 얹는 보강). 보존 시간 초기값은 재방문 간격 공식으로 구했고(24시간은 54% 만 살린다) 관리 콘솔에서 조절 | accepted | 웹 인증 · 개인정보 |
| [D-CS-010](D-CS-010-google-calls-in-dawn-batch-only.md) | **구글 API 는 새벽 3시 확인 창에 몰아서만** `[2026-09-29 사용자]` — 채팅에서 바로 부르지 않는다. 비는 값(원장·관광공사가 모르는 영업시간)을 메울 방법은 팀이 정한다 | accepted | 외부 소스 · 비용 |
| [D-CS-009](D-CS-009-daytime-closure-detection.md) | **낮에 생기는 임시휴무는 시스템이 찾는다 — 구현 대상** `[2026-09-29 사용자]` — 새벽 확인 한 번 + 고객 신고(09-24 팀 결정)에서 방문 전 시스템 확인·대체로. 확인 소스·횟수는 구현 때 비용 상한 안에서 | accepted | 감시 |
| [D-CS-006](D-CS-006-cancellation-terms-are-structured.md) | **취소 기한·위약금율은 구조화된 표에서 읽는다** — RAG 청크에서 꺼내려던 경로가 구조상 언제나 `None` 이었다. 수치는 `cancellation_terms`(예약→공급자→종류), 문장 근거는 `read.policy` | draft | RAG · 판정 |
| [D-CS-005](D-CS-005-odsay-not-used.md) | **ODsay 를 쓰지 않는다** — 약관이 결과 데이터 저장·가공을 사전 동의 없이 금지하고 무료 한도가 30회/일. 이동 시간은 일정이 들고 오는 경로 정의로 간다 | draft | 외부 소스 |

`[미확보]` `wiki/records/plans/`·`wiki/records/reports/`에서 이관 대상을 더 골라야 한다.

**후보** — 코드만 보면 되돌릴 위험이 있는 것들.

| 후보 | 왜 결정으로 남겨야 하나 |
|---|---|
| 프롬프트 allowlist fail-closed | "왜 없으면 죽게 했지" 하고 완화하기 쉽다 |
| `payment.status`가 DB를 안 읽음 | "구현 안 된 것"으로 오해하기 쉽다 — ★`[2026-09-10]` 커머스 capability 라 여행 코드에는 없다 |
| Context 예산 12,000 고정 | "늘리면 되지" 하고 바꾸기 쉽다 |
| timeout을 재시도 안 함 | "재시도 넣어야지" 하고 추가하기 쉽다 |

**네 개 다 "개선처럼 보이는 되돌리기"다.** 결정 문서가 없으면 에이전트가 특히 잘 되돌린다.

## 번호

`D-CS-<3자리>-<주제>.md`

중앙 허브의 `D-<3자리>`와 구분하려고 `CS`를 넣는다. 번호는 재사용하지 않는다.

## 중앙 허브의 결정 중 이 저장소에 영향을 주는 것

| ID | 결정 | 여기서 무엇이 바뀌나 |
|---|---|---|
| [D-001](../../../wiki/decisions/D-001-payment-ownership.md) | 결제는 쇼핑몰이 소유 | 환불 계산식을 대조 구조로 변경, `read.payment` 추가 — ★`[2026-09-10]` 쇼핑몰 조치안이라 대상이 사라졌다. 결론(결제를 갖지 않는다)은 여행에서도 산다 |
| [D-002](../../../wiki/decisions/D-002-graph-store-gate.md) | Graph Store는 게이트 통과 시에만 | `GraphStorePort` 유지, `SqlGraphAdapter`가 MVP |
| [D-003](../../../wiki/decisions/D-003-message-broker.md) | in-process queue | `MessageBusPort` 유지, 중복 전달·retry 테스트 필요 |
| [D-004](../../../wiki/decisions/D-004-self-hosting-rationale.md) | 자체호스팅은 규제 논거 | 3B 추론 실측 필요 |
| [D-018](../../../wiki/decisions/D-018-decision15-stop-paths.md) | 결정 15 는 층마다 멈춘다 | 기동 조립 거부 · Case 는 `fatal_source_failure` 로 사람 인계 · 스위퍼 exit 1. **고칠 코드는 없다** |

## 관계

- [../../../wiki/decisions/index.md](../../../wiki/decisions/index.md) — 중앙 허브 결정
- [../log.md](../log.md) — 변경 이력
