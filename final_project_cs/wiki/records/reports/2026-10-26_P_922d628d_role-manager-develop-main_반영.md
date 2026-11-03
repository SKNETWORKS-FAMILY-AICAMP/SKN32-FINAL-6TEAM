# 묶음 P — role-manager 922d628d(호텔 종류 · 계획 읽기 실패 화면 핫픽스) 를 develop · main 반영 (2026-10-26 13:20~13:50 KST)

## 결론
- 기준 커밋 = role-manager **922d628df9dd**(13:30 tip, push 직전 ls-remote 재확인). 사용자 핫픽스 두 건 모두 포함:
  - 호텔이 등록 뒤 액티비티로 바뀌던 결함 → `e3f9671d1`(숙소 후보 고르기가 종류를 활동으로 덮어쓰던 것)
  - 계획 읽기 실패(fatal)인데 「다 읽었어요」가 뜨던 결함(8/9줄) → `922d628df`
- 팀: develop **922d628d**(ff) · main **b4c2847e**(PR #104 merge 커밋, 부모 a50165d1 · 922d628d). 개인: develop **1c084df0**(병합). 개인 main 미변경. force push 0회, 보호 규칙 우회 0회.

## push 전후 SHA
| 저장소 | 브랜치 | 전 | 후 | 방식 |
|---|---|---|---|---|
| 팀 | role-manager | (다른 세션 push) | 922d628df9dd | P 는 push 안 함 |
| 개인 | role-manager | – | 922d628df9dd | 이미 같음, P 는 push 안 함 |
| 팀 | develop | 16d6b00ab240 | **922d628df9dd** | fast-forward (13:30:0x) |
| 개인 | develop | ce6a817181cc | **1c084df0da7d** | fast-forward(병합 커밋 = 개인 develop + 922d628d, 충돌 0) |
| 팀 | main | a50165d110ed | **b4c2847ec317** | PR #104 merge(13:41:06, 계정 roroblack, 필수 검사 3 통과 뒤) |
| 개인 | main | b0485d05fe18 | 변경 없음 | 공통 조상 없음 → 사용자 결정 대기 |

- 개인 develop 병합 확인: `git diff 922d628d 1c084df0 -- final_project_cs/app final_project_cs/tests final_project_cs/frontend .github` = 빈 diff. 차이는 앞 K 병합 때 보존한 wiki 4파일 +107줄뿐. 작업트리 `cache/scratch/integ-P-20261026/pdev`(원본 작업트리 미사용).
- 팀 main 과 922d628d 의 final_project_cs 차이 = main 쪽 AWS CD 4파일(기존 main 전용) 뿐.

## develop · main 에 들어간 패치 (16d6b00a 이후, role-manager 순서)
| 커밋 | 세션 | 내용 |
|---|---|---|
| e43e99681 | H(호텔) | 호텔 줄 — 숙박·활동·식사 종류 확인 질문, 숙소 후보 고객 선택(먼저 채우기 안 함), 체크인 없는 숙박 |
| 8dfee1493 | H | 호텔 질문에 후보(최대 3곳) 동봉 + e2e 5건 새 계약 |
| a620e25a3 | (intake-reader) | 로컬 timeout 뒤에도 유료 대체 시간 남김(reader 상한) |
| 738d303fe | (intake-reader) | 모델이 빠뜨린 시각 있는 줄 이어 읽기 — locked 유지 |
| 9597e174e | (채팅) | trip_desk Case 도 model_path 기록 |
| 626646cf3 | (채팅) | 「실내를 야외로」가 방금 바꾼 식당이면 활동 되묻기 |
| 3ebee4a56 | (채팅) | 「다른 안」 선택지는 모델 없이 고른 안으로 |
| 40231a565 | (보안) | 바깥 API 키 로그·진단·예외 글 가림(INV-CS-SEC-016) |
| e3f9671d1 | H | ★숙소 후보 고르기가 종류를 활동으로 덮던 것(호텔→액티비티) + e2e 2건 대상 고정 |
| 922d628df | N(읽기 화면) | ★계획 읽기 실패면 질문 붙잡기 대신 실패 화면 |

## 실패 분석(기준 결정)
- e43e9968 CI(main) 40265004266: 5 failed(test_intake_stay_lines ×2 · candidate_kinds · lodging_recommendation · lodging_retry) — 계약 변경(숙소 먼저 채우지 않음)에 e2e 미갱신. 시험 쪽, 운영 영향 없음(M 분석). 8dfee149 에서 고침.
- 8dfee149 CI(main) 40267184818: 12729 passed · 2 failed(lodging_recommendation · lodging_retry, `title=='호텔 조식'` 으로 줄을 골라 0개 — 실제 제목 '호텔'). 시험 쪽. e3f9671d 에서 고침.
- e3f9671d CI(main) 40268461317: **12789/12789 = 100%** → 심각한 실패 없음. 922d628d 는 그 위 web 4파일 + wiki 2파일.

## CI 결과 (실측)
| 대상 | run | 결과 | 시험 수 |
|---|---|---|---|
| role-manager e3f9671d CI (main) | [40268461317](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40268461317) | 성공 | 12789 passed · 0 failed · 466 skipped = 100%, 아키텍처 170/170 |
| develop push CI (develop) 922d628d | [40269397843](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40269397843) | 성공 | 10297 passed · 0 failed = 100% |
| develop push CI (web) 922d628d | 40269397816 | 성공 | – |
| PR #104 CI (main) | [40269421992](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40269421992) | 성공 | 12814 passed · 0 failed · 466 skipped = 100%, 아키텍처 170/170 |
| PR #104 CI (web) | 40269421999 | 병합 시점 진행 중(필수 아님) | – |
| main push CI (main) b4c2847e | [40270328526](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40270328526) | 성공(13:50) | 12814 passed · 0 failed · 466 skipped = 100%, 아키텍처 170/170 |
| main push CI (web) b4c2847e | 40270328504 | 13:51 진행 중 | – |
| main CD (AWS) b4c2847e | 40271109330 | 13:51 진행 중(main CI 성공 뒤 자동) | – |

- main 보호: 필수 검사 = `ruff (F·E9)` · `전체 시험 (live 제외)` · `Docker 빌드`. auto-merge 는 저장소 설정(enablePullRequestAutoMerge)상 불가 → 필수 검사 통과(13:41:00) 직후 일반 merge. 소요: PR 생성 13:31 → 병합 13:41(약 10분, 전체 시험 8분 24초).
- 개인 저장소 Actions 는 결제 한도로 미실행(앞 기록). 개인 develop 은 코드가 922d628d 와 바이트 동일.

## 남은 일
1. 개인 main 처리 결정(앞 K 보고서 선택지 a/b/c).
2. main push CI(web) 40270328504 · CD(AWS) 40271109330 결과 확인(13:51 진행 중).
3. x600 자동 배포 상태 확인(이 묶음에서 확인 안 함).
