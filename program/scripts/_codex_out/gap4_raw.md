===== DOC: A-COP_결제소유_경계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 결정 요약 | 반영 | `decisions/D-001-payment-ownership.md` — 쇼핑몰 소유, A-COP은 설명·대조만, 잔액 변경 금지, 환불 계산식 조치가 모두 있다 |
| 1. 지금 실제 상태 — 코드 근거 | 반영 | `decisions/D-001-payment-ownership.md`의 `지금 상태 — 거의 이미 그렇다` |
| 1-1. 결제 테이블이 없다 `[실측]` | 반영 | `decisions/D-001-payment-ownership.md`, `data/schema/index.md` — 마이그레이션 6개, `payments` 부재, `orders.status` 혼재 |
| 1-2. `payment.status`는 DB를 읽지 않는다 `[실측]` | 반영 | `decisions/D-001-payment-ownership.md`, `teams/procurement-order.md` — 전달받은 값 반환 및 근거 없으면 escalate |
| 1-3. 결제 조회 도구가 없다 `[실측]` | 반영 | `teams/procurement-order.md` — `Payment` 이름과 실제 `allowed_tools` 불일치까지 있다 |
| 1-4. `MockProviderPublisher`는 결제 연동이 아니다 `[실측]` | 반영 | `actions/outbox.md`, `runtime/message-broker.md` — 테스트 더블이며 파일명과 클래스명이 어긋난다는 결론 |
| 1-5. 포인트·캐시·쿠폰은 전혀 없다 `[실측]` | 반영 | `decisions/D-001-payment-ownership.md` |
| 1-6. 코드가 이미 결제를 막고 있다 `[실측]` | 반영 | `decisions/D-001-payment-ownership.md` — Core 금지어 목록과 기존 규칙의 문서화라는 결론 |
| 2. 왜 쇼핑몰이 소유해야 하는가 | 반영 | `decisions/D-001-payment-ownership.md`의 `선택지와 이유` |
| 근거 1 — 우리가 파는 물건이 그게 아니다 | 반영 | `decisions/D-001-payment-ownership.md` — 커머스 결제 시스템으로 제품 성격이 바뀐다는 기각 사유 |
| 근거 2 — 자체 호스팅 목표와 충돌한다 | 반영 | `decisions/D-001-payment-ownership.md` — PCI-DSS·규제 부담 |
| 근거 3 — 이중 장부가 된다 | 반영 | `decisions/D-001-payment-ownership.md` — 업무 상태 단일 원천과 충돌 |
| 근거 4 — Team은 side effect를 실행하지 않는다 | 반영 | `decisions/D-001-payment-ownership.md`, `teams/team-boundary.md` |
| 3. 경계선 | 반영 | `decisions/D-001-payment-ownership.md` — A-COP과 검증 쇼핑몰의 4행 경계표 |
| 4. 포인트·캐시·쿠폰 — 어디까지 | 반영 | `decisions/D-001-payment-ownership.md`의 3단계 |
| 단계 1 — 지금 필요한 것 (10주 안) | 반영 | `read.payment`, 금액 관련 30건·42%가 있다 |
| 단계 2 — 확장 범위 | 반영 | 잔액 조회와 Personal AI/MCP 확장 범위가 있다 |
| 단계 3 — 절대 갖지 않는 것 | 반영 | 적립·차감·소멸·쿠폰 발급 금지 |
| 5. ★ 지금 환불 계산식이 이미 위험하다 | 반영 | `decisions/D-001-payment-ownership.md`, `teams/return-refund.md`, `data/schema/index.md` |
| 문제 | 반영 | 균등 분할·할인 없음이라는 두 가정과 `total_cents` 단일 금액 칸 |
| 터지는 방식 | 반영 | 30,000원·쿠폰 5,000원·안내 15,000원·실제 12,500원·차액 2,500원 예시가 그대로 있다 |
| 사업적 크기 | 반영 | `business/unit-economics.md`, `product/problem.md` — 직접 손실과 재처리·3만원 오류 비용 연결 |
| 6. 조치안 | 반영 | `decisions/D-001-payment-ownership.md` — 원안 5개에 `1-A` 즉시 개선까지 보강 |
| 쇼핑몰에 요청할 필드 (초안) | 반영 | `decisions/D-001-payment-ownership.md` — 5개 필드와 이유 |
| 7. v8 병합 위치 | 누락 | wiki에 원본의 6행 v8 절별 병합 위치표가 없다 |
| 8. 남은 결정 | 반영 | `decisions/D-001-payment-ownership.md` — 착수 시점, 협의 창구, 스키마 분리 |
| 근거 목록 | 일부 | 근거가 각 wiki 문서와 front matter에 분산돼 있으나 원본의 전체 근거 목록과 “외부 인용 없음” 선언은 한곳에 보존되지 않았다 |
| 코드 | 반영 | `D-001`, `data/schema`, 각 Team 문서, `actions/outbox.md`에 해당 코드 위치와 관측이 분산 반영 |
| 테스트 | 반영 | `D-001`에 Core 도메인 격리 테스트와 금지어가 있다 |
| 데이터 | 반영 | `evaluation/golden-set.md` — 72건, 금액 관련 30건·42% |
| 계획서 | 누락 | v8 §1-1·§5·§7·§9-E·§11이라는 구체 참조 목록이 wiki에 없다 |

