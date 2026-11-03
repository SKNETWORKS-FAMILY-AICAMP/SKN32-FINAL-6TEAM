---
type: report
title: ST4F-746 체크아웃 날짜 후보 독립 검토
status: draft
domain: travel
---

확인 2026-10-29T12:14:49.011648+00:00, Codex. 기존 작성자와 별도 세션에서 후보를 검토했습니다. 담당은 매니저 role-manager, 현재 TeamFlow GET의 assignee `3rd_team_4_be`, 상태 review입니다. 트래커 쓰기·종결은 하지 않았습니다.

판정: 종료 날짜 비교 한 줄은 타당합니다. 기존 키·제목·좌표·시각·유일 대응 조건을 유지하며, review의 end_date가 없을 때 동일 날짜로만 대응하는 보수적 거절도 확인했습니다. 제품 코드 변경·통합·push·배포·운영 쓰기·삭제 0건. 기존 격리 checkout `scratch/teamflow-continue-20261029/repo`를 재사용했습니다. **격리본 필수3/3 = 100%이나 현재 원본과 보안 검사 조건이 달라 통합·릴리스 HOLD를 유지합니다.**

읽은 기준: 원본·격리본 AGENTS/RULE, 루트 wiki/index, 개발 역할, cs web-intakes/web-trips 계약, 원 handoff와 candidate.patch, 현재 coord 77개(원문 스냅숏 coord-private.json). 원 handoff·보고서의 한글은 실제 `?` 바이트로 손상돼 있습니다. 덮어쓰거나 복원한 것으로 주장하지 않고 이 문서로 보완합니다. 현재 제품 이름은 원본 triPilot 지침을 따릅니다. 격리본의 옛 제품 이름은 고치지 않았습니다.

실제 의미와 경위:

- assemble.py:177/268/321-338은 체크인~체크아웃을 하나의 lodging 항목으로 만들고 끝 날짜를 보존합니다. review.py:608/700/761은 end_date를 직렬화하며 832-846은 `체크인 날짜 < 방문 날짜 <= 체크아웃 날짜`의 첫 비숙박 일정에 아침 이동을 만듭니다. itinerary_checks.stay_on도 같은 포함 범위를 씁니다. 숙소를 바꾸는 당일 아침은 전날 묵은 숙소가 출발지입니다.
- 독립 morning 사례는 호텔 10-18 15:00→10-20 10:00, 광장시장 10-20 09:00이며 등록된 이동은 **10-20 08:30 서울 호텔 → 광장시장**입니다. 두 숙소의 각 목적지·10-20/10-22 이동 날짜도 검증했습니다. 이전 후보 시험의 체크인 당일 합성 구간만으로 실제 다일 의미를 입증했다고 보지 않았습니다.
- 실제 DB 경위는 `test_real_db.py`: 접수 원문 → 정식 review → API confirm → PostgreSQL TripStore readback입니다. 장소/이동 제공자는 기존 공개 시험의 명시적 대역이고 실제 LLM·공공 경로 정확도 시험은 아닙니다. 호텔 체크인·체크아웃 원문과 review.end_date, 저장된 N서울타워 목적지·아침 날짜를 확인했습니다. 검토 전용 DB의 그 숙박 행만 SQL로 하루 연장한 뒤 재조회하여 시:분·좌표·키는 같은데 이전 review와 _match가 거절됨을 확인했습니다. 운영 사례·실제 고객 피해를 입증한 것은 아닙니다.

실행 결과:

