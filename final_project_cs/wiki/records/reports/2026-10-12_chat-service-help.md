# 고객 채팅 기능 안내 개선

작업 시작 2026-10-11, 기록 2026-10-12(KST). 변경 담당·검토는 매니저 역할 작업자가 겸했다. 독립 검토 완료가 아니다.

## 문제와 원인

고객의 「너가 할 수 있는 게 뭐야?」가 서비스 기능 안내로 연결되지 않았다. 기존 해석 지침은 서비스 질문·정체 질문을 `other`로 분류하도록 명시했으며, `other` 답은 고정 예시와 여행 요약이었다. 정책 검색 범위는 여행 업무 규정 여섯 가지였고 서비스 사용법 코퍼스·전용 읽기 행동이 연결되지 않았다. 모델의 장기 기억 부족으로 이 문제를 확정할 근거는 아니다.

## 변경

- [해석기](../../../app/domains/travel_ops/components/conversation/decision_unit.py)에 `answer_service` 행동을 추가했다. 기능·사용법·지원 범위와 실제 여행 조회·변경을 구분한다. 안내 행동에 일정 대상·변경·사실 조회·후보를 섞으면 거부한다.
- [고객 기능 안내](../../../app/domains/travel_ops/components/conversation/service_help.py)는 인증된 tenant의 `travel_service` 범위만 기존 정책 검색기로 읽는다. 점수·범위·출처·배포된 본문과 일치하는 근거만 사용하고 고객용 문장을 답한다. 검색기 누락·예외·미적재·낮은 점수·오래된 본문은 실패 이유를 기록한다.
- [기능 안내 코퍼스](../../../knowledge/service/manifest.json)는 1문서·5절이다. 일정 조회, 변경·되돌리기, 지연·휴무, 예약·결제 경계를 안내한다. 기존 여행 업무 규정 12문서·130청크 집계와 분리했다. [배포 이미지](../../../deploy/Dockerfile.api)에 코퍼스 파서와 여행·서비스 지식 파일을 포함했다.
- 웹 JSON·SSE·중복 요청·타 고객 접근 거부를 검증했다. 안내 요청은 일정 버전·항목을 바꾸지 않고 출처·확인 시각은 기존 Case 기록에 보존한다. [계약](../../external/service-chat-help.md).

## 검증 증거

| 검증 | 결과 | 범위·한계 |
|---|---|---|
| 신규 단위 시험 | 최종 15/15 통과 | 검색 범위, 고객용 문장, 잘못된 출처·본문·점수, 장애, 지원 경계, 해석 검증. 잘못된 사실 enum 거부 표본 포함 |
| 웹·기존 대화·대상 보호 회귀 | 45/45 통과 | 신규 웹 3개, 기존 대화 및 변경 대상 보호. 실제 DB 사용, 모델·검색 결과는 시험용 대역 |
| 계약·보안 | 312/312 통과 | 기존 이동 개발도구의 escape 문자열 관련 경고 3개. 이번 작업에서 그 파일은 수정하지 않음 |
| 여행 검증 관문 | 26/26 항목 통과, MVP 18/18 | `python -m scripts.verify_dod_v11`. 항목 집계이며 위 시험 수에 더하지 않음. 현재 제품 전체 운영 완료를 뜻하지 않음 |
| 로컬 설정 모델 표본 | 0/9 검증 성공 | 9개 모두 연결 거절. 모델의 의미 해석 오답으로 집계하지 않음 |
| 운영 API 환경의 실제 모델 표본 | 9/9 통과 | 새 지침·스키마를 별도 Python 프로세스에만 전달. 기능 질문 5개와 여행지 조회·변경·규정·인사 각 1개. 배포 코드·고객 데이터는 수정하지 않음. 표본 결과를 전체 정확도로 일반화하지 않음 |
| 새 코퍼스 구조 검사 | 1문서·5절 파싱 | `python -m scripts.ingest_corpus_local --manifest knowledge/service/manifest.json --dry-run`. 지식 적재·임베딩 성공을 뜻하지 않음 |
| 운영 환경 임베딩 표본 준비 | 2회 모두 연결 끊김 | 예정한 질의 4개를 채점하기 전 첫 문서 임베딩에서 `ConnectionResetError`. 새 코퍼스의 실제 검색 품질은 미측정 |
| 운영 검색 함수 읽기 확인 | 새 기능 안내 범위 0건, 기존 기상 범위 RuntimeError | 인증 설정의 tenant와 각 단일 scope·질의만 확인. 다른 범위 전체의 상태로 일반화하지 않음 |

