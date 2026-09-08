# VISION-04. A2A 생태계 확장

| 항목 | 내용 |
|---|---|
| 상태 | 보류 |
| MVP 포함 | 아니오 |
| 최종 갱신 | 2026-08-13 |

## 1. 무엇인가

Remote Agent 다수 운영, Signed Agent Card 검증, 외부 조직 간 상호운용, OAuth 2.0/OIDC Authorization Server 연계를 도입한다. 현재는 더미 Remote Agent 1개와 API key+scope 경계만 둔다.

## 2. 지금 하지 않는 이유

- 현재 Remote Agent가 1개이고 외부 조직 신뢰 경계를 넘는 상호운용 요구가 확인되지 않았다.
- API key와 scope로 현재 단일 조직·소수 Agent의 호출 권한을 검증할 수 있다.
- 서명 검증·키 회전·조직별 issuer/audience·동의/철회까지 추가하면 인증 운영 범위가 별도 시스템이 된다.

## 3. 도입 트리거 (이 조건이 만족되면 재검토한다)

- 외부 조직 1곳 이상과 실제 연동 요구사항이 승인되면 검토한다.
- Remote Agent가 3개 이상 운영되면 Agent Card 서명·폐기 목록을 검토한다.
- 요청의 신뢰 경계가 2개 이상 조직을 넘는 Case에서 월 10건 이상 발생하면 OAuth 2.0/OIDC를 검토한다.
- API key 회전·폐기 수동 처리 요청이 월 5건 이상이면 중앙 Authorization Server를 검토한다.

## 4. 도입 시 예상 비용

전제: 6인 팀이 AI 코딩 도구를 상시 사용한다. 아래는 인·일이 아니라 실소요 일수(wall-clock)다.
단축률은 이 저장소 실측(2026-08-12, 2시간 21분에 18,390줄·테스트 107건)에 근거한 추정이며 정밀한 값이 아니다.

| 구분 | 내용 | 실소요 | AI 단축 정도 |
|---|---|---:|---|
| 생성 | Signed Agent Card, registry, OAuth 2.0/OIDC 연계 어댑터·스키마·테스트 골격 생성. 병목은 외부 계약을 반영하는 배선이다. | 1.5~2일 | 큼 |
| 검증·통합 | issuer·audience·scope·키 폐기, 조직 경계, unauthorized·재전송과 외부 Agent 호환성을 검증. 병목은 보안 경계와 실패 판정이다. | 2.5~3.5일 | 작음 — 사람이 판단한다 |
| 대기 | 외부 조직 연동, IdP·Authorization Server 설정과 승인 대기. 병목은 외부 조직·인프라 일정이다. | 0.5~1일 | 없음 |
| **합계** | | **4.5~6.5일** | |

병목: 코드 생성보다 외부 조직·IdP 연동과 신뢰 경계 검증이 지배적이다.

## 5. 선행 조건 (이게 먼저 있어야 도입 가능)

- Agent Card schema와 capability/scope 계약
- 조직·issuer·audience·키 회전·폐기 상태의 저장 및 감사 모델
- Remote 호출 trace와 신뢰 경계별 실패 로그
- 외부 조직을 포함한 unauthorized/scope/재전송 테스트

## 6. 폐기 조건 (이 조건이면 이 비전을 버린다)

- 12개월 동안 외부 조직 연동 요구가 0건이고 Remote Agent가 2개 이하이면 생태계 확장을 폐기한다.
- 3개 Agent까지 API key+scope가 키 회전 100%와 접근 차단 100%를 충족하면 Signed Card의 우선순위를 재평가한다.
- 외부 연동 1건이 취소되고 향후 6개월 계약·요구가 0건이면 OAuth Authorization Server 항목을 폐기한다.

## 7. 참고

- `wiki/records/handoff/03_REST_MCP_인터페이스.md`
- `wiki/records/handoff/06_가드레일_수치.md`
- OAuth 2.0/OIDC와 Signed Agent Card는 외부 리서치 인용 후보이며, 도입 전 표준·공식 문서를 확인한다.

## 개정 이력

- 2026-08-13 최초 작성.
- 2026-08-13 비용 산정 방식을 실소요 일수로 변경(실측 근거). 실측 커밋 구간은 2026-08-12 15:14~17:35다.
