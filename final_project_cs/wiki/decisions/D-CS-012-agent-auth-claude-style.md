---
type: decision
title: 에이전트 연결은 클로드 · 클로드 코드 방식(브라우저 로그인 허용) — 먼저 에이전트 키 분리, 다음 OAuth
description: 개인 AI 에이전트(MCP · API) 인증을 쿠키 로그인 위에 얹는다. 1단계 이름 · 만료 · 개별 폐기 · 권한 범위가 있는 에이전트 키, 2단계 MCP OAuth(인가 코드 + PKCE). 계정 관리는 브라우저 로그인에서만
status: draft
tags: [agent, api, security]
owners: [human:미배정]
domain: travel
decision_status: accepted
implementation_status: implemented
validation_status: partial
---

# D-CS-012 에이전트 연결은 클로드 · 클로드 코드 방식 — 먼저 에이전트 키 분리, 다음 OAuth

`[결정 2026-10-04 사용자]` 「에이전트용 인증은 클로드 · 클로드 CLI 방식을 그대로 적용한다. 우리가 기반이 없는 것도 아니고 코덱스와 논의하며 진행한다」. 앞 결정 [D-CS-011](D-CS-011-browser-session-cookie.md)(브라우저는 HttpOnly 쿠키)의 2단계다. 설계는 코덱스(웹 검색 · 코드 읽기 전용)와 상담했다.

## 현재 채택 범위 — 2026-10-11 W04 B안

[사용자 확정] 개인 AI를 로그인·동의로 연결하는 OAuth까지 이번 구현 범위에 포함합니다. “OAuth는 다음 단계로 둔다”는 이전 검토안은 대체합니다. 고객이 허용한 읽기·변경 권한, 본인 여행 소유 관계, 토큰 만료·폐기를 검사해야 합니다. 웹 소셜 로그인과 개인 AI OAuth는 같은 완료 항목이 아닙니다.

선택·wiki 반영은 완료했습니다. **2026-10-12 로컬 작업 트리에 OAuth·동의·권한을 구현하고 격리 PostgreSQL·SDK MCP로 검증했습니다. 실제 외부 개인 AI 연결과 x600 서버 배포는 확인하지 않았습니다.** 현재 세부 계약은 [개인 AI OAuth](../external/personal-ai-oauth.md), 실행 범위와 남은 한계는 [구현 보고](../records/reports/2026-10-12_personal-ai-oauth.md)에 있습니다. [MCP 공식 인증 사양](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)을 기준으로 코드 교환·PKCE·대상 자원 검증을 확인합니다.

예: 개인 AI 연결 때 여행 읽기만 허용하면 일정 조회만 가능합니다. 일정 변경을 허용해도 예약·결제 승인을 우회하지 않습니다. 연결 해제·토큰 만료 뒤에는 접근을 거부합니다.

[선택·반영·남은 구현 대조](../records/reports/2026-10-11_review-comments-v7.md).

## 세 개의 문 — 쿠키는 브라우저 전용이다

| 문 | 누가 | 인증 | 볼 수 있는 것 | 상태 |
|---|---|---|---|---|
| 웹 | 사람의 브라우저 | HttpOnly 쿠키 + CSRF | 본인 여행 | **끝**(D-CS-011) |
| 개인 AI(MCP · 사용자 API) | 사용자의 에이전트 | **에이전트 키**(1단계) · **OAuth 토큰**(2단계, MCP 전용) | **본인 여행의 작업만** | 로컬 구현·격리 검증, 외부 연결·배포 미확인 |
| 서버 연동 | 업체 · 외부 시스템 | 서버 scope 키(`require_scope`) | 테넌트 | 이미 있음 |

