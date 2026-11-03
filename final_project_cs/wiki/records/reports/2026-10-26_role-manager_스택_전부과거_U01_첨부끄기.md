# role-manager 스택 — 전부 과거 문구·계획 담기 가드·U01 미지원 안내·첨부 끄기 (2026-10-26)

## 결론

- 팀·개인 `role-manager` `376f2a67`(시험 시계 고정 포함, 양쪽 ls-remote 확인) 위에 커밋 5개를 쌓은 로컬 브랜치 `stack/rm-allpast-u01-extras-20261026`을 만들었습니다. tip은 `d3d0a06377b4330c09bf857348b084ff03f5d5ac`입니다. push는 하지 않았습니다(원격 0/2, x600 미반영, 로컬 8042/3100 미반영).
- 처음에는 `da4ccd97` 위에 시계 고정 커밋까지 6개로 쌓았습니다. 그 뒤 role-manager가 `376f2a67`로 진행됐고, 이 커밋의 변경 줄은 제 시계 고정 커밋과 같았습니다. 그래서 시계 고정 커밋은 빼고 재기준했습니다. 재기준한 tip 트리는 처음 6개 스택 tip 트리와 같습니다.
- 빠른 관문 결과: tip 9336/9512 통과(98.1%), 실패 3건, skip 173건. 기준 `376f2a67`도 같은 3개 nodeid가 실패합니다(git 하위 프로세스 WinError 5, 이 호스트 환경 문제). 이번 스택으로 새로 생긴 실패는 0건이고, 새 시험 28건은 28/28 통과했습니다.
- 웹 `npm run check`는 exit 0입니다(vitest 1138/1138). 비교 DB 시험은 9/9 통과했고, DB 전후 차이는 0입니다.

## 커밋

| # | SHA | 제목 | 파일 |
|---|---|---|---|
| 1 | `fb6a6cba1` | fix(web): translate the all-past refusal and label the plan-check date line | 8 |
| 2 | `c023140b5` | fix(intake): stop a wholly past plan on the plan-submission step | 5 |
| 3 | `fdbe5b4ef` | fix(web): return a wholly past intake to the plan entry with the text kept | 5 |
| 4 | `231e303a5` | fix(chat): answer vendor booking cancel/refund/payment as an unsupported request | 3 |
| 5 | `d3d0a0637` | feat(web·admin): 계획 담기 화면 보조 칸을 운영 설정 스위치 하나로 — `travel.plan_input.extras_enabled`(기본 꺼짐) (ST4F-739) — `350fcd19` cherry-pick -x, 원 저자 Choi-Sangwook | 23 |

- 1~4: patch를 `git -c core.autocrlf=false apply -3`로 적용했습니다. 충돌은 0건입니다. U01 patch는 `2ce73990c`용이었지만 `decision_unit.py`에 깨끗하게 적용됐습니다.
- 5: `wiki/log.md` 하나만 충돌했습니다. role-manager 쪽 내용은 그대로 두고, 원 커밋이 추가한 10-25 한 줄만 넣었습니다. develop에만 있는 문맥 줄 3개는 넣지 않았습니다. 그 결과 원 커밋과 변경 줄(+/−) 500줄이 같고 numstat도 같습니다.
- 계획 짜 주기: 읽은 일정이 전부 과거면 같은 안내를 냅니다. 리포트에 적힌 되돌릴 수 있는 기본값을 그대로 유지했습니다.
- T16 작업 파일(`conversation_work.py`·`itinerary_actions.py`)·`tests/conftest.py`와 겹치는 파일은 0개입니다.

## 검증

- 중간 커밋(재기준 뒤 다시 실행): 앱 import는 매 커밋 통과했습니다. 신규 시험 결과는 다음과 같습니다.
  - c2: 12/12
  - c4: 32/32
  - c5: 9/9
  - 웹 c1: 14/14, c3: 21/21, c5: 18/18(트리 차이는 conftest뿐)
- ruff F/E9(바뀐 py 15개): 0건.
- 비교 DB `gugu_replay_improved_20261025`, 새 tenant: `test_intake_all_past_gate_db` 2/2, `test_intake_progress_events` 6/6, `test_plan_input_extras_admin_switch` 1/1.
- 증거: `hermes/profiles/guguroute/cache/scratch/rm-stack-20261026-042400/ev/`(`fast-tip/r.xml`, `fast-base-376f2a67/r.xml`, `fast-compare.json`, `check-tip/`, `py-db-tip/`).
- 모델 호출: E4B 0회.

## x600에서 확인할 화면

1. 지난 날짜만 넣은 직접 입력 → 계획 확인 화면 없이 「여행 계획 담기」로 돌아오고, 글이 복원되고, 빨간 안내가 보입니다(ko/en).
2. 파일로 같은 내용 → 파일이 복원된 채 같은 안내가 보입니다.
3. 과거와 오늘/미래가 섞인 계획 → 지금처럼 계획 확인 화면으로 갑니다.
4. 계획 확인 화면에서 날짜를 과거로 고쳐 등록 → en 화면에 전용 영어 문장이 나오고, ✕ 줄에 「날짜 / Date」 이름이 붙습니다.
5. 채팅 「예약 취소하고 카드로 환불해줘」 → 미지원 안내가 나오고 일정은 바뀌지 않습니다.
6. 계획 담기 화면 기본 → 「직접 입력」만 보입니다. 관리 콘솔 운영 설정 `travel.plan_input.extras_enabled`를 켜면 네 칸이 보이고, 이용 방법 설명도 함께 바뀝니다.