- 관련 기존 4단위 파일 29건 + 실제 PG/API 기존 등록경로·숙박줄 12건 + 새 의미 시험9건 = **48/50 = 96%**. 기존 시험은 **41/41 = 100%**, 새 의미 시험은 **7/9 = 77.8%**입니다. 실패2는 아래 별도 기존 결함입니다.
- 실제 접수/API/PG 체크아웃 변경 회귀 **1/1 = 100%** 추가 통과. 따라서 두 실행 전체는 **49/51 = 96.1%**이며 실패를 분모에서 빼지 않았습니다.
- 수정 전 _match만 메모리에서 복원한 별도 프로세스 비교: **5/9 = 55.6%**, 체크아웃 날짜 변경·end_date 누락 음성2건과 기존 아침 읽기 실패2건. 후보는 날짜 음성 **2/2 = 100%**를 해소했습니다. 디스크 코드 변조·시험 xfail·스캐너 예외 추가 없음.
- 최종 계약 **367/367 = 100%**. 첫 실행의 Composer import 경로 누락, 두 번째 Git 실행 경로 오류, 세 번째 새 DB의 프롬프트 미등록10건을 로그 그대로 보존했습니다. 기존 sample의 Composer 패키지 경로와 기존 실행 가능한 mingit을 연결하고, 검토 DB에 정식 scripts.register_prompts를 실행한 뒤 전체 계약을 다시 통과시켰습니다. 운영 프롬프트 변경·LLM 호출 없음.
- DoD 26/26 = 100%. 보안 현재 결과: {'tests': 125, 'failures': 0, 'errors': 0, 'skipped': 0}. 환경 오류 로그와 최종 로그를 혼동하지 않습니다.
- 보안 범위 차이: 격리본 HEAD `006268853c0d52c8ff926727f4243230738beb98`, 추적 파일 19185개, 원본 17190개로 서로 다릅니다. 원본 Git은 tools/safe_git.py ls-files로만 조회했습니다. 격리 scanner에는 기존 example.com 공인 주소 예외가 있고 현재 원본 scanner의 ALLOWED_IPS는 비어 있습니다(`scanner-scope.diff`, `scope-comparison.json`). **이번 세션이 예외를 넣은 것은 아니며 두 scanner는 각각 보존했습니다. 125/125 통과는 해당 옛 격리본 조건의 결과이지 현재 원본 보안 HOLD의 해소가 아닙니다.** 원본의 더 엄격한 scanner를 적용한 최신 통합 후보 검증은 남아 있습니다. 원본 파일을 복사해 현재 트리를 고치거나 XML을 고쳐 통과시키지 않았습니다.
- XML/scanner SHA256 **335/335 = 100%** 보존. 원 red/green·tracker evidence와 원문 보고서도 유지했습니다. 새 XML은 이번 독립 디렉터리에만 생성했습니다.

별도 기존 결함(이번 변경 회귀 아님): `recover_for_routes`가 `_moves`의 `('before', id(destination))` 키를 소비하지 않아 from_stay 아침 이동을 읽기 복구하지 않습니다. 새 입력 키 있음·옛 legacy 양쪽 **2/2 = 100%** 재현이며 pre746 메모리 비교에서도 동일합니다. `test_missing_stay_morning_read_recovery` 두 실패를 원본 그대로 보존합니다. 이 결함을 ST4F-746 한 줄 수정으로 고쳤다고 종결하지 않습니다. 승인된 검토 범위에서 수정·새 트래커 등록은 하지 않았습니다.

명령: `python scratch/st4f746-review-20261029/run.py prepare|pg|tests|baseline|real-db|prompts|contract-v4|security-v3|dod`(각 단계 별도 실행). runner·test_semantics.py·test_real_db.py·baseline_plugin.py와 모든 로그/XML은 `scratch/st4f746-review-20261029/`에 있습니다. baseline plugin은 격리 프로세스 메모리의 한 조건만 제거합니다.

공간: 새 checkout/전체 사본 **0개**, 기존 PostgreSQL cluster 재사용, 새 검토 DB 논리 크기 15,957,015 bytes, 자체 증거 554,877 bytes(문서화 직전). 수GB 산출물 없음. inventory 등록0건, disk-inventory.json에 실측 여유를 보존했습니다. 기존 사본은 이미 released인 비장부 사본이며 소유권 설정을 바꾸지 않았습니다. DB·cluster·증거는 보존합니다. 기존 중지돼 있던 cluster는 검토 종료 후 다시 정지하며 데이터는 삭제하지 않습니다.
