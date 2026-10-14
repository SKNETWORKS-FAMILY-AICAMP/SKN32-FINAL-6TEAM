# 이동 시험 — 앱 폴더만 있는 실행 환경에서도 통과 (Claude, 2026-10-14)

commit 세션이 메모리를 아끼려고 앱 폴더(`final_project_cs`)만 임시 폴더에 풀어 이동 시험을 돌리자 9호선 급행 시험 4건이 실패했습니다. 코드 결함이 아니라, 그 시험이 저장소 맨 위 `datasets/mobility/scripts/reduce_75.py`(git 에 들어 있음)를 실행하는데 앱 폴더만 있으면 그 파일이 없어서였습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 앱 폴더만 있는 환경 재현(작업 폴더 밖 임시 폴더, CI 더미 환경 변수) | 고치기 전 실패 | 9호선 급행 4건 |
| 9호선 급행 시험 — 스크립트가 없으면 이유를 남기고 건너뜀 | 고침 | 1/1 |
| 앱 폴더만 있는 환경 이동 시험 | 실패 0 | 1,423 통과 · 127 건너뜀 · 0 실패 |
| 저장소 전체가 있는 환경 | 그대로 돎 | 9호선 급행 5/5 통과 |

- 고친 파일: `tests/unit/travel/mobility/test_reduce_line9_express_preservation_v1.py` — `pytestmark = pytest.mark.skipif(not SCRIPT.exists(), …)`. 건너뛴 시험은 통과로 세지 않습니다.
- GitHub CI(`ci-main.yml`)는 저장소 전체를 받으므로 이 시험이 그대로 돕니다. CI 설정은 바꾸지 않았습니다.
- 재현 스크립트: [ci_app_only_run.sh](ci_app_only_run.sh). 처음엔 임시 폴더를 작업 폴더 안에 만들어, 시험이 위로 올라가 실제 이동 자료를 찾아 쓰고 이 PC 메모리 부족 오류 2건이 섞였습니다([apponly-before-in-repo-tmp.xml](apponly-before-in-repo-tmp.xml)). 작업 폴더 밖으로 옮겨 다시 쟀습니다([apponly-after.xml](apponly-after.xml)).
- 남은 한계: 이동 자료가 없는 환경(GitHub CI 포함)에서는 실제 자료가 있어야 도는 이동 시험 127건(예시 일정 정답 비교 등)이 건너뛰어집니다. 그 시험들은 이동 자료가 있는 이 PC 에서만 돕니다.
- 백업: `final_project_cs/_backup/2026-10-14_ci_app_only/`.

mock 서버 시험(화면 반응): 해당 없음. 실서버 확인(서버 응답): 해당 없음(시험만 바꿈).
