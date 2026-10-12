# 원본 수집 예산 제한 검증 — 2026-10-09

원본 수집을 소스별 하루 2회·월 62회 시도와 공용 사용량 20% 중단선으로 제한했다. 외부 API를 쓰지 않는 안전 시험과 실제 로컬 개발 DB 시험을 구분한다.

## 실행과 출력

`final_project_cs`에서 작업 폴더 안의 새 임시 경로를 지정했다.

```powershell
python -m pytest var/alert-snapshots/verify_runner.py -q --basetemp <새 임시 경로> --tb=short
python -m pytest var/alert-snapshots/verify_budget_db.py -q --basetemp <다른 새 임시 경로> --tb=short
python -m py_compile scripts/capture_alert_scenarios.py ../.tmp/alert-snapshots/collect_x600.py
```

실제 출력:

```text
..........                                                               [100%]
10 passed in 1.53s
....                                                                     [100%]
4 passed in 2.24s
```

두 시험 종료 코드는 0이다. 첫 시험 종료 처리에는 `pyreadline3`의 Windows 핸들 경고가 뒤따랐다. 구문 검사는 출력 없이 종료 코드 0이다.

10개 안전 시험은 기존 6개에 한도 미확인 시 외부 전송 차단·캐시 재사용, 서로 다른 제한기의 호출 횟수 합산, DB 오류 시 호출 차단, 제한 설정 필수 및 기존 더 작은 몫 유지 검사를 더했다. [시험 코드](../../../../var/alert-snapshots/verify_runner.py).

4개 실제 DB 시험은 새 시험 카운터만 쓰고 지웠다. 별도 제한기 재생성 후에도 2회에서 중단, 공용 2/10 = 20%에서 수집 중단 및 일반 호출 8/10 보존, 동시 8개 중 2개만 허용, 하루 줄이 바뀌어도 월 제한 유지가 통과했다. 외부 경보 API와 고객 데이터는 쓰지 않았다. [DB 시험 코드](../../../../var/alert-snapshots/verify_budget_db.py).

## x600 서버의 cs 프로젝트 서버 확인

읽기 전용 예산 조회 시각은 11:10:42(한국 시간)다. ITS 공용 하루 사용량은 1/1,000 = 0.1%였다. 제공처의 월 초과 표시가 있었다. 우리 DB의 ITS 월 상한은 미설정이며 전체 제공처 잔여량을 이 값으로 계산하지 않는다. [개인 조회 원본](../../../../../.tmp/alert-snapshots/budget_probe_20261009.json).

새 제한을 적용한 원본 수집:

```powershell
python -m scripts.capture_alert_scenarios --archive-only
```

실제 출력:

```json
{"run_id": "2026-10-09_111600_e183aeb5", "status": "archived_partial", "snapshots": 0, "should_notify": true}
```

종료 코드 1이다. ITS의 기존 제공처 차단 때문에 부분 수집이다. [원본·실행 조건](../../../../var/alert-snapshots/real/2026-10-09_111600_e183aeb5/)의 `collection.json`에는 적용 몫 0.2·하루 2회·월 62회가 남아 있다. 기상특보·지진·UTIC·지하철 공지의 새 HTTP 응답은 각 1개, 재난문자는 캐시, ITS 새 HTTP 응답은 0개다.

11:17:37 예산 DB 조회에서 새 시도가 있었던 5개 소스의 수집용 카운터는 각 하루 1/2, 월 1/62였다. ITS도 실제 전송 전에 공용 예산이 거절했으므로 보수적으로 수집 시도 1회다. 캐시만 읽은 재난문자는 새 시도가 없어 수집용 카운터 줄을 만들지 않았다. [개인 카운터 조회 원본](../../../../../.tmp/alert-snapshots/snapshot_usage_20261009_111737.json).

예약 갱신 도구는 `automationId=tripilot, mode=update, status=ACTIVE`를 반환했다. 저장 파일에서도 활성 상태·매일 오전 9시·같은 채팅·세 제한값이 모두 유지된 것을 확인했다. 접수·대체안·브라우저·여행·고객 알림은 실행하지 않았다.

설정된 한도의 80%를 수집이 소비하지 않도록 한 중단선이지, 다른 기능의 사용량까지 제한한 결과는 아니다. 제공처 월 한도가 미확인인 소스의 실제 월 잔여율을 보장하지 않는다. 이 경우 수집 전용 월 62회 상한과 제공처 초과 차단을 적용한다.