**빠진 것 요약:** v8 절별 병합 위치표와 계획서 근거 목록이 누락됐고, 전체 근거 목록은 일부만 한곳에 모여 있다.

===== DOC: A-COP_페인포인트_페르소나_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 이 문서의 위치 | 누락 | 원본의 v8 병합 위치·성격 6행 표가 wiki에 없다 |
| 근거 표기 규칙 | 반영 | `governance/evidence-grades.md` — `[실측]`, `[추정]`, `[미확보]` 정의와 사용 규칙 |
| 1. 왜 이 문서가 필요한가 | 누락 | v8 검색어별 등장 횟수와 “상담원이 한 번도 없다”는 결손 실측표가 없다 |
| 2. 페인포인트 `[v8 §2-A 초안]` | 반영 | `product/problem.md` |
| 2-1. 데이터가 먼저 말하는 것 | 반영 | `product/problem.md`, `evaluation/golden-set.md` — 감정·후속 동작 전 행과 50%·39% 해석 |
| 2-2. 3층 페인포인트 | 반영 | `product/problem.md` — 고객·상담원·운영 책임자의 문제, 현재 대응, 제품 기능, 지표 |
| 3. 비용 `[v8 §2-B 초안]` | 반영 | `business/index.md`, `business/unit-economics.md` |
| 3-1. 절감액으로 팔면 자기모순이다 | 반영 | `business/index.md`의 `팔지 말아야 할 논거`와 3축 표 |
| 3-2. 축 2 — 오류 1건의 비용 | 반영 | `business/unit-economics.md`, `product/problem.md`, `decisions/D-001-payment-ownership.md` |
| 3-3. 축 3 — 우리 비용, 지금 측정할 수 있다 | 반영 | `evaluation/metrics.md`, `business/unit-economics.md` — `cost/case`, 승인 대기 21%, 과잉 기권율 연결 |
| 3-4. 축 1 — 참고로만 둔다 | 반영 | `business/index.md`, `business/unit-economics.md` — 처리 비용은 보조 축이고 추정값임을 명시 |
| 4. 페르소나 `[v8 §6-A 초안]` | 반영 | `product/personas.md` |
| 4-1. 원칙 — 장식이면 넣지 않는다 | 반영 | `product/personas.md` — 골든셋·평가 지표에 연결되지 않는 페르소나는 만들지 않는다는 원칙 |
| 4-2. 박선영 — 문의하는 고객 | 일부 | 핵심 문제와 지표는 `product/personas.md`에 있으나 34세·주 2회, “확인 후 연락”을 두 번 듣는 실패 조건은 없다 |
| 4-3. 김도현 — 상담원 | 일부 | 직접 사용자·근거 탐색 문제는 있으나 CS 2년차, 화면 서너 개, AI 초안을 처음부터 재검토하는 실패 조건이 빠졌다 |
| 4-4. 정미라 — 운영 책임자 ★ 구매 결정자 | 반영 | `product/personas.md`, `product/problem.md` — 상담원 12명, 구매 결정자, 자동화 경계와 실패 조건 |
| 4-5. 넣지 않는 페르소나 | 일부 | `product/personas.md`에 제외표가 있으나 원본의 경영진 제외 사유가 법무·컴플라이언스로 바뀌었고 Personal AI 제외 사유도 달라졌다 |
| 5. 페르소나 ↔ 골든셋 배분 | 일부 | `product/personas.md`에 3인별 집계는 있으나 원본의 capability 10종·미지정 12건 배분표가 없다 |
| 실행 방법 | 누락 | `golden.jsonl`의 `persona` 필드 추가, bridge의 페르소나별 집계, 지표표 행 추가라는 3단계가 없다 |
| 6. §6 타깃 도메인 모순 수정 | 반영 | `product/scope.md` |
| 현재 상태 — 자기모순이다 | 반영 | SaaS §6과 커머스 §10의 모순, 골든셋 SaaS 0건이 명시돼 있다 |
| 교체안 | 반영 | 온라인 커머스 고객운영, 대표 시나리오 6개, 72건, Billing/Technical의 DoD-8 용도가 있다 |
| 7. §26 심사 질문 보강안 | 반영 | `product/pitch-questions.md` — 질문 5개와 답이 모두 있다 |
| 8. 데이터 교정 계획 | 반영 | `delivery/open-items.md`의 `미측정을 없애는 절차` |
| 1단계 — 있는 데이터로 채운다 | 반영 | 원본의 6개 데이터·실행 소스가 표로 있다 |
| 2단계 — 없는 것을 표시한 채로 남긴다 | 일부 | 축 1이 미확보라는 상태는 남았으나 “확보 전 발표에 넣지 않는다”는 명시적 판정이 없다 |
| 검증 기준 | 누락 | `[추정]` 0건이 아니라 남은 이유가 설명돼 있으면 완료라는 기준이 없다 |
| 9. 남은 결정 | 반영 | `delivery/open-items.md` — v8 병합 시점, persona 담당, 축 1 통계 확보 여부 |

