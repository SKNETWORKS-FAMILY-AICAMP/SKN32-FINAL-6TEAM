===== DOC: 2026-09-01_VOC가_팀모듈로_흘러간_경위.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 왜 이 문서가 필요한가 | 누락 | 아무도 틀린 판단을 하지 않았는데 낡은 진술의 권위 승격으로 오답이 생겼다는 사후분석 목적이 wiki에 없다 |
| 2. 타임라인 | 일부 | `final_project_cs/wiki/teams/voc-store-manager.md`에 v7 승격 근거 부재와 v7.1 재판정은 있다. `9c11327`, 게이트 부착, `voc: false` 기동 실패를 사양으로 굳힌 과정은 없다 |
| 3. 정확히 어디가 어긋났나 | 누락 | v7.1 정정이 §0·§7-A에만 반영되고 §3-A에는 옛 문장이 남았다는 3행 대조표가 없다 |
| 4. ★ 낡은 진술이 권위를 얻은 경로 | 누락 | `v8 §3-A → CLAUDE.md:67 → handoff/08 → composition.py:44` 승격 경로가 없다 |
| 5. 실제 피해 | 누락 | `voc: false` 기동 실패, 트랜잭션 안 LLM·Case 롤백, Controller 재시도 불가의 3개 피해가 없다 |
| 6. 왜 점검 장치가 못 잡았나 | 누락 | 기존 점검 3항목의 실패 이유, “개정 항목의 절 간 모순” 추가, v7.1 7건 전수검사 결과가 없다 |
| 7. 곁가지 — Team 승격의 근거도 없었다 | 반영 | `final_project_cs/wiki/teams/voc-store-manager.md`의 `왜 재판정했나`·`지금 상태`에 승격 근거 부재, 미구현 LLM 판단, 집계는 코어 1이라는 결론이 있다 |
| 8. 고친 것 | 일부 | `final_project_cs/wiki/teams/voc-store-manager.md`, `wiki/delivery/roles.md`, `final_project_cs/wiki/external/rest-api.md`에 최종 소유 경계는 있다. 계획서 수정 목록과 검증 수치는 없다 |
| 코드 (`final_project_cs`) | 일부 | `wiki/delivery/roles.md`에 호출 시점·실패 처리는 코어 1, 라벨·프롬프트는 모델 담당이라는 분할이 있다. 두 `require_module` 제거, 트랜잭션 밖 이동, handoff 정정은 없다 |
| 계획서 (`program/plan/A-COP_구현계획서_v8.md`) | 누락 | §0·§3-A·§7·§7-A·§8-B·§16 및 루트 `CLAUDE.md`를 갱신했다는 기록이 없다 |
| 검증 | 누락 | `voc: false` 조립 성공, `feedback_job.py`의 호출 0건, 테스트 90건 통과가 없다 |
| 9. 안 고친 것 | 일부 | `wiki/product/scope.md`에 p50 20~34초는 있다. Controller의 트랜잭션 안 LLM과 `voc` 토글 주석 문제는 없다 |
| 10. 재발 방지 | 일부 | `wiki/governance/document-standard.md`의 “CLAUDE.md에 지식을 넣지 않는다”와 `review-policy.md`의 모순 분류 규칙은 있다. 점검 항목 4, v7.1 7건 전수검사, 기준선 동시 수정 규칙은 없다 |
| 관련 문서 | 누락 | 원본이 열거한 계획서 절·점검 캘린더·디버그 리포트·handoff·커밋의 연결 목록이 없다 |

**빠진 것 요약:** 사고의 최종 재판정은 반영됐지만, 권위 승격 경로·실제 피해·점검 실패·수정 검증을 담은 사후분석 본체가 빠졌다.

===== DOC: _평가harness_결함_2026-08-29.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 지금 나오는 숫자 | 일부 | `final_project_cs/wiki/quality/eval-harness.md`와 `wiki/business/infrastructure-cost.md`에 Proposed 216건·p95 32.2초 등은 있다. A/B/Proposed 성공률·평균 점수·비용 합계 표는 의도적으로 빠졌다 |
| 결함 1. Proposed 페널티가 죽은 코드다 | 반영 | `wiki/evaluation/metrics.md`에 `common.py:477`의 값을 `:487`이 덮어쓰며, 수정하면 성공률이 더 내려간다는 결론까지 있다 |
| 결함 2. 채점 기준이 승인 대기를 벌점 처리한다 | 반영 | `wiki/evaluation/metrics.md`에 156건, `wait_for_approval`, `answer: null`, 근거 8건, 채점식과 결론이 있다 |
| 방어지표는 정상이다 | 반영 | `wiki/evaluation/metrics.md`에 681/702, 21/702, 60/60, 21/60, 분모 0이 모두 있다 |
| 해야 할 것 | 일부 | `wiki/evaluation/metrics.md`에 두 결함 수정 후 재측정한다는 순서는 있다. `team_failed` 합성 방식과 승인 fixture 분리·`next_action` 채점안은 없다 |
| 왜 지금 보고서를 안 쓰나 | 반영 | `wiki/evaluation/metrics.md`에 결함 수정·재측정 전에는 A/B 대조값을 싣지 않는다고 명시됐다 |
| 확인하지 못한 것 | 일부 | `wiki/evaluation/judge.md`에 사람 라벨 20건 미측정, `metrics.md`에 승인 대기와 과잉 기권 관계 미확인이 있다. `degraded: true` 156건의 원인 분리와 A군 0.0% 조사는 없다 |

