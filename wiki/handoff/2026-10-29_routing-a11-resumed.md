---
type: handoff
title: 중단된 S6 A11 숙소 체크아웃 짝짓기 재개
status: draft
domain: travel
---

# 결과와 한 일 목록

숙박 회귀 **16/16 = 100%**. 수정 후보는 로컬 보존이며 **필수 관문 0/3 = 0% 통과, 통합 HOLD**입니다. PR110 draft HOLD를 유지합니다. push·배포·운영 쓰기·TeamFlow 변경은 0건입니다.

- 루트 AGENTS, cs AGENTS/RULE, 양쪽 wiki 색인, handoff 색인, 개발 역할과 숙소 접수 코드를 확인했습니다. guguroute profile `cache/delegation/live/deleg_ebfdaed6/manifest.json` 및 task-0/task-1 부분 기록, `_coord` S4/S5/S6와 EKS 관련 알림을 읽었습니다. 두 이전 작업자는 interrupted입니다.
- EKS 작업은 `C:/_proj/eksremain3_1029`에 bisect·진단이 남았으나 이번에 실행·수정하지 않았습니다. 운영 reader fatal 미확정, PR110 draft HOLD는 기존 경계 그대로입니다.
- S6의 미완료 A11을 선택했습니다. 다른 호텔 체크아웃 줄이 먼저 나오면 현재 숙소의 끝으로 합쳐져 사라지고, 실제 같은 호텔 체크아웃은 남는 오류입니다. 새 트리에서 기존 코드에 새 시험만 추가하여 **2/5 실패·3/5 통과**를 재현했습니다.
- 새 격리 worktree `C:/_proj/routingresume1029`, branch `routing-resume-1029`, base `d1b06357e`를 사용했습니다. 원본 Git 디렉터리가 아닌 기존 격리 repo의 worktree이며 Git 객체·가상환경을 재사용했습니다. 삭제·새 데이터셋 복제는 하지 않았습니다. 일반 git.exe 실행 접근 거부로 기존 MinGit을 사용했고 GIT_OPTIONAL_LOCKS=0, GIT_INDEX_FILE 제거 조건을 지켰습니다.
- S6의 미커밋 `assemble.py` 후보와 새 시험을 새 트리에 가져왔습니다. 체크인/체크아웃 장소가 분명히 다르면 짝에서 제외합니다. 같은 place_id·이름 변형·좌표상 같은 장소·장소 없는 체크아웃은 기존 연결을 유지합니다. 제품 변경은 assemble.py 24줄 추가/1줄 변경이며 시험 파일 1개를 추가했습니다. S6/S5/wt 원본은 수정하지 않았습니다.

## 실행 증거와 한계

증거 위치: [counts](C:/_proj/routingresume1029_evidence/counts.json), [패치](C:/_proj/routingresume1029_evidence/candidate.patch), [새 시험 패치](C:/_proj/routingresume1029_evidence/new-test.patch), [XML 보존](C:/_proj/routingresume1029_evidence/xml-preservation.json). 로컬 로그와 XML에는 기존 보안 탐지 내용이 들어갈 수 있어 wiki에 원문을 복사하지 않았습니다.

실행기는 기존 Python3.12 환경을 재사용하며 mock provider, 접속 불가 loopback DB, socket/psycopg 차단, 바이트코드·pytest cache 비활성화를 적용했습니다. 외부 API·실제 모델·운영 DB는 호출하지 않았습니다. runner.py/sitecustomize.py에 조건을 보존했습니다.

| 실행 | 실측 결과 |
|---|---|
| 새 시험 기존 코드 RED | 3/5 = 60%, 실패 2 |
| 새 시험+기존 숙박 3파일 | 16/16 = 100% |
| tests/contract 전체 | 352/367 = 95.91%, 실패 12·오류 3 |
| tests/security 전체 | 120/125 = 96%, 실패 2·오류 3 |
| verify_dod_v11 최종 | 3/26 = 11.54%, 나머지 23 항목 실패 |
| 기존 tracked XML SHA256 | 118/118 = 100% S6와 일치 |

명령은 `python -B runner.py <숙박4파일> tests/contract tests/security -q -p pytest_asyncio.plugin -p no:cacheprovider --junitxml=.../validated.xml`입니다. 숙박4파일은 `test_intake_stay_other_hotel_checkout.py`, `test_intake_agent_checkout_stay.py`, `test_intake_stays.py`, `test_intake_stay_morning.py`입니다. 별도 focused.xml도 16/16 통과했습니다. `git diff --check` 통과입니다.

DoD는 동일 격리 조건에서 `python -B -m scripts.verify_dod_v11 --evidence-dir .../dod-with-async`로 실행했습니다. 첫 실행의 asyncio 플러그인 누락을 확인해 `PYTEST_ADDOPTS=-p pytest_asyncio.plugin -p no:cacheprovider`를 지정하여 다시 실행했습니다. 첫 결과도 `dod/`에 보존했습니다. 최종 하위 시험은 167/216 = 77.31%, 실패 4·오류 45이며 49건 모두 차단된 DB/네트워크 조건을 포함합니다. 이 실행은 실DB 관문 통과 증거가 아닙니다.

계약·보안 합계 비통과 20건 중 19건은 차단된 DB/네트워크 조건을 포함하고, 1건은 기존 tracked-text 보안 탐지입니다. 탐지 파일은 기존 `2026-10-29_st4f728-guest-logout/security-ready.xml`입니다. 해당 XML 재작성·삭제·예외 추가·스캐너 약화는 하지 않았습니다. 이전 보고와 같은 차단 위치지만 동일 기준판 전체 재실행은 하지 않았으므로 새 실패 0이라고 주장하지 않습니다. 오입력한 시험 파일명으로 collection 실패한 최초 실행도 green-gates.log/xml에 보존했습니다.

## 다음 담당자

1. 필수 관문과 기존 XML 보안 HOLD가 정식으로 해결되기 전에는 통합·push하지 않습니다. 보호 증거를 고쳐 통과시키지 않습니다.
2. 담당자가 A11 후보를 검토하고 승인된 격리 DB 환경에서 계약·보안·DoD 전체를 재검증해야 합니다. 자체 검증이며 독립 승인 없음, 실제 LLM·화면 수락 없음입니다.
3. 기존 S5 `d1b06357e`도 후보 체인입니다. 이번 후보를 운영 완료로 세거나 원본으로 역복사하지 않습니다. 전체 라우팅 미결 분모는 재집계하지 않아 모릅니다.
4. TeamFlow 작업을 만들 때 role-manager 담당 `3rd_team_4_be`를 유지합니다. develop/main/EKS 변경과 PR110 HOLD 해제는 이번 범위가 아닙니다.