**빠진 것 요약:** v8 결손 실측표·병합표, 골든셋 capability별 페르소나 배분과 실행 방법, 데이터 교정 완료 기준이 누락됐다.

===== DOC: A-COP_사업성_단위경제.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 이 문서가 답하는 것 | 반영 | `business/index.md`의 문서별 질문 표 |
| 1. 요약 — 숫자 세 개 | 일부 | `business/index.md`에 결론은 있으나 원본 4.06원·0.36%·32명은 새 도메인 실측 3.03원·0.27%·43명으로 정정됐다 |
| 2. 시장 규모 | 반영 | `business/market.md` |
| 2-1. 외부 수치 | 반영 | 9조 8,811억원, 19만 4,203명, USD 922.7M, CAGR 26.4%와 신뢰도 |
| 2-2. 파생 — 좌석 1개와 문의 1건의 값 | 반영 | 5,088만원, 연 10,500건, 건당 4,846원, CPH 민감도 5·7·10 |
| 2-3. TAM / SAM / SOM | 반영 | TAM 1.29조원, SAM 미확보, SOM 미산정과 이유 |
| 3. 우리 원가 — 실측 | 반영 | `business/infrastructure-cost.md`, `business/gpu-limits.md` |
| 3-1. 건당 LLM 비용 `[실측]` | 일부 | 새 도메인 Proposed 값은 반영됐으나 원본의 Baseline A/B와 Proposed 4.06원 표는 옛 도메인 측정이라 무효 처리됐다 |
| 3-2. 이 표가 말하는 것 | 일부 | 지연과 용도별 가능 여부는 반영됐으나 “단순 LLM보다 8.6~11.5배”는 Baseline 무효로 삭제됐다 |
| 3-3. LLM API 단가 비교 | 일부 | `business/infrastructure-cost.md`에 비교표가 있으나 토큰 기준이 정정됐고 Gemini 3.1 Pro 행이 빠졌다 |
| 3-4. 인프라 — 네 가지 경로 | 일부 | `infrastructure-cost.md`, `gpu-limits.md`, `architecture/repository-map.md`, `D-004`에 핵심은 있으나 L40S 행과 12GB 해결수단 4행 표 등 일부 세부가 없다 |
| 3-5. 네트워크 트래픽 — 텍스트에서는 반올림 오차다 | 반영 | `business/infrastructure-cost.md` — 6.3GB/년, 800원 미만, 100배 규모, 음성 예외 |
| 3-6. 인프라 결론 네 줄 | 반영 | `business/infrastructure-cost.md`, `business/index.md` — 수치는 정정됐지만 네 결론이 모두 있다 |
| 3-7. 아직 안 잰 것 | 반영 | `business/infrastructure-cost.md` — 추론, 4-bit 정확도, 처리량, 자체호스팅 지연 |
| 4. 고객의 이윤 — 오류 비용이 축이다 | 반영 | `business/unit-economics.md` |
| 4-1. 모델 조직 | 반영 | 상담원 12명·연 126,000건 |
| 4-2. 축 1 — 건당 처리 비용, 사람 vs A-COP | 반영 | 사람 비용 적산, 후속 동작별 시간, 2.36분, 72%, 총비용 표와 감축 해석의 함정 |
| 4-3. 축 2 — 오류 비용 ★ 이게 우리 축 | 반영 | 126,000건·1.0%·0.3%·3만원, 3,780만·1,134만·2,646만원 |
| 4-4. 오류 1건이 3만원이라는 가정의 근거 | 반영 | 직접 손실·재처리·신뢰 손실 3층 표 |
| 4-5. 축 3 — 도입 기업이 추가로 쓰는 비용 | 일부 | LLM·인프라 비용은 다른 문서에 있으나 원본의 승인 대기·구축 연동을 포함한 연간 비용표와 240만~539만원 비교가 없다 |
| 5. 우리 가격 — 세 안 | 일부 | `business/pricing.md`에 A/B/C와 C 권고 이유는 모두 있으나 32명 경계가 정정된 43명으로 대체됐다 |
| 6. 이 모델을 깨는 것 | 반영 | `business/index.md` — 13종 리스크가 여러 표와 `pricing.md`에 분산 반영 |
| 7. 다음에 채울 것 — 우선순위 | 반영 | `business/index.md`, `delivery/open-items.md` — 측정 우선순위와 방법 |
| 8. v8 병합 위치 | 누락 | 시장·원가·고객 이윤·가격·리스크의 v8 병합 위치표가 없다 |
| 출처 | 일부 | 각 business 문서의 front matter에 주요 근거가 있으나 원본 전체 출처 목록은 보존되지 않았다 |
| 인건비 | 일부 | 평균 연봉·보험·이직률은 있으나 최저임금, Bolta, CS쉐어링 출처가 빠졌다 |
| 내부 실측 (장비 제약) | 반영 | `business/gpu-limits.md`, `evaluation/finetuning.md`, `architecture/repository-map.md` |
| 인프라 시세 | 일부 | RunPod·AWS·전기요금 주요 출처는 있으나 원본의 보조 출처 전체는 없다 |
| LLM API 단가 | 누락 | 모델별 숫자는 남았지만 원본에 적힌 단가 출처 3개가 wiki에 없다 |