**빠진 것 요약:** 결함 2건과 방어지표는 반영됐지만, 원래 A/B 수치표와 구체적인 수정 절차·잔여 조사 두 항목이 빠졌다.

===== DOC: _컴포저_설계대비_구현대조.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 결론 | 일부 | `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`, `D-CS-004-composer-boundary.md`, `wiki/decisions/D-006-composer-ownership.md`에 토글 전용 v3와 전체 설정 방식의 차이는 있다. 원본의 v3 대비 불일치 판정과 패키징 결합 결론은 그대로 남지 않았다 |
| 2. 대조 시점 | 누락 | HEAD `033ebc2`, `.pytest-tmp/`, 2026-08-20 스냅샷, read-only 대조 조건이 없다 |
| 3. 검증 항목별 판정표 | 일부 | 전체 YAML 저장·정식 loader 검증·allowlist·원자 저장은 `D-CS-003`·`D-CS-004`에 있다. 11개 항목별 판정과 `일치 1 / 불일치 8 / 미구현 1 / 설계에 없음 1`은 없다 |
| 4. 경계 검증 결과 | 일부 | `wiki/decisions/D-006-composer-ownership.md`에 `acop_basement`·`acop_composer` 분리 구조는 있다. basement의 router 인자·JWT 설정·implementation registry 결합과 architecture test 누락은 없다 |
| 5. 토글 계약 범위 검증 결과 | 일부 | `D-CS-003`에 토글 전용 범위가 전체 Composer를 대체하지 못한다는 결론, `D-CS-004`에 전체 loader 검증이 있다. `/validate`·`/apply` payload와 `load_project_config()` 호출 경로는 없다 |
| 6. 설계 문서 갱신 권고 | 일부 | `D-CS-003`에 범위 재정의와 계약 제안은 반영됐다. 고객 wheel 파일 목록 검사, Composer metadata 배제, v2 handoff 폐기·갱신 권고는 없다 |
| 7. 이 대조의 한계 | 누락 | 테스트·wheel build 미실행, UI 저장소 범위 제외, 미커밋 상태, 인코딩 한계가 없다 |
| 출력 요약 | 일부 | 주요 불일치의 일부가 Composer 결정 문서들에 흩어져 있다. 판정 분포와 원본의 중요 불일치 3개 요약은 없다 |

**빠진 것 요약:** Composer 범위에 관한 결론 일부는 후속 결정으로 흡수됐지만, 11항목 실측표·경계 결합 증거·판정 분포와 조사 한계가 빠졌다.

===== DOC: _중앙설정저장소_검토_2026-08-29.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 반영한 곳 | 누락 | DB 설계서·시스템 구성도·화면설계서의 반영 내용과 세 문서 모두 “아직 연결되지 않았다”고 썼다는 표가 없다 |
| 2. 결정 자체는 타당하다 | 반영 | `wiki/decisions/D-007-central-config-store.md`에 로컬 YAML의 두 요구 충돌, 수천 배포에서 central 선택, 수십 개 이하라는 반증 조건이 있다 |
| 3. ★가장 큰 문제 — 자체 호스팅 주장과 충돌한다 | 누락 | 기동마다 중앙 서버 접속, 망분리 불가, 3,000곳 공동 장애라는 세 결과와 자체호스팅 포지셔닝 충돌이 없다 |
| 제안 | 일부 | `wiki/decisions/D-007-central-config-store.md`에 direct·central 두 모드가 있다. 고객사 내부 설정 서비스 형태와 `FileConfigStore`·`PostgresConfigStore` 두 구현 근거는 없다 |
| 4. 구현 상태와 문서 서술이 어긋난다 | 누락 | 당시 저장 계층만 있고 호출부가 없으며 `service.py`가 로컬 YAML을 썼다는 상태는 없다. wiki에는 후속 상태인 “438개 테스트 통과·구현 완료”만 있다 |
| 5. 테스트는 잘 짜였다 | 일부 | `D-007`의 DB row+CAS와 `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md`의 원자 저장은 있다. 통합 테스트 10건과 stale write·동시 writer·없는 배포·임시 파일 4개 검증은 없다 |
| 6. 더 물어야 할 것 | 일부 | `D-007`에 `deployment_id`, append-only DB, HA·백업·인증·방화벽 미정은 있다. 감사 로그 분리, ID 발급자, 3,000곳 설정 유출, 스프린트 에픽 부재는 없다 |
| 7. 정리 | 일부 | `D-007`에 진단·방향·규모 조건은 있다. 자체호스팅 충돌, 당시 미연결 상태, 테스트 10건, 일정 미반영이라는 원본 요약은 없다 |

