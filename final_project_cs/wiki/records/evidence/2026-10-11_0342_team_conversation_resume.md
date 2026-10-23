# 여행 Team의 웹 업무 대기·재개 검증

실행 시각: 2026-10-11 03:42 KST. 현재 작업 폴더의 코드에서 실행했으며 커밋·배포하지 않았다.

## 재현 명령과 실제 출력

Windows 격리 환경에서는 `asyncio.new_event_loop()`가 내부 socketpair를 만들다가 멈췄다. `faulthandler.dump_traceback_later(5)`로 `socket._fallback_socketpair -> accept` 정지를 확인하고, 일반 실행 권한에서 동일 시험을 실행했다. 앱 전체 조립을 대체하는 시험 fixture는 추가하지 않았고 기존 공통 fixture를 사용했다.

```powershell
python -m ruff check app/domains/travel_ops/instances/_shared/conversation_work.py tests/unit/travel/test_conversation_work.py
python -u -m pytest tests/unit/travel/test_conversation_work.py tests/unit/travel/test_fresh_alternate.py tests/unit/travel/test_dining_review_fixes.py -q
```

```text
All checks passed!
.........................................                                [100%]
41 passed in 2.36s
```

새 대화 시험 21건과 기존 대체 장소·영업 여부·조회 예산 보호 회귀 시험 20건으로 41/41 = 100%이다. 화면과 실제 DB의 단일 적용은 이 시험의 확인 범위가 아니며 웹/Controller 통합 스트림에서 별도로 확인해야 한다.

## 확인한 동작

- 실제 `DiningTeam.execute`가 분 단위 부족 정보를 질문과 근거를 갖춘 `WAIT_FOR_INPUT`으로 반환한다. 추가 답변 `30분이요`는 기존 계산기의 `minutes=30`으로 전달된다.
- 음수·소수·범위·전화번호 형식·모호한 문장을 시간으로 적용하지 않는다. 중복 제목은 첫 항목을 임의로 고르지 않고 다시 묻는다.
- 대상 선택 및 되돌림 확인은 같은 업무의 필수 입력 스키마에 보존한다. 두 차례 질문에서도 먼저 해석한 업무·버전이 사라지지 않는다.
- `apply_change`의 실제 대체 식당 계산은 `itinerary.apply` 제안 1개를 반환하며 주입된 일정 읽기 모델의 버전·장소는 바뀌지 않는다. Team 내부는 쓰기나 알림을 수행하지 않는다.
- 기존 `ItineraryApply._ask_instead`의 보호 조건 및 적용 시 전체 재판정은 변경하지 않았다.

## 인터페이스

`run_itinerary`는 `subject_ref.request.type=conversation`을 `run_conversation`에 전달한다. `action`은 `clarify`, `answer_fact`, `apply_change`, `rollback`, `redo`, `report_delay`, `report_closed`를 지원한다. 읽기 도구에서 여행 일정이 없는 오류는 고객 정보 부족과 달리 기존 사람 이관으로 처리한다.

필수 상태 전달은 `subject_ref`, `customer_input`, `customer_input_history`, `required_input_schema`이다. 질문의 스키마 확장 `x-conversation`에는 서버가 구성한 `request`와 선택한 `part_id`가 들어가며 다음 질문에서 이전 빈칸을 유지한다. `choices`에는 선택을 식별할 `action/item_id/fact/to_version`을 보존한다. 조건 완화 후보는 이전에 표시한 식별자·시각과 새 계산 결과가 일치해야 선택한다.

처음 담당과 다른 종류의 항목을 고객이 고르면 이 부품은 `target_kind_mismatch`로 차단한다. 웹 재개 라우팅에서 선택 대상에 맞는 실제 Team을 다시 배정해야 한다.

## 파일 해시와 원본 보존

원본 백업: `../../../_backup/2026-10-11_team_conversation/`의 `itinerary_team.py`, `dining_team.py`.

| 파일 | SHA256 |
|---|---|
| conversation_work.py | EE76E84B74DB7354DF2A6EB0D9722B0539F5BAAB35B8A0D11CA3526A152B4CB0 |
| itinerary_team.py | BAF66B6D64BEB80C873982CE1F3EE87AC838C914461BEF1E7D9E5DA4CB3D1CFD |
| dining/team.py | D08D294E8B66F9A6715E3C3D993FBB91CBADB4E454A21DBB06E7BF44BE3BCCF3 |
| test_conversation_work.py | B4E9AA55C4B010EEF4530AD4838D0A3983D952635ADCD899851CB12E4BD73632 |
