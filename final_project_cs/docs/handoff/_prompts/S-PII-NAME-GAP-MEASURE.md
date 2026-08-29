# S-PII-NAME-GAP-MEASURE — REV PII 정규식의 "이름 탐지 0%" 갭을 실측하고 개선안 제안

## 0. 배경 (읽기만)

- `app/modules/customer_ops/response_review_policy.py` 의 `PII_PATTERNS` 를
  직접 확인했다:
  ```python
  PII_PATTERNS: tuple[Pattern[str], ...] = (
      re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),          # 이메일
      re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"),      # 전화번호류
      re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),            # 카드/계좌류
  )
  ```
  **사람 이름(성명)을 잡는 패턴이 하나도 없다.** "흔치 않은 이름을 놓칠 수
  있다"는 정도가 아니라, 이름 탐지 자체가 구조적으로 없는 상태다.
- `datasets/voc/nikl_ne_2022/raw/NIKL_NE_2022_CSV.zip` — 국립국어원 개체명
  분석 말뭉치(NE, 개체 연결 아님). CSV 3종(M/N/S 접두사). 스키마 확인됨:
  `file_id,doc_id,title,author,date,topic,sent_id,sent_form,NE_id,NE_form,NE_label,NE_begin,NE_end`
  — `sent_form` 이 문장 원문, `NE_form`/`NE_label` 이 그 문장 안에서 태깅된
  개체명과 그 유형(배열로 여러 개 있을 수 있음, 없으면 `[]`).
- 이번 작업은 **개선안 제안까지다 — `response_review_policy.py` 를
  직접 수정하지 않는다.** PII 즉시 escalate 는 안전 관련 코드라 실측
  근거 없이 바로 배포용 코드를 바꾸지 않는다(`CLAUDE.md` §0.1). Claude
  가 결과를 검토한 뒤 별도 작업으로 실제 반영 여부를 결정한다.

## 1. 할 일

1. `NIKL_NE_2022_CSV.zip` 을 파싱해서(압축 해제 없이 `zipfile` 로 스트리밍
   읽어도 되고, 필요하면 해제해도 된다 — 디스크 여유는 확인해라) 사람
   이름에 해당하는 `NE_label` 값을 찾아라(국립국어원 표준 개체명 태그셋
   기준으로 `PS_NAME` 류로 추정되나, **실제 데이터에서 나오는 라벨 값을
   직접 확인하고 정확한 값을 써라** — 추측으로 필터링하지 마라).
2. 사람 이름으로 태깅된 case 를 최소 500건 이상 표본으로 뽑아라(전체가
   더 많으면 무작위 표본, 재현 가능하게 seed 고정).
3. 각 표본의 `sent_form`(그 이름이 들어있는 문장 원문)에 현재
   `PII_PATTERNS` 3개를 실제로 돌려서, 이름이 매칭되는지 확인해라
   (매칭 안 될 거라고 이미 알고 있지만, **추정하지 말고 실제로 코드를
   실행해서 수치를 내라** — 0건이면 0건이라고 실측으로 적어라).
4. **개선안을 2가지 이상 설계하고 각각의 recall 을 같은 표본으로
   측정해라**:
   - 안 A: 한국어 성씨 사전 기반 패턴(예: 흔한 성씨 100여 개 + 그 뒤에
     오는 1~2음절 이름 패턴, 조사/호칭 — "님", "씨" 등 — 로 경계 판단).
     실제 사전을 어디서 가져올지(공개 성씨 빈도 목록 등) 밝혀라. 없으면
     이 NIKL 말뭉치 자체에서 관찰된 성씨 글자를 사전으로 구성해도 된다.
   - 안 B: 다른 접근(예: 조사/호칭 패턴만으로 이름 후보를 잡는 방식,
     또는 이미 이 환경에 설치된 형태소 분석기가 있다면 그걸 이용하는
     방식 — 있는지 먼저 확인해라, 없으면 새로 설치하지 마라).
   - 각 안의 recall(진짜 이름 중 몇 %를 잡는지) 과 **오탐 위험**(일반
     단어를 이름으로 잘못 잡는 경우가 얼마나 될지 — 같은 표본에서 이름이
     아닌 부분을 얼마나 잘못 잡는지도 확인해라)을 같이 보고해라.
5. 실제 고객 응대 문맥과 가까운 도메인(M/S 접두사 — 메신저/SNS 대화)과
   뉴스(N 접두사)를 구분해서 recall 을 따로 내라 — 우리 서비스는 고객
   메시지가 대상이라 대화체 도메인이 더 대표성 있다.

## 2. 산출물

- `datasets/voc/nikl_ne_2022/processed/pii_name_gap_measurement.md` (신규)
  — §1의 실측 결과, 안 A/B 비교표, 권고안(어느 안을 추천하는지와 이유)
- `datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py` (신규,
  재실행 가능한 측정 스크립트 — 이게 이번 작업의 핵심 산출물이다)
- `docs/reports/2026-08-24_S-PII-NAME-GAP-MEASURE_리포트.md` (신규)

## 3. 쓰기 대상 (workspace 루트 기준 — `-C` 가 `final_workspace` 다)

- `datasets/voc/nikl_ne_2022/processed/` 아래 신규 파일들
- `final_project_cs/docs/reports/2026-08-24_S-PII-NAME-GAP-MEASURE_리포트.md`

## 4. 하지 말 것

- `app/modules/customer_ops/response_review_policy.py` 수정 금지 — 이번엔
  측정·제안까지다
- `app/modules/customer_ops/response_review.py` 등 다른 REV 코드 수정 금지
- 새 Python 패키지 설치 금지(형태소 분석기 등 이미 설치된 것만 써라,
  없으면 안 은 사전 기반으로 한정해라)
- 원본 NIKL zip 압축 해제한 파일을 그대로 커밋 대상 경로에 남기지 마라
  (필요하면 임시 디렉터리에서 작업하고 정리해라) — `processed/` 에는
  측정 결과와 스크립트만 남긴다

## 5. 검증

- 측정 스크립트를 두 번 실행해서 같은 seed 로 같은 숫자가 나오는지
  확인해라(재현성).
- 리포트에 실제 실행 명령과 터미널 출력을 그대로 붙여라.