최초 샌드박스 웹 시험은 로컬 DB 연결 권한 때문에 3개가 준비 단계에서 실패했으며, 접속을 허용한 실행에서 위 웹 시험 3개가 통과했다. 실패 시도를 통과로 숨기지 않는다.

단위 15개 + 웹·기존 대화·대상 보호 45개 + 계약·보안 312개 = 372/372 통과다. 이와 별도로 최신 작업 트리에서 신규 단위·웹 17개를 다시 실행해 17/17 통과한 뒤, 잘못된 enum 거부 표본을 추가한 최종 단위 15/15를 확인했다. 반복 실행 건수를 고유 시험 수에 더하지 않았다. 일부 로컬 실행의 종료 정리에서 pyreadline3의 OSError가 출력됐지만 pytest 결과와 프로세스 종료 코드는 성공(0)이었다.

실행 명령:

```text
python -m pytest tests/unit/travel/test_service_help.py tests/e2e/test_service_help_web.py -q
python -m pytest tests/e2e/test_service_help_web.py tests/e2e/test_decision_unit_web.py tests/unit/travel/test_decision_target_guard.py -q --tb=short
python -m pytest tests/contract tests/security -q --tb=short
python -m scripts.verify_dod_v11
python -m scripts.ingest_corpus_local --manifest knowledge/service/manifest.json --dry-run
```

mock 서버 시험(화면 반응): 안 했음 — 이 대화는 고객 웹을 수정하지 않았다. 웹 API의 시험용 모델·검색 대역 사용은 실제 화면 시험이 아니다.

실서버 확인(서버 응답): 했음 — 운영 API 환경에서 실제 해석 모델 9개 표본 및 정책 검색 함수의 두 범위를 읽기 전용 확인했다. 수정 코드가 적용된 서비스 화면의 전체 왕복은 아직 확인하지 않았다.

## 운영 반영과 남은 일

이 작업에서 운영 배포·재시작·지식 적재·커밋·푸시를 실행하지 않았다. 새 코드와 지식 파일을 함께 배포하고, 실제 tenant·임베딩 제공자에 맞춰 서비스 코퍼스를 적재한 뒤 고객 화면에서 「너가 할 수 있는 게 뭐야?」의 전체 왕복을 확인해야 한다. 임베딩 연결·기존 지식 검색 오류는 별도 운영 환경 확인이 필요하다. 연결이 복구되기 전 검색 성공이나 화면 개선 완료를 선언하지 않는다.

일정 후속 질문의 참조·기억·최신 연구 검토는 별도 사용자 요청 대화에서 진행한다. 채팅 최신 위치로 이동하는 버튼은 사용자가 지정한 UI/UX 대화에 전달되었으며 해당 대화에서 화면 시험을 진행 중이다. 이 보고서는 두 작업의 완료를 주장하지 않는다.

## 수정 전 백업

- [해석기·메시지 처리기](../../../app/domains/travel_ops/components/conversation/_backup/2026-10-11_2335_service_help/)
- [웹 API 계약](../../external/rest-endpoints/_backup/2026-10-11_2335_service_help/)
- [API 이미지](../../../deploy/_backup/2026-10-11_2342_service_help/)
- [여행 코퍼스 통합 시험](../../../tests/integration/rag/_backup/2026-10-11_2351_service_help/)

접속 대상이 들어간 로컬 검증 스크립트는 개별 ignore 규칙으로 Git에서 제외했다. 기록 문서에는 실제 접속 주소·계정·SSH 별칭·비밀값을 넣지 않았다.
