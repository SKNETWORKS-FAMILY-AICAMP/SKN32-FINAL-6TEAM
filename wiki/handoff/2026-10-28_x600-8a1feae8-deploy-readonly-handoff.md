# 인계 — role-manager `8a1feae8f` x600 자동 배포 읽기 전용 확인(중단 · 이관) (2026-10-28)

- 상태: **사용자 지시로 「라우팅 에이전트 구현」 세션에 이관하며 중단.** 배포 · 수정 · 서비스 변경 · 고객 쓰기 0. 원인 조사 미완.
- 기록 시각: 2026-10-28 03:24 KST(확인은 그 직전).
- **해소(2026-10-28 03:37 KST 추가):** 「미배포」는 시간차였다. 03:25:25에 시작했고 03:29:39에 `반영 완료 8a1feae8fc`가 찍혔다. board `deploy:8a1feae8fc-1793125528`는 phase done이다. api의 `ACOP_DEPLOYMENT_VERSION=8a1feae8fc`. 실서버 확인은 `final_project_cs/wiki/records/reports/2026-10-28_x600_8a1feae8_실서버확인.md`.

## 확인된 것(실측)
- 원격: `git ls-remote` 로 origin · team `role-manager` 둘 다 `8a1feae8fc71a18f160e5699e631e2dfdfeeb0c7` (푸시됨).
- x600 공개 `/health`: HTTP 200(0.16초) — **실행 중**일 뿐, 이 커밋의 배포 증거가 아니다.
- 공지 게시판 `GET /v1/web/support/notices/board`: 가장 최근 배포 항목이 `deploy:93c7ba8ecf-1793095010`(10-27 18:56 시작 · 18:59 done). **`8a1feae8f` 배포 항목 없음.**
- `/root/tripilot-docker/deploy.log` 끝 40줄(SSH 키 로그인 · 읽기만): `93c7ba8ecf` 이미지 빌드 · admin 재생성 · 이미지 정리로 끝남. `8a1feae8f` 시작/반영 완료/마이그레이션 실패 줄은 **그 범위에 없음**.
- 결론(확인 시점): **x600 실행 판 = `93c7ba8ecf`, `8a1feae8f` 는 배포되지 않음(배포 미시작 또는 진행 중 — 구분 못 함).**

## 확인 못 한 것
- 미배포 원인: deploy.log 전체 결과 줄 grep · `state/`(bad_sha · deployed_sha · lock) · 타이머 · 실행 중 deploy 프로세스 조회는 **미실행**. 준비만 한 읽기 전용 스크립트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/x600-8a1feae8-readonly/check.sh` (실행: `ssh -i ~/.ssh/id_ed25519_x600 Yeon@192.168.0.8 "wsl -u root -e bash -s" < check.sh`, compose/env 덤프는 안 읽음).
- 「2분쯤 걸릴 수 있어요」 안내 게스트 화면 readback: **미실행**(배포 전이라 화면에 반영됐을 근거 없음).
- 푸시 시각 대비 경과 시간 미확인 — 자동 배포는 보통 푸시 후 3~5분.

## 이슈
- `python tools/safe_git.py` 가 이 셸에서 `PermissionError: [WinError 5]`(git 프로세스 생성 거부)로 실패 → 원본 저장소 조회는 `GIT_OPTIONAL_LOCKS=0 git ls-remote` 만 사용(로컬 상태 변경 0).

## 디스크
- 새로 만든 것: 위 scratch 폴더의 `check.sh` 1개(1KB). 삭제한 것 0.

## 재개 확인 — 「2분쯤」 안내 반영 여부 (2026-10-28 10:26~10:35 KST, 읽기 전용)
- 결론: **미반영이 아니다.** 「2분쯤」 문구는 x600에 반영돼 있다. 문구 커밋은 로컬 후보 `72c6a718f`(push 0)가 아니라, cherry-pick된 `02461e7a1`로 들어갔다. `02461e7a1`은 `8a1feae8fc`와 현재 HEAD `efc6fca47c`의 조상이다. 「미반영」으로 보인 원인은 두 가지다. ① 03:24 확인 때는 8a1feae8 배포가 시작되기 전이었다(03:25 시작 · 03:29 완료). ② `72c6a718f`가 어느 배포 커밋에도 없는 것은 같은 변경이 다른 SHA로 들어갔기 때문이다.
- 원격: origin · team `role-manager` = `efc6fca47c76…`. 8a1feae8 뒤로 4fee819c · e78e038b · 1bc49795 · bdb48ffc · efc6fca4가 모두 「반영 완료」됐다(deploy.log). board 최신 항목은 `deploy:efc6fca47c-1793148358`(09:45~09:47)이고 phase는 done이다.
- 서버: `state/deployed_sha`와 `current_tag`는 efc6fca47c다. `bad_sha`는 비어 있다. lock을 잡은 프로세스와 실행 중인 deploy 프로세스는 0이다. `tripilot-autodeploy.timer`는 active이고 5분 주기다(마지막 실행 10:25:56, exit 0). api 이미지는 `tripilot-api:efc6fca47c`(3f1a80002ec1), web 이미지는 `tripilot-web:efc6fca47c`(bd2faabc9160)다. api의 `ACOP_DEPLOYMENT_VERSION`은 efc6fca47c다. 컨테이너는 모두 healthy다. 공개 `/health`는 200이다.
- 공개 번들: 7개 경로의 JS 19개를 읽었다. 「2분쯤」은 `3w1dqeo9dwa_r.js`에 2건 있다(이용 방법 안내 · 「사진 한 장은 2분쯤 걸릴 수 있어요」). 「1분쯤」은 0건이다. plan-check 화면 청크는 지연 로딩이라 이번에 다시 읽지 않았다. 03:37의 8a1feae8 실서버 확인에서 읽기 화면 스크린샷으로 이미 통과했다(`final_project_cs/wiki/records/reports/2026-10-28_x600_8a1feae8_실서버확인.md`).
- 서비스 재시작 · 설정 변경 · 고객 쓰기는 0이다. 서버에서는 check.sh, docker ps · image ls · printenv, systemctl status, deploy.log 읽기만 실행했다.
- 참고: GitHub compare API는 404를 반환했다(비공개 저장소). 조상 관계는 로컬 `GIT_OPTIONAL_LOCKS=0 git merge-base --is-ancestor`로 확인했다(fetch 0).
