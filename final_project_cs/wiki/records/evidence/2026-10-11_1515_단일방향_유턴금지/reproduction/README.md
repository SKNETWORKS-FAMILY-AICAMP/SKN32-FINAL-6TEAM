# 이번 실행의 재현 자료

원래 실행 위치는 워크스페이스의 `.tmp/mobility_complete_20261008/`입니다. 이 폴더의 스크립트는 그 위치에서 실행한 원문을 그대로 보존한 사본입니다. 직접 실행하면 부모 폴더 계산이 달라지므로 원래 위치와 같은 깊이의 **새 격리 워크스페이스 사본**에 옮겨 사용합니다.

`prepare`와 `publish`는 기존 파일을 백업하고 문서를 수정하며, `audit_uturn`은 로컬 회전 자료를 교체합니다. 현재 운영 자료나 이미 생긴 evidence에 다시 실행하지 않습니다. 감사 전 상태는 백업 명세의 회전 파일이며, 감사 후 상태는 `turn_restrictions_extended_v1.json`입니다. 출력 폴더도 새 이름으로 바꾸고 `open('x')`의 기존 출력 보호를 유지합니다.

회귀 시험만 다시 실행할 때는 저장소 루트에서 아래 명령의 임시 폴더·XML 이름을 아직 없는 새 이름으로 바꿉니다.

```powershell
python -m pytest tests/unit/travel/mobility/test_same_way_uturn_policy_v1.py tests/unit/travel/mobility/test_car_turn_restrictions_v1.py tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py tests/unit/travel/mobility/test_graph_router.py -q -k "not real_graph" --basetemp=../.tmp/mobility_uturn_new_check --junitxml=../.tmp/mobility_uturn_new_check.xml
```

원래 시험은 외부 연결을 차단한 `test_uturn_related_20261011.py`로 실행했습니다. 실제 인자와 종료 코드·연결 시도 수는 상위 폴더의 `related-command.json`, 원문은 `related-v1.log`입니다. 공개 API 호출 없이 저장 도로 자료만 사용합니다.