- 쿠키는 브라우저가 자동으로 붙이는 값이라 에이전트(브라우저가 아닌 프로그램)가 쓸 수 없다. 에이전트는 요청마다 명시적으로 키/토큰을 보낸다. 한 요청에 쿠키와 키가 같이 오면 400(구현돼 있다).
- **계정 관리는 에이전트가 못 한다** — 구글 연동 · 해제, 새 키 만들기, 연락처(웹훅) 바꾸기, 로그인 · 로그아웃은 **쿠키 로그인(브라우저)에서만**.
- 에이전트 키는 **로그인한 사용자(회원)만** 만든다. 게스트는 없다(D-CS-011).

## 클로드 · 코덱스는 어떻게 하나(조사 2026-10-04, 코덱스 웹 검색)

- 최신 MCP 인증 사양 [2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization): `401 + WWW-Authenticate(resource_metadata)` → 보호 자원 메타데이터(RFC 9728) → 인증 서버 메타데이터(RFC 8414) → 클라이언트 식별 → **로그인 · 허용** → 인가 코드 + PKCE(S256) → 콜백 → 토큰 교환 · 갱신 → 매 요청 `Authorization: Bearer`. 대상 자원(RFC 8707 `resource`)은 인가 · 토큰 요청에 필수이고 서버가 검증한다.
- **동적 클라이언트 등록(DCR, RFC 7591)은 필수가 아니다**(최신판에서는 호환용으로 폐기 예정) — 클라이언트 ID 메타데이터 문서(CIMD)나 **사전 등록**도 된다. 우리는 **사전 등록**으로 시작하고 `/oauth/register` 는 끈다.
- claude.ai: 연결할 때 OAuth, 콜백 `https://claude.ai/api/mcp/auth_callback`. Claude Code: `/mcp` 또는 `claude mcp login <이름>`, 로컬 루프백. Codex CLI: `codex mcp login <이름>`, 기본 `127.0.0.1` 루프백. 외부 MCP 서버용 기기 코드 흐름 지원은 **못 찾음**. `claude setup-token`(1년 토큰)은 모델 호출용이라 우리 인증을 대신하지 않는다.
- 우리 서버에 설치된 `mcp 1.28.1` 에 `OAuthAuthorizationServerProvider` · `AuthSettings` · `TokenVerifier` · PKCE · 메타데이터 · 폐기 경로가 있다(코드와 `pip show` 로 확인) → **SDK 를 쓴다**(Authlib 추가나 직접 구현 안 함). 단 저장 · 동의 · 일회용 코드 · 갱신 순환은 직접 만든다. SDK 의 최신 사양 전체 준수는 `[미확인]`.

## 1단계 — 에이전트 키(지금 구현)

- **무엇**: 로그인한 사용자가 「에이전트 연결」에서 이름을 붙여 키를 만든다. 형식 `acop_a_…`(무작위 256비트), **서버엔 해시만**, 만들 때 **한 번만** 보여 준다. 만료 **기본 90일(최대 90일)**, **개별 폐기**, 마지막 사용 기록.
- **권한 범위**: `read`(GET 만) · `write`(여행 작업 — 쓰기 도구는 `travel.mcp.write_enabled` 스위치도 켜져 있어야 MCP 에 등록된다). 어느 키든 **계정 관리 경로는 못 연다**(`/v1/web/auth/*` · `/v1/web/session*` · `/v1/web/profile*` · `/v1/web/agent-keys*` → 403 `agent_forbidden`).
- **마지막 소셜 연결을 해제하면 에이전트 키를 모두 거둔다**(복구 불가능한 계정에 강한 키만 남지 않게).
- 옛 사용자 키(`acop_u_…`, 브라우저가 쓰던 것)는 그대로 둔다(웹이 쿠키로 옮겨 가는 동안). 에이전트용으로는 새 키를 쓰도록 안내하고, 옛 키를 걷는 것은 나중에 정한다.
- 크기(코덱스 견적): **6~9개 파일 · 3~5인일(예상)**.

## 2단계 — MCP OAuth(로컬 구현, 외부 연결·배포 미확인)

