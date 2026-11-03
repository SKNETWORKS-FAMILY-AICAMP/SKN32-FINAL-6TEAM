---
type: handoff
title: A11 체크아웃 짝짓기 실DB 기준판 대조와 관문 재검증
status: draft
domain: travel
---

# 결과와 한 일 목록

기록 시각: 2026-10-29T16:22:23 KST. 후보 DoD 실행 시각(UTC): 2026-10-29T07:07:15.667214+00:00 → 2026-10-29T07:16:28.074908+00:00.

필수 관문 **2/3 = 66.67%**, 통합·push HOLD입니다. 계약과 DoD는 기준판·후보 모두 통과하고, 보안은 기존 보호 XML 탐지 1건이 양쪽에서 같습니다. PR110 draft HOLD 유지, push·배포·운영 변경·TeamFlow 변경 0건입니다. 전체 라우팅 미결 분모는 이번에 재집계하지 않아 모릅니다.

- 이전 [인계](2026-10-29_routing-a11-resumed.md), 루트·cs AGENTS/RULE, 양쪽 wiki 색인, 개발 역할·코드 경로·숙박 접수 계약, `_coord` S4/S5/S6·기존 재개 알림과 EKS HOLD, 중단 delegation manifest를 확인했습니다. EKS·인증·다른 세션 트리는 수정하지 않았습니다. 변경 담당은 이번 Codex 세션(매니저 개발 범위), 검토는 자체 검토이며 독립 승인 없음입니다.
- 기존 후보 `C:/_proj/routingresume1029`(base `d1b06357e`)를 보존했습니다. 기준판은 기존 격리 저장소의 새 worktree `C:/_proj/routinga11base1029`입니다. 원본 Git은 변경하지 않았고, 모든 격리 Git 실행은 `GIT_OPTIONAL_LOCKS=0`·`GIT_INDEX_FILE` 제거 조건을 적용했습니다.
- A11 제품 후보는 기존 `assemble.py`의 **24줄 추가/1줄 변경**, 새 시험 파일 1개 그대로입니다. 시간 순서만으로 다른 호텔 체크아웃을 삼키던 짝짓기를 장소가 분명히 다르면 제외합니다. 같은 ID·이름 변형·같은 지점의 다른 언어 이름·장소 없는 체크아웃은 기존 연결을 유지합니다. 이번 재검증에서 추가 제품 코드 수정은 필요하지 않았습니다.
- 이전 실행기의 접속 불가 DB와 socket/psycopg 전면 차단을 검증 환경 문제로 분리했습니다. Python3.12·MinGit·PG16.15 바이너리와 Git 객체를 재사용하고, 전용 loopback PG63941에 기준/후보의 독립 DB를 만들었습니다. 실제 운영·개발 DB, 실제 모델·외부 API는 호출하지 않았습니다. mock provider와 비loopback 접속 차단은 유지하고 로컬 DB/HTTP/asyncio 소켓만 허용했습니다.
- 첫 포트 55891은 Windows TCP 예약 범위(55891–55990)여서 바인딩 거절됐습니다. 예약 설정을 바꾸지 않고 전용 63941로 해결했습니다. 실패 로그도 보존했습니다.
- CI와 동일하게 migration → `scripts.register_prompts` → `scripts.seed_travel`, `TZ/PGTZ=Asia/Seoul`, asyncio plugin을 적용했습니다. 실제 DB만 준비한 초기 대조도 별도 로그로 보존했습니다. 프롬프트 등록 전 계약은 양쪽 357/367 = 97.28%(활성 프롬프트 10건 실패), 등록 뒤 양쪽 전부 통과했습니다. 시험·스캐너·allowlist·XML을 고쳐 통과시키지 않았습니다.

## 같은 환경의 기준판·후보 대조

| 관문 | 기준판 | 후보 |
|---|---|---|
| 계약 | 367/367 = 100.00%, 실패 0 · 오류 0 · 건너뜀 0 | 367/367 = 100.00%, 실패 0 · 오류 0 · 건너뜀 0 |
| 보안 | 124/125 = 99.20%, 실패 1 · 오류 0 · 건너뜀 0 | 124/125 = 99.20%, 실패 1 · 오류 0 · 건너뜀 0 |
| DoD | 26/26 = 100.00% | 26/26 = 100.00% |
| 접수·숙박·예약·항공·아키텍처 회귀 | 1503/1505 = 99.87%, 실패 2 · 오류 0 · 건너뜀 0 | 1505/1505 = 100.00%, 실패 0 · 오류 0 · 건너뜀 0 |

DoD 하위 시험도 기준·후보 216/216 = 100%이며 node별 결과가 같습니다(`dod-comparison.json`).

