# 여행 Team의 후보 조회·선택 재개 추가 검증

실행 시각: 2026-10-11 03:49 KST. 앞선 [대화 재개 검증](2026-10-11_0342_team_conversation_resume.md) 이후 확인 문장·후보 조회 분기를 보완했다. 앞 기록의 파일 해시는 당시 판이며 현재 해시는 아래와 같다.

## 실행 명령과 실제 출력

```powershell
python -u -m pytest tests/unit/travel/test_conversation_work.py tests/unit/travel/test_fresh_alternate.py tests/unit/travel/test_dining_review_fixes.py -q
```

```text
..............................................                           [100%]
46 passed in 1.86s
```

새 대화 시험 26건과 기존 회귀 시험 20건, 46/46 = 100%이다. Windows asyncio의 내부 socketpair 제한을 피하기 위해 동일 시험을 일반 권한으로 실행했다. 실제 외부 공급자 호출·화면·DB 단일 적용은 별도 통합 시험 범위다.

## 추가 확인

- `네, 되돌려 줘`는 전체 문장이 긍정·되돌림 확인일 때만 재개한다. 무관한 문장이나 부정은 긍정으로 처리하지 않는다.
- `propose_alternatives`는 기존 대체 후보 계산과 `options_from`으로 후보를 만들고 일정은 바꾸지 않은 채 `WAIT_FOR_INPUT`으로 질문한다. 결과의 `decisions[0]`은 `itinerary=asked`, `options`, `choices`를 담는다. 원래 장소는 후보에서 제외한다.
- 같은 업무에서 2번을 고르면 해당 후보의 식별자·시각을 확인한 뒤 기존 `plan_swap` 계산과 `ActionProposal` 1개로 연결한다. 표시했던 후보가 사라지면 새 2번 후보를 임의 적용하지 않고 다시 묻는다.
- 조건 완화 후보도 숫자 순위가 아닌 `plan_swap`의 실제 계약인 옵션 `key`로 선택하며 고객이 선택한 시작·종료 시각을 그대로 유지한다.
- Team 내부는 쓰기와 알림을 수행하지 않는다. 실제 일정 적용과 통지는 Controller의 기존 공통 적용 경로가 맡는다.

## 원본 백업과 현재 해시

확인 문장 보완 전 백업: `../../../_backup/2026-10-11_0350_team_confirmation/`. 후보 조회 보완 전 백업: `../../../_backup/2026-10-11_0346_team_propose/`.

| 파일 | SHA256 |
|---|---|
| conversation_work.py | 0838701367D535C645F876C017BB14E82AE6DF2A1FFF85DEEF682A465FC43AF0 |
| test_conversation_work.py | 47D10AA5803CE349E434530C0E46AD17705CBA4EAA7A69C19FA7A3F56C659696 |
