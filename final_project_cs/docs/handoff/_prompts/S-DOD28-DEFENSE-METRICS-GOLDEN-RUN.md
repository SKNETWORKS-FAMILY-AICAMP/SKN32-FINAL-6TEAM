# S-DOD28-DEFENSE-METRICS-GOLDEN-RUN — 방어지표를 픽스처가 아니라 실제 golden/holdout 출력으로 측정

## 0. 배경

- `docs/evidence/DoD-28_파인튜닝_방어지표.md` — 방어지표 5종(grounding_match,
  grounding_excess, proper_abstention, over_abstention, schema_compliance)
  은 `eval/defense_metrics.py` 에 구현돼 있고 `eval/datasets/attack_fixtures.jsonl`
  (공격 픽스처 17건, 사람이 직접 작성한 것)로만 검증됐다. **실제 LLM 이
  golden/holdout 을 풀어서 낸 출력에는 이 지표를 한 번도 돌려본 적이
  없다.**
- 실제 파인튜닝(1차 공개데이터·2차 알파실데이터 모델)은 이번 작업
  범위가 아니다 — 그건 GPU·학습데이터·시간이 필요한 별도 작업이고,
  Codex 세션 하나로 할 일이 아니다. **이번엔 "이미 있는 Proposed 모델
  경로가 golden/holdout 을 실제로 풀었을 때 방어지표가 어떻게 나오는지
  최초로 측정"까지만** 한다.
- `eval/runners/proposed.py` 가 이미 존재한다 — 이걸 읽고 golden 또는
  holdout 데이터셋에 대해 실제로 실행하는 방법을 파악해라.

## 1. 할 일

1. `eval/runners/proposed.py` 를 golden.jsonl(72건, DoD-29 작업으로
   방금 12건이 늘었다) 에 대해 실제로 실행해서 각 case 의 제안(proposal)
   출력을 얻는다. 이 실행에 실 LLM 호출이 필요하다면 — 이 프로젝트의
   `-m live` 관례를 따르고, API 키가 없으면 스킵하되 스킵했다는 사실을
   정직하게 리포트에 남겨라(지어내지 마라).
2. 그 출력들에 `eval/defense_metrics.py` 의 5개 지표를 실제로 적용해서
   분자/분모와 함께 기록한다. `docs/evidence/DoD-28_파인튜닝_방어지표.md`
   가 요구하는 형식(각 지표의 정의·분자·분모)을 그대로 따른다.
3. 픽스처 기반 결과(기존 17건)와 golden 기반 결과(신규)를 **같은 표에서
   나란히 비교**해서 리포트에 남긴다 — 둘이 다르게 나온다면 왜 다른지도
   적어라(픽스처는 사람이 의도적으로 만든 공격 사례라 실제 분포와 다를
   수 있다는 점 등).
4. **파인튜닝 자체를 하지 않았다는 것을 명확히 남겨라** — "1차/2차
   모델 비교"는 여전히 미착수라고 정직하게 적는다. 이번 작업은 그
   비교를 할 수 있는 측정 파이프라인이 golden 레벨에서 실제로 도는 걸
   최초로 확인한 것뿐이다.

## 2. 쓰기 대상

- `eval/reports/` 아래 신규 결과 파일(기존 파일명 관례 확인 후 따라라 —
  `run_id`/날짜가 파일명에 들어가는 관례가 있다면 지켜라)
- `docs/reports/2026-08-20_S-DOD28-DEFENSE-METRICS-GOLDEN-RUN_리포트.md` (신규)

## 3. 하지 말 것

- 실제 파인튜닝을 시작하지 않는다 — 이건 범위 밖이다
- `eval/defense_metrics.py` 의 지표 계산 로직을 수정하지 않는다(이미
  검증된 코드 — 이번엔 실행·측정만 한다)
- API 키가 없어서 실 LLM 호출을 못 했다면 가짜 숫자를 채우지 않는다 —
  "미실행"이라고 정직하게 적는다
- `docs/evidence/DoD-28_파인튜닝_방어지표.md` 직접 수정(Claude 가 검증
  후 갱신한다)

## 4. 검증

- 실제로 실행한 명령과 터미널 출력을 리포트에 그대로 붙여라. 몇 건을
  실제로 돌렸는지, 몇 건이 API 키 부재 등으로 스킵됐는지 정확한 숫자로
  남겨라.