- 경로: `/.well-known/oauth-protected-resource/mcp/` · `/.well-known/oauth-authorization-server/oauth` · `/oauth/{authorize,token,revoke}`. 인가 화면은 **쿠키 로그인 위의 「허용하시겠어요?」 한 화면**.
- 저장: clients(정확한 redirect URI) · codes(해시 · 회원 · client · URI · resource · scope · PKCE · 만료 · 사용 여부) · grants(회원 · client · 허용 scope · 동의/폐기 시각) · tokens(access/refresh 해시 · 순환 family · 폐기).
- scope `travel:read` · `travel:write`(쓰기는 scope **와** `travel.mcp.write_enabled` 둘 다). 수명 제안: 코드 **2분** · access **15분** · refresh **미사용 30일 · 절대 90일**, 갱신마다 순환, 재사용 감지 시 family 폐기(제안값 — 제품 판단).
- 에이전트 키와 OAuth 토큰은 **같은 검증 · 같은 권한 판정**으로 합친다. MCP 는 OAuth 토큰을 내부 웹 API 에 그대로 넘기지 않고 **검증된 사용자 · scope** 를 내부 문맥으로 넘긴다.
- 동의 화면 문구: 「[클라이언트명]이 [로그인 계정]의 본인 여행에 접근하도록 허용하시겠어요?」 + 조회 대상 · 선택한 변경 작업 · 쓰기 활성 여부 · 연결 만료일 · 「계정 연동 · 키 생성 권한 없음」 · 마이페이지에서 폐기 · 허용/취소. 등록 이름을 검증된 업체 신원처럼 보이지 않게 한다.
- 위험과 대비: 리디렉션 URI 는 정확히 일치(루프백 포트만 예외) · 코드에 client/URI/resource/PKCE 를 묶음 · 동의 POST 는 Origin + CSRF · 토큰 경로는 쿠키에 의존하지 않음 · 장차 DCR 은 속도 · 등록 수 제한과 만료 청소([RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html)). 크기 **9~14개 파일 · 6~10인일(예상)**.

## 되돌아보기

- 개인 AI 입구(`/mcp/`)는 지금 `Authorization: Bearer <사용자 키>` 또는 `X-User-Key` 를 받는다. 1단계가 끝나면 새 에이전트 키도 같은 머리말로 받고, 만료 · 폐기 · 권한 범위가 적용된다.
- 지금 사용자 키 인증은 **만료를 검사하지 않고** `rotate` 가 모든 키를 한꺼번에 거둔다 — 에이전트용은 새 표(`web_agent_keys`)에서 따로 다룬다.

## 출처(조사 2026-10-04)

MCP authorization 2026-07-28 · Claude 커넥터 인증 요구사항 · Claude Code MCP 문서 · Codex MCP 문서 · RFC 9728 · RFC 8414 · RFC 7591 · RFC 8707 · RFC 9700.


## 이번 개정의 구현·환경 반영

결정 확정, 로컬 구현·격리 검증, 실제 외부 개인 AI 연결, 운영 반영을 구분합니다. 2026-10-12 인증 담당의 [실행 보고](../records/reports/2026-10-12_personal-ai-oauth.md)를 추가했습니다. 세부 구현은 해당 보고와 [OAuth 계약](../external/personal-ai-oauth.md)이 현재 상태이며, 아래 과거 설계의 루프백 포트 예외는 아직 구현하지 않았습니다.

| 대상 | 상태 | 근거 |
|---|---|---|
| 이번 결정 | 확정 | 2026-10-11 사용자 댓글 |
| 이번 개정 코드·시험 | 로컬 구현·격리 검증 | [담당 보고](../records/reports/2026-10-12_personal-ai-oauth.md) |
| 로컬 업무 DB 반영 | 안 했음 | 인증 담당 전용 PostgreSQL만 사용 |
| 실제 외부 개인 AI 연결 | 안 했음 | 사전 등록·외부 종단 시험 필요 |
| x600 서버의 cs 프로젝트 환경 반영 | 안 했음 | 배포·실행 증거 미확보 |

[상태 표시 읽는 법](../../../wiki/governance/implementation-state.md)을 따릅니다.
