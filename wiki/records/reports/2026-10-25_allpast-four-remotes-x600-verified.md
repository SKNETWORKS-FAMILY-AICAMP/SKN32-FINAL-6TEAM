# 2026-10-25 전체 과거 날짜 가드 — 4개 원격 반영·x600 실서버 확인

확인 시각: 2026-10-25 21:55 KST 전후. 근거는 원격 Git 재조회와 x600 공개 API 실호출이다.

## 결론

- 사용자 요청 "일부만 과거면 통과, 전부 과거면 차단"을 팀/개인 `role-manager`·`develop` 4개 원격에 반영했다. **4/4 = 100%**
- x600 서버는 `role-manager`를 자동 배포한다. `08b99597`이 21:40~21:41에 배포 완료(`done`)됐고, 실서버 확인 **3/3 = 100%** 통과했다.
- 로컬 실행 서버(localhost/LAN v7)와 원본 작업 폴더에는 아직 반영되지 않았다. 검색 결과 0건이며, 반영하려면 API 재시작 승인이 필요하다.

## 원격 반영 (부모가 `git ls-remote`로 직접 재조회)

| 대상 | SHA | 부모 | 검증 |
|---|---|---|---|
| 팀 develop | `d2ab93a65e127e03154af535654bada0d9383d90` | `beb726b9…` | 로컬 전체 관문 9,372 통과/173 skip, 부모 재실행 35/35, GitHub CI develop 2/2 success(9,420 통과) |
| 팀 role-manager | `08b99597633a9d1e8e858bc03705314b927a6775` | `6410f754…` | 21/21, 선택 관문 9,244 통과/173 skip(실패 0). role-manager에는 CI가 없다(10-13 결정) |
| 개인 role-manager | 같은 `08b99597…` | 같음 | 같음 |
| 개인 develop | `d8366bbf0bb5e875cc4cc116dd139ed62c08e990` | `5d52dfbf…` | 17/17, 전체 관문 9,112 통과/173 skip. GitHub check/run 0건이라 CI는 미확인 |

- 작성자는 실제 인증 계정 `roroblack`의 GitHub noreply 주소다. 전역 Git 설정은 바꾸지 않았다.
- 각 브랜치는 기존 코드를 보존한 채 hotfix 11경로만 3-way 적용했다. 다른 브랜치를 merge하거나 force push하지 않았다.
- 브랜치별 시험 수가 다르다(35/21/17). 그 브랜치에 없는 시험 파일은 가져오지 않았기 때문이다.

## x600 실서버 확인 (`tripilot.devroro.click`, 21:53 KST)

| 경우 | 결과 |
|---|---|
| `POST /v1/web/trips`, 전부 과거(10/20·10/21) | 422 `itinerary_infeasible`/`all_dates_in_past`, 여행 생성 0건 |
| 계획 접수, 전부 과거(10/20·10/21) | review에 "모든 일정이 오늘 이전이에요" 표시, ready=false |
| 계획 접수, 과거+미래(10/24·10/27) | 해당 문구 없음, ready=true |

- 부수 기록: 시험 게스트 4개와 미등록 접수 3건이 생겼다. 등록된 여행은 0건이며, 게스트 7일 자동 정리 대상이다.
- 시험 스크립트: Hermes scratch `x600_allpast_intake_check.py`, `x600_allpast_check.py`.

## 남은 일

1. 로컬 v7 API에 hotfix 3파일을 반영하고 재시작한다(사용자 승인 필요).
2. 개인 develop의 CI는 실행 기록이 없어 미확인이다.
3. 별도 후보(temporal/F02/Comment9/I06)는 서빙 교체 보류 중이다. I06 booked-only 오고정 수정은 Opus 담당자에게 맡겼다(`deleg_38b99b1d`).

증거 폴더: Hermes scratch `allpast-hotfix-20261025-2005/` — `ROLE_DELIVERY_RESULT.json`, `PERSONAL_DELIVERY.json`, `parent-confirm-final.xml`, `latest-complete-gate.xml`, `role-full-final.xml`, `personal-final-gate.xml`.
