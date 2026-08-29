# S-PII-NAME-DETECTOR-IMPLEMENT — 성씨사전+호칭 결합 이름탐지를 실제 구현

## 0. 배경 (읽기만)

- `docs/reports/2026-08-24_S-PII-NAME-GAP-MEASURE_리포트.md` — 실측 결과:
  현재 `PII_PATTERNS`(이메일/전화/카드번호)엔 이름탐지가 0%. 안 A(관찰된
  성씨 첫음절 전부)는 recall 60~73%지만 오탐이 500문장당 684~5,161건으로
  못 쓴다. 안 B(호칭만)는 오탐은 적지만 recall 0.4~2.2%로 단독 사용 불가.
  권고: **검증된 성씨 사전으로 좁히고 호칭 문맥과 결합**.
- `datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py` — 기존
  측정 스크립트(안 A/B 비교용). **이 스크립트의 측정 로직·표본(seed
  20260824, M/S/N 각 500건)을 그대로 재사용해서 새 방법도 같은 기준으로
  측정해라** — 다른 표본으로 비교하면 수치가 의미 없어진다.
- 대상 코드: `app/modules/customer_ops/response_review_policy.py` 의
  `PII_PATTERNS`. 이번엔 **실제로 프로덕션 코드에 반영한다** — 안전
  관련 코드이니 §3 기준을 반드시 충족해야 반영해라, 기준 미달이면
  반영하지 말고 그 사실을 정직하게 보고해라.

## 1. 할 일

1. **검증된 성씨 사전을 확보해라.** NIKL 말뭉치에서 관찰된 성씨를
   자동으로 다 쓰지 마라(이게 안 A 가 오탐 폭증한 원인이었다). 대신:
   - 통계청 인구총조사 "성씨 및 본관별 인구" 같은 공식 자료나, 흔히
     알려진 한국 성씨 빈도 상위 목록(대략 상위 30~50개가 인구 대다수를
     차지한다고 알려져 있다)을 찾아서 근거와 함께 사전을 구성해라.
     웹검색이 가능하면 실제 출처를 인용해라. 안 되면 이 저장소 안에
     이미 있는 자료(NIKL 관찰 빈도 등)로 대체하되, **왜 그 임계값을
     골랐는지**(예: 상위 N개, 빈도 M회 이상만 채택) 리포트에 근거를
     남겨라 — "그냥 다 넣었다"는 안 된다.
2. **호칭 문맥과 결합해라**: "님", "씨", "고객님" 류 호칭이 이름 뒤에
   붙거나, "저는 ○○입니다"/"성함은 ○○" 류 패턴이 앞에 오는 경우만
   양성으로 잡아라. 사전에 있는 성씨라도 호칭 문맥이 없으면 잡지 마라
   (이게 안 A 오탐의 핵심 원인 — 문맥 없이 아무 데서나 매칭했다).
3. `measure_pii_recall.py` 를 확장해(새 스크립트를 또 만들지 말고 같은
   스크립트에 새 방법을 추가해라) 새 방법의 recall·오탐을 M/S/N 도메인별로
   측정해라.

## 2. 판정 기준 — 이걸 충족해야 반영한다

- **오탐이 안 A보다 최소 10배 이상 적어야 한다**(500문장당 오탐이
  두 자릿수 이하 목표 — 안 B 수준의 오탐 통제를 유지하면서).
- **recall 이 안 B(0.4~2.2%)보다는 뚜렷하게 나아야 한다** — 완벽한 수치
  기준을 못 박긴 어렵다, 하지만 "거의 안 잡히는 수준"이면 실용성이
  없다고 판단하고 반영하지 마라.
- 두 조건을 만족하면 §3 으로 진행해라. 못 만족하면 **반영하지 말고**,
  측정 결과와 "왜 기준 미달인지"를 리포트에 정직하게 적고 멈춰라 —
  억지로 기준을 낮춰 통과시키지 마라.

## 3. 반영 (판정 통과 시에만)

1. `response_review_policy.py` 의 `PII_PATTERNS` 옆에 새 이름탐지 함수를
   추가해라(정규식 하나로 표현이 안 되면 함수로 만들어도 된다 — 기존
   `PII_PATTERNS` 는 정규식 튜플이니, 이름탐지가 문맥 결합이 필요하다면
   별도 함수 `detect_person_name_pii(text: str) -> bool` 류로 만들고
   REV 가 이 함수도 같이 호출하도록 `response_review.py` 의 호출부를
   최소 침습적으로 연결해라).
2. `tests/unit/teams/test_response_review.py` 에 새 테스트를 추가해라:
   이름+호칭이 있는 문장 → PII 로 즉시 escalate, 이름 같은 단어가 있어도
   호칭 문맥 없으면 → escalate 안 함(오탐 방지 확인), 기존 6개 테스트가
   여전히 통과하는지.

## 4. 쓰기 대상

★작업 루트가 `final_workspace`(상위 폴더) 전체다 — `-C` 가 그렇게
설정돼 있다. 아래 경로는 전부 `final_workspace` 기준 상대경로다
(`app/...`가 아니라 `final_project_cs/app/...`).

- `datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py` (방법 추가)
- `datasets/voc/nikl_ne_2022/processed/pii_name_gap_measurement.md` (결과 갱신)
- `final_project_cs/app/modules/customer_ops/response_review_policy.py` (§3 통과 시에만)
- `final_project_cs/app/modules/customer_ops/response_review.py` (§3 통과 시에만, 호출부 연결)
- `final_project_cs/tests/unit/teams/test_response_review.py` (§3 통과 시에만)
- `final_project_cs/docs/reports/2026-08-24_S-PII-NAME-DETECTOR-IMPLEMENT_리포트.md` (신규)

## 5. 하지 말 것

- 새 Python 패키지 설치 금지
- 기준 미달인데 반영하지 마라(§2)
- 기존 `PII_PATTERNS` 3개(이메일/전화/카드) 로직 수정 금지 — 추가만 한다
- `verify_proposal`/사실대조 등 REV 의 다른 검증 단계 수정 금지

## 6. 검증

- 측정 스크립트를 두 번 실행해 재현되는지 확인해라.
- §3 까지 갔다면 `final_project_cs` 디렉터리 안에서
  `python -m pytest -q -m "not live"` 를 실행한 결과를 리포트에 실제
  출력 그대로 붙여라(현재 354 passed 기준 변화 명시).