**빠진 것 요약:** 중앙 저장소의 결정 논리는 반영됐지만, 자체호스팅과의 충돌 및 2026-08-29 당시 미연결 구현 상태가 통째로 빠졌다.

===== DOC: _3차_인용검증_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 왜 이 문서가 필요한가 | 일부 | `wiki/decisions/D-005-write-gate.md`와 `product/problem.md`에 근거 없는 판단을 코드로 차단한다는 목표가 있다. 잘못된 보장 안내가 청구·포기 손실을 만든다는 원래 사례는 없다 |
| 1. 팀 안에서 제기된 문제 인식 — 맞다 | 누락 | `answer_question.py`에서 근거 0건만 차단하고 1건 이상이면 LLM을 호출한다는 코드와 위험 진단이 없다 |
| 2. 다만 "프롬프트가 유일한 방어선"이라는 결론에는 동의하지 않는다 | 반영 | `wiki/decisions/D-005-write-gate.md`에 프롬프트는 약한 층이며 코드 대조를 통과해야 한다는 원칙이 명시됐다 |
| 핵심 아이디어 | 일부 | `D-005-write-gate.md`와 `final_project_cs/wiki/actions/evidence-check.md`에 evidence ID·source digest 대조는 있다. LLM 본문에서 조항 번호를 추출해 실제 조항 집합과 맞추는 절차는 없다 |
| 지금 왜 못 막나 | 누락 | `_citations()`가 검색 결과를 그대로 붙여 허위 답을 더 그럴듯하게 만든다는 구현 결함이 없다 |
| 3. 방어를 층으로 겹친다 | 일부 | `D-005-write-gate.md`에 입력·지시·출력·실행 직전·감사 7층이 있다. 빈 응답 금지와 답변별 인용 로그 등 원본의 답변 전용 행은 없다 |
| 3-1. 구조화 출력 | 일부 | `D-005-write-gate.md`와 Team 계약에 구조화 스키마 강제가 있다. `verdict`, `cited_clauses`, `reason`, `applied_terms` 구조와 cited clause 필수 규칙은 없다 |
| 3-2. 인용 검증 | 일부 | `final_project_cs/wiki/actions/evidence-check.md`에 근거 식별자 대조와 불일치 시 차단·감사가 있다. `qualified_no` 집합 대조와 본문 `제N조` 경고 규칙은 없다 |
| 3-3. 판정에 쓸 수 없는 데이터는 애초에 넣지 않는다 | 일부 | `D-005-write-gate.md`에 `parse_status != ok`를 `ContextPack.degraded=true` 자동 실행 금지로 옮긴 대응이 있다. `date_confidence == unknown`과 `page_fallback` 제외는 없다 |
| 4. 모델팀에 전할 것 — 관점을 바꿔야 한다 | 반영 | `D-005-write-gate.md`에 “착한 모델을 고르는 게 아니라 검사에 걸리는 모델을 만든다”는 결론이 그대로 있다 |
| 모델 평가 지표 제안 | 반영 | `wiki/evaluation/metrics.md`에 근거 정합률·초과율·적절한 기권율·과잉 기권율·스키마 준수율의 5개 산식이 있다 |
| 5. 지금 구현 상태 요약 | 누락 | `nodes/judge_coverage.py` 부재, `answer_question.py`의 기존 방어 4종, 인용 검증·구조화 출력 부재가 없다 |
| 6. 할 일 | 일부 | `D-005-write-gate.md`, `actions/evidence-check.md`, `evaluation/metrics.md`에 구조화 검증·근거 대조·평가 지표의 후속 형태는 있다. `AnswerResult` 필드 추가와 `qualified_no`, `parse_status`·`date_confidence` 작업은 없다 |