**빠진 것 요약:** v8 병합표와 LLM 단가 출처가 누락됐고, 옛 도메인 수치·32명 손익분기 등은 새 실측으로 정정되면서 원본 표 일부가 사라졌다.

===== DOC: 2026-08-30_DoD28-FT-RAG통합_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 결론 먼저 — 단순 배선이 아니라 재학습이 필요하다 | 반영 | `decisions/D-CS-002-finetuned-model-not-adopted.md` — 학습 입력과 실제 Team 입력의 차이, 배선+재학습 결론 |
| 1. 현재 아키텍처 | 일부 | `evaluation/finetuning.md`, `teams/response-review.md` 등에 일부가 있으나 9개 구성요소·파일/줄·인터페이스·배선 지점 전체 표가 없다 |
| 2. 설계 | 일부 | 재학습 원칙과 결과는 있으나 서빙·backend·배선 상세가 대부분 빠졌다 |
| 2.1 재학습 (stage 3) — 실제 Team 입출력 형태로 | 일부 | 입력과 실제 호출 shape의 차이는 있으나 stage3 JSON 계약, 22건 재구성 방법과 부분집합 조건이 없다 |
| 2.2 서빙 — x600에 최소 추론 서버 | 누락 | FastAPI `/complete`, 모델 1회 로드, SSH `8100` 포트포워딩, 운영 배포 제외가 없다 |
| 2.3 `LocalFTTeamLLM` — 같은 인터페이스로 새 backend | 누락 | 클래스 계약, prompts 조회, HTTP 호출, `provider="local_ft"` 감사 기록, 동일 반환 shape가 없다 |
| 2.4 배선 — 설정으로 전환 가능하게 | 누락 | settings·composition·eval runner의 `local_ft` 분기 설계가 없다 |
| 2.5 검증 순서 | 일부 | `evaluation/finetuning.md`에 동일 golden/holdout 비교 원칙은 있으나 세 arm, 27.8% 기준, holdout 1회 규칙의 구체 순서가 없다 |
| 3. 미확인/리스크 | 일부 | prompt 등록 결함과 소표본 위험은 반영됐으나 x600 네트워크·인증 범위가 없다 |
| 4. 이번 세션에서 하지 않는 것 | 누락 | 설계 당시 별도 작업으로 남긴 범위와 이후 뒤집혔다는 기록이 없다 |
| 5. 실행 결과 — 배선은 성공, 모델은 채택 불가 | 반영 | `D-CS-002`, `evaluation/finetuning.md` |
| 5.0 전제조건 결함 발견·수정 | 반영 | `teams/response-review.md`, `evaluation/finetuning.md` — 미등록 prompt, 재현 오류, 비활성화로 은폐, 수정 내용 |
| 5.1 golden.jsonl은 이 팀을 단 한 건도 안 거친다 | 반영 | `evaluation/finetuning.md` — 사후 review Team이며 학습 데이터가 0건이라는 원인 |
| 5.2 배선 — 전부 동작 확인 | 일부 | 배선 성공 결론은 있으나 신규 파일, 테스트 8건, SSH 연결, CUDA allocator 결함과 E2E 경로가 없다 |
| 5.3 모델 품질 — 채택 불가 | 일부 | 9건·0%와 채택 불가 결론은 있으나 loss 1.652, token accuracy 0.6656, JSON 0/3 비교표가 없다 |
| 5.4 판단 — 지금 채택하지 않는다 | 반영 | `D-CS-002` — 하이퍼파라미터 기각, 운영 transcript 또는 더 큰 case 집합이라는 두 경로 |
| 5.5 데이터 12건으로 늘려 재학습 | 일부 | `D-CS-002`에 12건 이력만 있고 16건 train 12/test 4, loss 1.475, accuracy 0.7054, JSON 0/4 재검증 결과가 없다 |
| 5.6 산출물 | 누락 | 신규 코드·테스트 10건·데이터셋·비교 파일·x600 체크포인트 목록이 없다 |
| 6. 데이터 84건 확충·근본 버그 2건·v6 첫 출력 | 반영 | `D-CS-002`, `evaluation/finetuning.md`, `business/gpu-limits.md` |
| 6.1 실주문 데이터로 68건 추가 확보 | 반영 | `D-CS-002` — 84건과 실주문 68건 추가 |
| 6.2 근본 버그 2건 | 일부 | Context Broker 우회와 evidence 중복은 `operations/troubleshooting.md`에 있으나 `serve.py` 입력 절삭·`max_length` 버그가 없다 |
| 6.3 v5도 여전히 OOM — Windows WDDM의 느린 실패 | 반영 | `business/gpu-limits.md`, `operations/troubleshooting.md` — 2,560토큰·25분·1,024토큰 축소 |
| 6.4 v6 결과 — 첫 유효 출력, 시나리오 획일성 | 일부 | 첫 유효 출력과 draft 2종 결론은 있으나 14/14 JSON·grounded·safe 비교표와 echo 14/14가 없다 |
| 6.5 산출물 | 누락 | 합성 케이스·축소 함수·진단 도구·v3~v6 데이터·WSL/E: I/O 경합 기록이 없다 |
| 7. 실 민원 데이터 추가·draft 원인 특정 | 반영 | `evaluation/finetuning.md` |
| 7.1 실 민원 원문 93건 추가 확보 | 반영 | 93건, 전체 157건·9.8배가 있다 |
| 7.2 고유 draft는 여전히 2개 — 원인 특정 | 반영 | 151건 반품 고정문구·6건 주문 문구와 `_maybe_review()` 원인이 있다 |
| 7.3 `--provider local_ft` 실배선 완료 | 누락 | eval runner 인자·주입 분기·470 passed 결과가 없다 |
| 7.4 다음 단계 — 재학습보다 우선순위 높은 것 | 반영 | `evaluation/finetuning.md` — `shipment.status`로 최소 3종 확보와 실제 재작성 사례 비율 우선 |
| 7.5 가설 증명 및 stage3-v7 채택 불가 | 일부 | `D-CS-002`에 v7 채택 불가만 있고 172건·4종·28/28 echo, 단일 반례와 grounded=0 이유가 없다 |
| 7.6 stage3-v8, 의도적 불일치 데이터 | 누락 | mismatch 30건, evidence 정렬 버그, holdout 33건, echo 50%, 채택 보류 결과가 없다 |
| 7.7 stage3-v9, mismatch 표본 확대 | 누락 | 262건·24%, 층화분할 220/42, 잘못된 grounded 지표, 직접 대조 40%·echo 60%, 확대 중단 결정이 전부 없다 |

