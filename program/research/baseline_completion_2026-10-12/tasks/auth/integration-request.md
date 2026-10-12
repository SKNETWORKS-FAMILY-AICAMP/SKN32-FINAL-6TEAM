# 개인 AI OAuth 통합 인계

인증 라우터와 MCP 경계는 작업 트리에 접합했습니다. 외부 클라이언트 사전 등록과 운영 환경 반영은 하지 않았습니다.

| 항목 | 현재 상태 | 통합 시 확인 |
|---|---|---|
| 앱 접합 | 기존 `build_auth_router()`에 전용 라우터 포함 | 공용 조립 파일·여행 API 수정 없음 |
| 신규 SQL | [개인 AI 전용 SQL](../../../../../final_project_cs/app/infrastructure/db/migrations/901_personal_ai_oauth.sql) | SQL 안전 담당의 적용 목록·배포 검증에 포함. 업무 DB 적용은 별도 승인 범위 |
| 의존성 | 기존 `mcp[cli]==1.28.1` 사용 | requirements 추가 요청 없음 |
| 설정 | 기존 public base·web origin + [전용 정책](../../../../../final_project_cs/config/personal-ai-oauth.json) | 공개 HTTPS 주소·고객 웹 주소를 환경별 검증 |
| 고객 웹 | 기존 로그인 페이지를 새 탭으로 열고 동의 화면에서 재확인 | 공통 웹 스타일·마이페이지 코드 수정 없음 |
| 외부 개인 AI | 사전 등록된 public client만 허용 | 실제 client ID·이름·정확한 callback 주소 확보 후 아래 배포자 접합부로 등록 |

사전 등록은 HTTP로 노출하지 않습니다. 운영자가 기존 신뢰된 실행 환경에서 `Provider(tenant, public_base).preregister(client_id, name, [redirect_uri], scopes=["travel:read"])`를 호출하는 내부 접합부입니다. 이 문서의 식별자는 변수이며 실제 접속 정보를 기록하지 않습니다. 처음에는 읽기만 등록하고, 일정 변경이 필요할 때 등록 scope에 `travel:write`를 추가하며 MCP 쓰기 스위치도 별도로 검토합니다.

루프백 callback도 포트까지 정확히 등록해야 합니다. CLI가 매번 임의 포트를 쓴다면 고정 callback 설정 또는 후속 호환 구현이 필요합니다. DCR·confidential client·CIMD 자동 등록을 지원한다고 표시하지 않습니다. 해당 기능과 실제 외부 개인 AI 종단 연결은 검증하지 않았습니다.

공용 REST 계약 본문은 충돌을 피하려고 수정하지 않았습니다. 인증 절에 [개인 AI OAuth 계약](../../../../../final_project_cs/wiki/external/personal-ai-oauth.md)을 연결하면 됩니다. 매니저 공통 인증 검토·고객 웹 호출 경계 검토는 아직 독립 완료로 기록하지 않았습니다. 이번 작업자가 구현과 검증을 함께 수행했습니다.

실제 시험 명령·실패 이력·화면 자료는 [담당 보고서](report.md)에 남깁니다. 업무 DB·x600 서버의 cs 프로젝트 앱은 변경하지 않았고 커밋·푸시하지 않았습니다.