**빠진 것 요약:** 방어 원칙과 평가 지표는 A-COP의 Action 검증으로 옮겨졌지만, `answer_question.py`의 구체 결함과 조항 단위 인용 검증 계약은 빠졌다.

===== DOC: _법령원문_2026-08-20.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 조회 방법 (재현 가능) | 누락 | law.go.kr 검색·서비스 API 경로, MST 획득 순서와 `OC` 취급 방법이 없다 |
| 1. 전자상거래 등에서의 소비자보호에 관한 법률 — 제17조(청약철회등) | 일부 | `final_project_cs/wiki/context/rag-retrieval.md`에 7일, 3개월·30일, 제한 6범주가 있다. 법령ID `009318`, MST `282793`, 제1~6항 전문과 Team 미반영 예외 상세는 없다 |
| 2. 개인정보 보호법 — 제2조(정의), 제15조(수집·이용), 제17조(제공) | 일부 | `final_project_cs/wiki/external/auth-boundary.md`와 `teams/response-review-design.md`에 PII 마스킹·결합 재식별 위험·정규식 검사가 있다. 법령ID `011357`, MST `270351`, 세 조문과 REV의 법적 근거 연결은 없다 |
| 3. 남은 것 (수동 조회로는 안 됨 — API 키·파이프라인 필요) | 일부 | `context/rag-retrieval.md`에 청약철회 제한 6범주가 들어갔다. 소비자24 5~10건 수집, 타 기관 API, 확보했으나 Team 코드에 미반영된 조항 목록은 없다 |

**빠진 것 요약:** 일부 법정 기간과 제한 범주는 코퍼스 문서에 반영됐지만, 재현 가능한 조회법·법령 식별자·조문 전문과 개인정보 법적 근거가 빠졌다.

===== DOC: _분쟁조정사례_2026-08-20.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 수집 방법 | 누락 | 소비자24 공개 게시판, “청약철회” 336건 중 4건 선별, `trublMdatCaseSn` 직접 접근 방법이 없다 |
| 사례 1. 물품 하자로 인한 환불 청구 (trublMdatCaseSn=13117) | 일부 | `final_project_cs/wiki/context/rag-retrieval.md`에 단순변심 배송비와 3영업일 환급은 있다. 사건번호·하자 판단과 환급 지연의 쟁점 분리, 원본의 연 24% 수치는 없다 |
| 사례 2. 구두 및 레깅스 배송 지연으로 인한 구입가 환급 요구 (trublMdatCaseSn=12290) | 일부 | `context/rag-retrieval.md`에 불리한 “반품 금지” 특약 무효와 3영업일 환급이 있다. 고정 디자인·사이즈 선택은 개별생산이 아니라는 판단과 돌잔치 배송 지연 적용은 없다 |
| 사례 3. 인터넷 쇼핑몰에서 청약철회한 의류대금 환급 요구 (trublMdatCaseSn=11916) | 일부 | `context/rag-retrieval.md`에 청약철회 제한 6범주는 있다. 반복 청약철회 이력이 거절 근거가 아니라는 결론, 판매자의 훼손 입증 책임, VOC 반복 감지의 사용 제한은 없다 |
| 사례 4. 해외구매대행 물품 하자로 인한 환불요청 (trublMdatCaseSn=13182) | 일부 | `wiki/decisions/D-001-payment-ownership.md`에 실결제액을 환불 기준으로 삼는 방향, `final_project_cs/wiki/teams/fulfillment-logistics.md`에 해외구매대행 Live 연동은 Mock이라는 서술이 있다. 배송비 공제 조건과 위자료 불인정 판단은 없다 |
| 남은 것 | 누락 | 4/336 비대표 표본, 원문 재배포 정책 미확인, 학습 데이터 사용 금지, 결제 오류·개인정보·분실 사례 미수집이 없다 |

**빠진 것 요약:** 일반 법정 기준 일부만 반영됐고, 네 사건의 사건번호·고유 판단·Team별 적용 결론과 표본 한계는 대부분 빠졌다.

