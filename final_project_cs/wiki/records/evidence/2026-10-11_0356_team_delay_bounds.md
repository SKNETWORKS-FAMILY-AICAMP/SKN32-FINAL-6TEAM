# 여행 Team 지연 시간 입력 범위 검증

실행 시각: 2026-10-11 03:56 KST. [숫자 선택 분리 검증](2026-10-11_0353_team_numeric_reply_resume.md) 이후 최초 입력과 재개 답변의 허용 범위를 맞췄다.

## 확인한 동작

지연 시간은 불리언을 제외한 정수 1~1440분이다. 문자열 답변의 분·시간 합산도 같은 범위로 제한한다. 전화번호(하이픈 포함·숫자만), 0·음수·소수·범위 표현, 1441분·25시간은 계산으로 넘기지 않고 다시 묻는다. 1분·1440분·24시간은 허용한다. request.minutes가 문자열인 경우에도 숫자 정수 계약을 먼저 채우도록 묻는다.

```powershell
python -u -m pytest tests/unit/travel/test_conversation_work.py tests/unit/travel/test_fresh_alternate.py tests/unit/travel/test_dining_review_fixes.py -q
```

실제 출력: `64 passed in 2.87s`. 새 대화 시험 44건과 기존 회귀 시험 20건, 64/64 = 100%이다. Windows asyncio socketpair 제한을 피한 일반 권한 실행이다. Ruff 검사도 통과했다. 실제 화면·외부 공급자·DB 단일 적용은 별도 통합 확인 범위다.

## 원본 보존과 해시

변경 직전 원본은 [백업 폴더](../../../_backup/2026-10-11_0355_team_delay_bounds/)에 보존했다.

| 파일 | SHA256 |
|---|---|
| conversation_work.py | 6D805F244A9E1E0E065E707462B9DE7699C713A9200A786E9DD1514708DE1F71 |
| test_conversation_work.py | 4E33D8DAF74FEE98A3429D6447E202BD1113BEAD058BA9F839EABA9AA1601C8D |
