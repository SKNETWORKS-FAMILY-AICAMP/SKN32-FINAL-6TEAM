# 관리자 3300 · ops 8070 종료 원인과 복원 상태 — 2026-10-28

## 결론
- **종료 원인은 파일 삭제가 아니다.** 2026-10-28 06:02 다른 세션의 원본 직접 실행 전환 작업(프로필 scratch `original_switch_20261028/stop_prev.ps1 -Go`)이 PID·시작시각·명령줄을 확인한 뒤 `taskkill /T /F`로 3888·13632·6896·26236을 종료했다. 그래서 Hermes 핸들 `proc_3d18708d8ff1`·`proc_ab9bdbb87b03`이 exit 1로 끝났다. 결과 파일 기록 시각은 06:02:46/47이고 `stop_prev_go.log`와 맞는다. 관련 기록은 같은 폴더의 `ROLLBACK.md`와 `prev_servers_rollback.json`이다.
- **파일 삭제는 별개로 일어났다.** 10-27 19:46 텔레그램 세션 `20261026_055053_ce47d8ba`가 수동으로 scratch를 정리했다(`scratch/_cleanup3b.py`, 목록 `_cleanup_ok.txt` 10행 `admin-testmode-20261025`). 그때 `launch.py`·로그와 runtime 파일이 지워졌다. `runtime/final_project_cs`는 실행 중인 ops의 cwd라서 빈 폴더로 남았다. 10-27 작업폴더 캐시 정리(`2026-10-27_workspace-cache-cleanup`)는 scratch를 제외했고, Hermes 자동 정리 로그(`logs/scratch-prune.log`)에도 해당 항목이 없다. 그 뒤 ops는 메모리에 올라간 상태로만 06:02까지 동작했다.
- 이전 admin의 불변 빌드(`local_admin_3300_v2/repo`)도 지금은 없다. 따라서 10-25 구성과 같은 바이트로 재기동하는 것은 불가능하다.

## 현재 실행 중(06:03~, 전환 세션 소유, 이번 작업에서 기동·종료 0)
| 역할 | 포트 | listener PID(부모) | 코드 | 확인 |
|---|---|---|---|---|
| ops | 127.0.0.1:8070 | 26564 (15464 venv) | 원본 `C:/_proj/final_workspace/final_project_cs` 작업트리(HEAD efeb873 + 미커밋 통합) | GET /health 200 |
| admin | 127.0.0.1:3300 | 32620 (6576, `next dev`) | 같은 원본 `frontend/apps/admin`, NEXT_DIST_DIR=.next-batch | GET / 200, /settings 200 |

- 이 서버들을 띄운 `run_and_hold.ps1`은 "gone"을 출력하고 끝났지만, 두 서버는 그대로 동작한다. 그래서 이 서버들에는 Hermes 핸들이 없다.
- 부작용: `next dev`가 원본 `frontend/apps/admin/tsconfig.json` include에 `.next-batch/...`를 추가했다(Next 로그에 기록됨).
- 운영 3100·8042·5433은 변경하지 않았다.

## 4fee819(role-manager) 대비 스키마
- 4fee819의 migration 파일은 116개이고, 원본 작업트리에는 103개와 pending이 있다. 4fee819에만 있는 파일은 14개다.
- 그중 7개 파일의 대표 객체 10개를 acop_cs(5433)에서 읽기 전용(`default_transaction_read_only=on`)으로 확인했다. **10/10 = 100% 존재**한다(intake_alternatives, trip_archives(_marks), lg_offer_shown, lg_core_place_link, intake_backups, activity.ac_live_status, trip_intakes.screened/survey_plan/reopen_trip_id). 표본 결과로는 migrate가 필요 없어 보인다. 전수 비교는 하지 않았고, migrate는 실행하지 않았다.
- 원본 HEAD efeb873과 4fee819는 1,077커밋 차이가 난다. 지금 서빙하는 코드는 4fee819가 아니다.

## 복원 준비물(기동하지 않음)
- `프로필 cache/scratch/admin-restore-20261028-0612/`: `launch.py`(ops|admin, 127.0.0.1만, 포트를 이미 쓰고 있으면 rc=2로 거부, 비공개 env에서 DB URL만 프로세스 env로 주입, `--repo`로 코드 위치 지정), `schema_probe.py`와 결과 `.out.json`, `dryrun.log`(두 역할 모두 portBusy로 rc=2).
- 위치 제안: `cache/scratch`는 24시간 자동 정리와 다른 세션의 수동 정리 대상이다. 실행 중인 런처와 빌드는 정리 대상이 아닌 프로필 `workspace/services/<이름>/`(또는 `C:/_proj/final_workspace/.backup`)에 두는 것이 좋다. scratch 정리 스크립트 keep 규칙에 "현재 listener의 cwd/명령줄이 가리키는 폴더"도 넣어야 한다.

## 남은 일
- 전환 세션의 인계 문서가 아직 없다. 이 서버의 소유자를 인계 문서에 확정해야 한다.
- 4fee819로 서빙하려면 새 export와 admin build를 만든 뒤 소유자가 교체해야 한다(이번 작업 범위 밖).
- 테스트 모드(`testing.plan_test_mode`)는 DB 설정이다. 이번 작업에서 읽기·쓰기를 하지 않았으므로 미검증이다.
