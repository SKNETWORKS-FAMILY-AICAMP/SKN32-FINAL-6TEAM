---
type: contract
title: 개인 AI 여행 권한 OAuth
description: 브라우저 동의로 개인 AI에 본인 여행의 읽기·변경을 위임하는 인증 경계
status: draft
domain: travel
---

# 개인 AI 여행 권한 OAuth

D-CS-012와 W04 B안의 구현 계약입니다. 웹 소셜 로그인은 회원을 확인하고, 이 OAuth는 그 회원의 여행 작업을 개인 AI에 위임합니다. 공유 계획 링크는 읽기 전용이며 OAuth 자격으로 쓰지 않습니다.

## 경로와 권한

- `/.well-known/oauth-protected-resource/mcp` 및 끝 슬래시 경로: 자원과 인가 발급자 안내. `/.well-known/oauth-authorization-server/oauth`: 발급자 안내.
- `/oauth/authorize`: 사전 등록된 공개 클라이언트, 명시적 redirect URI, state, S256 PKCE, 자원, scope를 확인한 뒤 인증 전용 동의 화면으로 이동합니다. 동적 등록은 제공하지 않습니다.
- `/oauth/consent`: 브라우저 쿠키 로그인 회원만 허용합니다. 로그인 전에는 기존 웹의 `/mypage#accounts`를 새 탭으로 여는 링크를 제공합니다. 로그인 후 원래 동의 화면에서 다시 확인합니다. POST는 Origin와 세션 CSRF를 검사합니다. 요청한 권한을 보여 주고 허용 또는 취소합니다. 외부 클라이언트 이름을 검증된 업체 신원으로 표현하지 않습니다.
- `/oauth/token`: SDK가 코드·클라이언트·redirect·PKCE를 검사합니다. 추가 경계가 자원 필수·일치, PKCE 길이·문자, 중복 인자를 검사합니다. 코드와 갱신 교환은 DB 잠금 안에서 한 번만 성공합니다.
- `/oauth/revoke`: SDK의 클라이언트 확인 뒤 해당 동의와 토큰 묶음을 폐기합니다. 브라우저는 `/v1/web/agent-connections`에서 목록과 개별 폐기를 사용합니다.

`travel:read`는 여행 조회와 부수효과 없는 이동 판정만 허용합니다. `travel:write`는 일정 변경 권한이며 MCP 쓰기 스위치도 켜져 있어야 합니다. 두 권한 모두 계정 관리·연락처·새 키 발급·항로 지킴이 권한 변경을 허용하지 않습니다. 목록과 여행 상세는 기존 웹 API의 tenant/customer 소유 검사로 본인 여행만 열립니다. OAuth 자원은 공개 기준 주소의 `/mcp/`이며 REST에 직접 보낸 OAuth 토큰은 거절합니다. MCP는 검증된 사용자 문맥을 같은 프로세스의 API로 전달합니다.

## 저장과 수명

인증 저장은 `901_personal_ai_oauth.sql`의 tenant별 레코드입니다. 무작위 코드·access·refresh·동의 요청 표는 SHA-256 해시만 저장합니다. 브라우저 동의는 로그인 세션과 연결되고 다른 세션은 처리하지 못합니다. 고객 삭제는 종속 레코드를 삭제합니다. 소셜 연결을 모두 해제하면 기존 동의도 폐기하며, 토큰 검증 때도 현재 회원 여부를 확인합니다.

전용 [정책 파일](../../config/personal-ai-oauth.json)과 환경변수 `ACOP_PERSONAL_AI_OAUTH_*`: 코드 120초, 동의 대기 600초, access 900초, refresh 유휴 30일·절대 90일. 모두 초기 정책값이며 실측 최적값 주장이 아닙니다. 갱신 때 access/refresh를 함께 교체하고 옛 refresh 재사용은 옛 토큰의 만료 여부와 관계없이 살아 있는 동의 전체를 폐기합니다. 새 access 발급이 동의의 절대 만료를 연장하지 않습니다. 사전 등록은 배포자가 별도 수행하며 고객 입력으로 등록하지 않습니다. 비밀이 필요한 confidential client는 이번 지원 범위 밖입니다.

인가 코드·refresh·access는 회원·클라이언트·허용 권한·대상 자원을 동의와 대조합니다. DB의 고객 외래 키도 tenant와 고객을 함께 묶습니다. 리디렉션은 루프백의 포트까지 사전 등록 값과 정확히 일치해야 합니다. 임의 포트를 쓰는 외부 CLI와의 호환은 별도 확인이 필요합니다. 폐기·만료 레코드의 정기 정리와 운영 부하 시험은 이번 구현에서 수행하지 않았습니다.

인증 화면은 API 공개 주소에서 제공합니다. 기존 CSRF 검사는 고객 웹 허용 출처와 설정된 API 공개 주소의 출처를 허용하고, 다른 출처는 거절합니다. 연결 관리 화면은 이름·상태 검색과 페이지 이동을 제공하고 폐기 전에 클라이언트명을 확인합니다. 외부 클라이언트 사전 등록·운영 반영 조건은 [통합 인계](../../../program/research/baseline_completion_2026-10-12/tasks/auth/integration-request.md)에 있습니다.

## 공식 근거와 검증 상태

[MCP 인증 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)은 자원 발견·Bearer·대상 자원 검증을 요구합니다. [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html)은 PKCE와 갱신 토큰 재사용 방어, [RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html)은 대상 자원 결합 근거입니다. SDK의 프로토콜 처리와 별도로 저장·동의·원자적 교환을 구현합니다. 실제 외부 개인 AI 연결과 운영 적용은 로컬 격리 시험과 구분해 기록합니다.
