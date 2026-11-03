# 원본 최소 통합 — launcher 독립분 반영 / 나머지 HOLD

## 현재 결론

2026-10-25 승인 범위 중 `C:/_proj/final_workspace`에 launcher 독립분만 반영 중입니다. D→C 이관 기록과 현재 라이팅 인계가 이 경로를 작업 원본으로 사용합니다. 별도 `파이널스페이스`는 sparse/skip-worktree 및 다른 로컬 변경이 있는 사본이므로 적용하지 않습니다.

최신 팀 develop은 정식 safe_git fetch로 확인한 `6c34589b4e34dede82e566d43b3757e127a5d5d9`입니다. 수락 후보 `d0cc4f375bd51f1d251756af4737eb1087df4f2b`와 공통 기준선 `325ba25d88c91ce97da61f2bda635e5888fe3b40`의 변경 109경로를 양 원본과 분류했습니다. 최신팀과 후보의 실제 충돌은 intake/pipeline.py, intake/review.py, cs wiki/index.md입니다. 원본과 후보에는 추가 의미충돌·물리적 부재가 있어 admin/core 전체를 부분 덮어쓰지 않습니다. 현 원본 HEAD는 최신팀으로 이동하지 않았습니다.

## 실제 적용 범위

- 시작/종료 배치의 전체 cmd 실패코드, LF/CRLF bootstrap, 기존 listener 충돌, PID/시작시각 소유 및 최종 readiness 회귀 수정.
- 대응 `tools/tests/test_local_launcher.py`, `wiki/operations/local-app-bundle.md`와 그 과거 근거 보고서 2개.
- 양 wiki·handoff·reports 및 README에 이번 부분 반영/차단 상태 기록. 기존 라이팅 기록 보존.
- backend/admin/auth 제품 파일과 private env/Next 생성물은 수정하지 않습니다. 후보 141 core·41 admin·2 auth 과거 결과는 이번 원본 통과로 승격하지 않습니다.

검증 상태: 이번 원본 launcher 회귀 실행 전이며 이 기록 뒤 실제 결과를 추가합니다. 서비스 기동/중지·DB·모델·원격 push·배포 없음.

## 정확한 차단 및 복원 근거

active profile scratch `original_minimal_integration/`의 `byte-backup-manifest.json`, `0|1/gitmeta-verified.json`, `threeway-results.json`, `threeway/<row>/local-merged|team-merged`, `RESTORE.md`를 참조합니다. conflict markers는 독립 scratch에만 있으며 원본에는 쓰지 않습니다. 관련 tracked/untracked 바이트·index·refs·flags 백업을 검증했고 적용 전 preimage를 다시 대조합니다. 원본 Git index/HEAD/flags를 변경하지 않습니다.

남은 작업: 최신팀의 intake/review 호출 계약 및 누적 후보와 원본 사용자 변경을 의미 통합한 뒤 admin/core/auth 영향 회귀. DB 소유 라이팅 세션의 검증된 endpoint/cluster/tenant 비공개 인계를 받은 뒤에만 실제 로그인·revision-aware 예약 OFF PATCH→fresh GET을 진행합니다. 지금 유효 예약 OFF 저장은 미확인입니다.

## 적용 후 실행 결과

원본 tools/tests/test_local_launcher.py를 Python 3.12로 실제 실행하여 18/18 = 100% 통과(exit 0, 47.064초)했습니다. LF/CRLF·전달바이트 전체 cmd, 실패코드, 기존 listener 비소유, readiness 실패, PID/시작시각 소유, 기존 기록 보존을 포함합니다. 시험 서비스/HTTP는 scratch 대역이며 실제 서비스 중지·기동 없음. 정확 diff/공백·보존 검산은 같은 scratch FINAL.json에 기록합니다. 관리자/core/auth 제품은 이번에 적용하지 않았으므로 기존 후보 결과를 원본 통과로 표시하지 않습니다.