**빠진 것 요약:** 최소 추론 서버·LocalFT backend·설정 배선 설계와 산출물 목록이 누락됐고, 가장 최신인 stage3-v8·v9의 실험·지표 결함·최종 기각 이유가 통째로 없다.

===== DOC: 2026-08-12_1507_A-COP_실행계획서_v1.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. v5와 이 문서의 관계 | 일부 | `delivery/dod.md`, `delivery/roles.md`에 기준 내용은 있으나 “v5 범위·계약·DoD는 유지하고 6명을 에이전트 스트림으로 재편한다”는 비교표가 없다 |
| 0-1. 실측으로 확인한 환경 | 반영 | `operations/local-setup.md` — PG 16.14, `:5433`, Docker 없음, Python 3.12.7, vector 1536 |
| 1. 최종 산출물 정의 | 일부 | `delivery/dod.md`에 DoD 1~18의 의미는 있으나 원본의 담당 스트림·Phase 열과 DoD-17 재해석이 없다 |
| 2. 스트림과 소유 디렉터리 | 반영 | `delivery/roles.md` — 누락됐던 Core·DB·API·Team·RAG·VOC·Eval·UI 8스트림 표 |
| 왜 Core를 Claude가 갖는가 | 반영 | `delivery/roles.md` — 경합·부분 실패·토큰 경계와 계약 테스트 분리 이유 |
| Codex 호출 형식 | 누락 | `codex exec -s workspace-write`의 정확한 파이프 명령과 계약 문서 인용 규칙이 없다 |
| 3. Phase 계획 | 일부 | 개별 기능 문서에는 내용이 있으나 P0~P10 체계와 각 단계 검증 명령을 한 계획으로 보존하지 않았다 |
| P0 — 부트스트랩 | 반영 | `operations/local-setup.md`, `quality/guardrails.md` — 환경·설정·가드레일 단일 원천·환경 검사 |
| P1 — Core 계약과 상태 | 반영 | `runtime/case-lifecycle.md`, `runtime/shared-state.md`, `runtime/conflict-retry.md`, `actions/outbox.md` |
| P2 — 데이터 계층 | 일부 | `data/schema`, `data/migrations`에 제약과 구조는 있으나 v5 DDL 그대로·13테이블·구독/결제 seed라는 당시 표는 보존되지 않았다 |
| P3 — Context Broker와 RAG | 반영 | `context/context-broker.md`, `context/corpus-authoring.md`, `quality/guardrails.md` — 25문서·300~400청크·12,000토큰 |
| P4 — Agent Team | 일부 | TeamModule·manifest·side effect 금지는 있으나 Billing/Technical 두 Team, prompt 6종, 당시 소유 파일 목록이 없다 |
| P5 — Controller·WAIT/RESUME·Outbox | 반영 | `runtime/*`, `actions/outbox.md` — resume, checkpoint/projection 분리, worker claim, replay |
| P6 — REST·MCP·보안 | 반영 | `external/*`, `actions/*` — REST·MCP, scope, idempotency, 승인 |
| P7 — Feedback Analytics | 반영 | `teams/voc-store-manager.md`, `quality/guardrails.md` — 인라인 분류·급증식·실패 처리 |
| P8 — 운영 UI | 일부 | `delivery/dod.md`, `teams/index.md`에 4화면과 E2E 기준은 있으나 화면별 산출물·Playwright 3시나리오 계획이 없다 |
| P9 — 평가 | 반영 | `evaluation/protocol.md`, `evaluation/golden-set.md`, `quality/eval-harness.md` |
| P10 — 통합·DoD·제출 | 일부 | DoD와 evidence 원칙은 있으나 `docs/submission`, E2E 3종, M3 산출물 묶음이 없다 |
| 4. 의존 순서와 병렬 실행 | 누락 | P0→P1 뒤 P2~P7 병렬, P5·P8·P9·P10으로 이어지는 원본 의존 그래프가 없다 |
| 5. 각 Phase 종료 시 반드시 하는 것 | 반영 | `governance/work-loop.md`, `governance/parallel-work.md` — report, evidence, history, 상태 갱신, 검수 4종 |
| 6. 이 계획의 리스크 | 반영 | `governance/parallel-work.md`, `operations/local-setup.md`, `evaluation/protocol.md`에 범위 삭감·파일 충돌·계약·PG·비용·수치 과대해석 대응 |
| 7. 진행 상태 | 일부 | 각 영역의 현재 상태는 있으나 원본 P0~P10 상태표와 당시 비고를 그대로 추적하는 표는 없다 |
| 마일스톤 | 누락 | 원본의 M1 도달·M2 도달 상태 전이·M3 미도달 표가 없다 |
| 반복된 실패 유형 | 반영 | `governance/parallel-work.md`, `context/corpus-authoring.md`, `quality/blind-spots.md`, `operations/troubleshooting.md`에 7종 원인과 사례가 분산 반영 |
| 참조 | 일부 | RULE·CLAUDE·DoD 근거는 wiki에 있으나 v5 절별 참조와 외부 구조 원형 경로가 없다 |