회귀는 같은 새 A11 시험을 기준판에도 추가하고 같은 파일 목록으로 실행했습니다. 기준판 실패는 A11의 다른 호텔 checkout 오짝짓기 2건이며 후보에서 해소됐습니다. 그 외 새 비통과는 **0건**입니다. 예약·숙박·항공으로 이름이 식별되는 회귀 하위 집합은 기준 **188/188 = 100.00%**, 후보 **188/188 = 100.00%**입니다. 전체 목록과 node별 대조는 증거의 `*-regression-files.json`, XML, `summary.json`에 있습니다. 이 하위 집합은 전체 예약 기능 완료율이 아닙니다.

회귀의 기본 `pytest.ini`는 `-m "not live"`입니다. 양쪽 원래 설정을 유지하며 실제 모델을 부르는 245건은 선택 제외됐습니다. 실행 범위는 1505/1750 = 86%, 미실행 live 245/1750 = 14%이며 위 표의 통과율은 선택된 비live 범위입니다. live를 포함한 전체 검증 완료를 뜻하지 않습니다.

추가 탐색 `test_identity_controls.py`는 기준·후보 모두 1/2 = 50%였습니다. 같은 place_id·다른 이름·좌표 없는 checkout 연결은 양쪽 통과했습니다. 「좌표 없는 다른 호텔도 분리」라는 탐색 가정은 양쪽 실패했습니다. 실제 입력 계약의 place는 좌표를 아는 장소 또는 None이고(`assemble.py` collect 설명과 `_row`), latitude 없는 place는 `_row`에서 None으로 정규화돼 기존의 장소 없는 checkout 연결로 갑니다. 이 탐색은 기존 계약보다 넓은 가정이었으며 시험을 바꾸거나 제품 코드를 바꾸어 초록으로 만들지 않았습니다. 원문·양쪽 실패 XML을 별도 보존하고, 좌표 없는 이름까지 식별할지는 별도 요구로 남깁니다.

이전 계약 352/367 · 보안 120/125의 비통과 20건 중 19건은 DB/소켓 차단과 함께 나타났고, 동일 시험의 실DB 실행에서 통과했습니다. 이전 DoD 3/26(하위 비통과49건)도 양쪽 실DB에서 26/26으로 바뀌었습니다. 환경 영향을 A11의 제품 회귀로 세지 않습니다.

## 보존과 남은 경계

기존 후보 추적 파일 **12189/12189 = 100.00%** 해시 불변입니다. 전체 추적 XML **336/336 = 100.00%**, 이전 인계 목록 **118/118 = 100.00%** 일치합니다. 추가 후보 변경·관련 없는 파일 손상은 확인되지 않았고 `git diff --check`도 통과했습니다. 새 A11 시험은 두 트리에서 동일 바이트입니다. 기존 후보·S6·S5·wt와 보호 XML·스캐너는 편집하지 않았습니다.

보안 실패는 `test_no_tracked_text_file_leaks_infrastructure`이며 기존 `2026-10-29_st4f728-guest-logout/security-ready.xml` 탐지입니다. 보호 증거 원문·탐지 원문을 wiki에 재복사하지 않습니다. 해당 보안 HOLD를 정식으로 해결하기 전에는 통합·push하지 않습니다. 독립 승인·실제 모델·화면 수락·운영 배포를 완료한 결과가 아닙니다.

## 실행과 증거

- [실행기](C:/_proj/routinga11verify1029/verify.py): 환경값·DB명·명령·파일 목록 생성 로직. `prepared`, `regression base/candidate`로 실행했습니다. 초기 `gates`도 별도 로그·XML로 남았습니다.
- [집계](C:/_proj/routinga11verify1029/summary.json), [보존 검산](C:/_proj/routinga11verify1029/preservation.json), [실행 전 전체 해시](C:/_proj/routinga11verify1029/candidate-before.json).
- [기준 DoD](C:/_proj/routinga11verify1029/base-ready-dod/summary.json), [후보 DoD](C:/_proj/routinga11verify1029/candidate-ready-dod/summary.json), [기준 회귀](C:/_proj/routinga11verify1029/base-regression.xml), [후보 회귀](C:/_proj/routinga11verify1029/candidate-regression.xml).
- [환경 식별·스키마·프롬프트·같은 시험 해시](C:/_proj/routinga11verify1029/environment.json). 양쪽 PG16.15·Asia/Seoul·public table 89개·active prompt 10개 일치입니다. 추가 정상 ID/입력 정규화 검증 `test_resolved_identity.py`는 양쪽 2/2 = 100%이고 앞선 탐색 실패 파일은 수정하지 않았습니다.
- 이전 패치·RED·차단 실행 증거는 `C:/_proj/routingresume1029_evidence` 그대로 보존했습니다. 새 자료·DB·worktree를 삭제하지 않았습니다. 전용 PG는 검증 후 정지하며 데이터는 보존합니다. Git 객체·가상환경·바이너리 재사용, 데이터셋 복제 0건입니다.

다음 작업은 보호 XML 보안 HOLD의 정식 처리와 독립 검토입니다. 기준판도 미통합 후보 체인이므로 이번 결과를 운영 반영으로 세거나 원본으로 통째로 역복사하지 않습니다.
