# DoD-18 재측정 원문

## 재현 명령

fake Team의 첫 실행이 `waiting_approval`을 반환하도록 REST Case를 만들고 삭제 전에 다음 경로를 호출했다.

```text
GET /ui/cases
GET /ui/cases/{case_id}
GET /ui/approvals
GET /ui/cases/{case_id}/trace
```

HTML 본문에서 UUID 전체 문자열과 trace version 위치를 검색했다. 종료 후 tenant와 연결 데이터를 삭제했다.

## 실제 출력

```text
DOD18_page= /ui/cases case_id_exact= True case_id_prefix= True
DOD18_page= /ui/cases/762ba6ac-b9b0-4d90-bc70-b04957024706 case_id_exact= True case_id_prefix= True
DOD18_page= /ui/approvals case_id_exact= True case_id_prefix= True
DOD18_page= /ui/cases/762ba6ac-b9b0-4d90-bc70-b04957024706/trace case_id_exact= False case_id_prefix= False
DOD18_trace_version_positions= [1396, 1609, 1880, 2124]
DOD18_trace_increasing= True
DOD18_case_state= ('waiting_approval', 4)
DOD18_events= [('created', 1), ('classified', 2), ('routed', 3), ('approval_required', 4)]
```

## 관측 사실

- `/ui/cases`, `/ui/cases/{id}`, `/ui/approvals` 본문 검색의 `case_id_exact`는 모두 `True`였다.
- trace 본문 검색의 `case_id_exact`와 `case_id_prefix`는 모두 `False`였다.
- trace version 검색 위치는 `[1396, 1609, 1880, 2124]`였다.
- Case DB 상태·버전은 `('waiting_approval', 4)`였다.
- Case event 출력은 `created/1`, `classified/2`, `routed/3`, `approval_required/4`였다.

## 확인하지 못한 것

- 승인 버튼을 UI에서 눌러 이후 화면을 다시 조회하는 동작은 실행하지 않았다.
- trace 본문에서 UUID 전체 문자열 검색 결과는 `False`였다.