**빠진 것 요약:** 8스트림 소유 표는 반영됐지만 Codex 호출 명령, P0~P10 의존 그래프, M1~M3 당시 상태가 누락됐다.

===== DOC: A-COP_Composer_중앙설정저장소_결정.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 결정 | 반영 | `decisions/D-007-central-config-store.md` — direct·central 동시 지원, UI 환경변수 선택, 수천 규모에서는 central |
| 2. 왜 — 두 요구가 지금 구조에서 충돌했다 | 반영 | `D-007` — 고객 빌드 쓰기 코드 금지와 릴리즈 후 관리 요구의 충돌 및 로컬 YAML 한계 |
| 3. 어떻게 바뀌나 | 반영 | `D-007`의 구조·변경 전후 표 |
| 3.1 지금 | 일부 | 로컬 YAML과 대상별 쓰기 구조는 있으나 고객사 1·2·3000 각각에 Composer가 필요하다는 원본 도식은 축약됐다 |
| 3.2 결정 후 | 반영 | 중앙 서비스+DB, 배포본 읽기 전용, 쓰기 코드 제거라는 구조 |
| 4. 용어 | 누락 | 대상·설정·중앙 저장소·설정 서비스·UI·`acop_composer_ui` 6개 용어표가 없다 |
| 5. UI에서 모듈·인스턴스 CRUD가 되는가 | 반영 | `D-007`, `D-CS-003`, `D-CS-004` — `/catalog`, `/changes`, `/toggle`, 인스턴스 CRUD와 grant ceiling |
| 6. 무엇을 고쳐야 하나 | 일부 | `D-007`에 YAML→DB row/CAS, 식별, 감사, 읽기는 있으나 `threading.Lock`, 부트스트랩+캐시 등 원본 변경표 전체는 없다 |
| 7. 이 결정이 바꾸지 않는 것 | 반영 | 저장/활성 구분, 서버 판정, grant ceiling이 있다 |
| 8. 아직 정하지 않은 것 | 일부 | HA·백업·인증·방화벽은 남았으나 PostgreSQL 재사용, `deployment_id`, fail-fast, reload, 운영 연기 등 확정된 전체 행이 없다 |
| 8-1. 구현 결과 | 일부 | 마이그레이션·store·config source·service app과 438 tests는 있으나 6개 단계별 파일·커밋 표와 격리/CAS 검증 전체가 없다 |
| 9. 이 결정이 틀릴 수 있는 조건 | 반영 | `D-007` — 실제 대상이 수십 개 이하이면 direct가 낫다는 반증 조건 |
| 10. 다른 문서와의 관계 | 반영 | 인스턴스 CRUD 금지 철회, 임의 Python 경로 금지 유지, 3패키지 구조 유지 |