===== DOC: dev2_브리핑_교차검증_2026-08-28.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 계약·기준선 | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`에 `outcome`, `decisions[]`, `handoff_capability` 계약이 있고 `return-refund.md`·`wiki/evaluation/finetuning.md`에 Return Mock·평가 배분 0이 있다. `verdict` 매핑 규칙과 LOCAL 승격 조건은 없다 |
| 숫자 | 누락 | 해외 39건의 세 분모별 비율, 10,527/57,860=18.19%, F 8/322=2.48%, D5 1/1,704=0.0587%가 없다 |
| 안건별 판정 | 일부 | `final_project_cs/wiki/teams/fulfillment-logistics.md`에 국외 배송·해외구매대행은 Mock이라는 결론은 있다. 판매자취소 이관, warranty gate, D5 fixture, ETA 3층, 기록 재생 시연 등 나머지 구체 판정은 없다 |
| 확인이 더 필요한 것 | 일부 | `final_project_cs/wiki/external/auth-boundary.md`에 마스킹·join key 분리·최소 증거·비식별 fixture와 hash가 있다. 품질보증 관련 공식 법령과 39건의 in-scope 분모 미확인은 없다 |

**빠진 것 요약:** 공통 계약과 개인정보 조치는 일부 반영됐지만, 검산 수치 전부와 7개 안건의 대부분이 빠졌다.

===== DOC: _기술스택_공식문서_2026-08-17.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 링크를 걸지 않은 항목과 이유 | 누락 | `wiki/architecture/tech-stack.md`에 기술 분류는 있으나 RAG·GraphRAG, API Key+Scope, harness, bootstrap·McNemar, Registry·Adapter에 링크를 걸지 않은 이유 표가 없다 |

**빠진 것 요약:** 링크 제외 5항목과 각각의 이유가 전부 빠졌다.

===== DOC: _codex_추적화면_교차검증_2026-09-01.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. monkey patch로 데이터 추출 (첫 번째) | 누락 | `steps.py`·`sheet_data.py`의 import 순서 의존, 전역 함수 변경, `sys.path` 충돌과 단일 `Step` 데이터 모델 제안이 없다 |
| 2. `trace_data.py`와 `steps.py`의 중복 12단계 (첫 번째) | 누락 | 두 배열의 인덱스 결합, 4단계 제목 불일치, 색 필드 무검사와 안정 ID·제목·순서 검증안이 없다 |
| 3. 줄 번호 기반 `cut()` (첫 번째) | 누락 | 시작 줄만 검사하는 절단 결함과 Python AST·SQL 종료 세미콜론·YAML 키 경로 대안이 없다 |
| 4. 2.0MB 단일 HTML (첫 번째) | 누락 | PNG 7장 1.48MiB, base64 1.97MiB, RGBA 약 80MiB와 lazy loading·크기 지정·CSP 조건이 없다 |
| 5. 접근성·사용성 (첫 번째) | 누락 | 전역 키보드 차단, 모달 ARIA·초점 관리·live region·reduced motion·대비·모바일 결함과 개선안이 없다 |
| 6. 그 밖에 실제로 깨질 지점 (첫 번째) | 누락 | 자동재생 1단계 건너뜀, 팝업 상태 불일치, `</script>` 조기 종료, 속성 따옴표, 산출물 신선도·원자 교체·폰트 경로 결함이 없다 |
| 가장 위험한 것 3개 (첫 번째) | 누락 | 배열 정체성 미검증, import 순서 의존 monkey patch, 줄 절단·신선도 미검사의 우선순위가 없다 |
| 1. monkey patch로 데이터 추출 (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 2. `trace_data.py`와 `steps.py`의 중복 12단계 (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 3. 줄 번호 기반 `cut()` (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 4. 2.0MB 단일 HTML (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 5. 접근성·사용성 (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 6. 그 밖에 실제로 깨질 지점 (중복본) | 누락 | 동일 내용이 wiki에 없다 |
| 가장 위험한 것 3개 (중복본) | 누락 | 동일 내용이 wiki에 없다 |

**빠진 것 요약:** 추적 화면 교차검증의 7개 절이 중복본을 포함해 전부 wiki에 없다.

===== 전체 =====

| 원본 | 절 수 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| 2026-09-01_VOC가_팀모듈로_흘러간_경위.md | 14 | 1 | 5 | 8 |
| _평가harness_결함_2026-08-29.md | 7 | 4 | 3 | 0 |
| _컴포저_설계대비_구현대조.md | 8 | 0 | 6 | 2 |
| _중앙설정저장소_검토_2026-08-29.md | 8 | 1 | 4 | 3 |
| _3차_인용검증_설계.md | 13 | 3 | 7 | 3 |
| _법령원문_2026-08-20.md | 4 | 0 | 3 | 1 |
| _분쟁조정사례_2026-08-20.md | 6 | 0 | 4 | 2 |
| dev2_브리핑_교차검증_2026-08-28.md | 4 | 0 | 3 | 1 |
| _기술스택_공식문서_2026-08-17.md | 1 | 0 | 0 | 1 |
| _codex_추적화면_교차검증_2026-09-01.md | 14 | 0 | 0 | 14 |
| **합계** | **79** | **9** | **35** | **35** |