**빠진 것 요약:** Composer 용어표가 누락됐고, 저장 계층 변경표·확정된 운영 결정·구현 커밋 표는 일부만 축약 반영됐다.

===== DOC: A-COP_확장추천_검토.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 결론 | 반영 | `decisions/D-009-recommendation-scope.md` — 자기 관측은 VISION-13, 교차 프로젝트는 VISION-10 2층, 둘 다 현재는 보류 |
| 2. 추천 근거 두 종류 | 일부 | 자기 관측/교차 프로젝트 구분은 있으나 필요한 프로젝트 수 1개·3개 이상과 두 예시가 없다 |
| 3. 자기 관측 기반은 지금 구조에서 성립한다 | 반영 | `D-009` — 기존 이벤트를 추천 근거로 쓸 수 있다는 결론 |
| 3.1 라우팅 실패가 이벤트로 남는다 | 일부 | `routing_failed`는 있으나 `RegistryError` 코드, `failure_code=no_team`, 파일·줄 근거가 없다 |
| 3.2 다른 신호도 이미 있다 | 일부 | `classification_failed`까지만 예시로 있고 `missing_input`, `retry_exhausted`, `guardrail_escalated`, `approval_required`와 저장 컬럼 표가 없다 |
| 3.3 다만 집계 경로가 없다 | 반영 | `D-009` — 이벤트는 쌓이지만 세는 집계 조회가 없다는 결론 |
| 4. 위험과 관리 방법 | 반영 | `D-009` — dry-run, 사람 적용, 익명 집계, 근거 Case 공개 |
| 5. 등록 형태 제안 | 일부 | VISION-13·VISION-10 분리는 있으나 각 항목의 비용·폐기 조건까지 등록되지 않았다 |
| 5.1 VISION-13 신규 등록 | 일부 | 트리거가 원본의 “50건 이상 AND 동일 유형 10건 이상 AND 집계 조회”에서 wiki의 “50건 OR 동일 유형 10건”으로 바뀌었고, 3~5일·2~4일 비용과 3회 연속 무시 폐기 조건이 없다 |
| 5.2 VISION-10 2층 갱신 | 일부 | 교차 프로젝트 추천 흡수 결론은 있으나 릴리즈 프로젝트 2개 이상·인스턴스 3세트 이상 트리거가 없다 |
| 6. 확인하지 못한 것 | 일부 | 이벤트량·집계 조회·표시 화면은 있으나 Codex 파일 쓰기 실패라는 검토 한계가 빠졌다 |

**빠진 것 요약:** 추천 기능의 큰 결정은 반영됐지만 이벤트 신호표, VISION-13의 AND 트리거·비용·폐기 조건, VISION-10 수량 트리거가 축약되거나 바뀌었다.

===== DOC: A-COP_비전항목_검토.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 결론 | 일부 | `decisions/D-009-recommendation-scope.md`에 항목 B의 3분할은 있으나 항목 A를 “예제 라이브러리+선언형 Team+CRUD의 Phase 2 흐름”으로 정의한 결론은 축약됐다 |
| 2. 항목 A 검토 | 일부 | `D-CS-003`, `D-CS-004`, `D-009`에 카탈로그·CRUD 구성요소는 있으나 하나의 비전 항목으로 묶은 검토는 없다 |
| 판단 | 일부 | 카탈로그 기반 CRUD의 필요성은 있으나 계획 3개를 잇는 이유, 현재 예제 2개, UI 선택 생성 미확인, 6개 Team과의 단절이 없다 |
| 권고 형태와 시점 | 일부 | 카탈로그·revision·검증 개념은 있으나 6단계 사용자 흐름, 선언형/코드형 구분, namespace·라우팅 선행조건이 없다 |
| 3. 항목 B 검토 | 반영 | `D-009` — 공개 데이터 전처리·고객 RAG·평가셋 보조를 서로 다른 성격으로 분리 |
| 공개 데이터셋 정리 | 일부 | 제품에서 제외한다는 결론은 있으나 `raw/processed/scripts/REPORT/preprocess_stats` 규약과 데이터셋별 판단 유지가 없다 |
| 고객 문서의 RAG 지식화 | 일부 | 제품 기능·사람 승인·반출 위험은 있으나 업로드부터 롤백까지의 수집 계층과 청크별 출처·기간·tenant·해시·승인자 계약이 없다 |
| 고객사 평가셋 작성 | 반영 | `D-009`, `evaluation/protocol.md`, `evaluation/golden-set.md` — 후보 생성까지만 자동화, 독립 라벨, 제3자 조정, holdout 봉인 |
| 4. 위험과 관리 방법 | 일부 | 위험 4종은 `D-009`에 있으나 staging·변환 이력·접근 로그·노출 시 holdout 폐기 등 구체 통제표가 축약됐다 |
| 5. 의존 관계와 순서 | 반영 | `D-009`의 Team→예제→CRUD, 문서→승인→RAG, Case→라벨→holdout 순서 |
| 6. 비전 TODO 문서 형태 제안 | 누락 | `final_project_sample/docs/vision/`을 정본으로 유지하고 VISION-10 갱신·항목 B 2문서 분리·상태값을 제한하자는 구조 제안이 없다 |
| 7. 확인하지 못한 것 | 일부 | `D-009`에 CRUD·고객 문서·배포·holdout 미확인은 있으나 카탈로그/6개 Team 불일치와 VOC 4종·924MB 정정이 없다 |

**빠진 것 요약:** 항목 B의 분리 결정은 반영됐지만 항목 A의 구체 사용자 흐름과 비전 TODO 정본·문서 구조 제안이 빠졌다.

===== 전체 =====

| 원본 | 절 수 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| A-COP_결제소유_경계.md | 31 | 28 | 1 | 2 |
| A-COP_페인포인트_페르소나_설계.md | 28 | 19 | 5 | 4 |
| A-COP_사업성_단위경제.md | 29 | 17 | 10 | 2 |
| 2026-08-30_DoD28-FT-RAG통합_설계.md | 32 | 12 | 11 | 9 |
| 2026-08-12_1507_A-COP_실행계획서_v1.md | 25 | 13 | 9 | 3 |
| A-COP_Composer_중앙설정저장소_결정.md | 13 | 8 | 4 | 1 |
| A-COP_확장추천_검토.md | 11 | 5 | 6 | 0 |
| A-COP_비전항목_검토.md | 12 | 3 | 8 | 1 |
| **합계** | **181** | **105** | **54** | **22** |