# 「오후 5시 30분으로 옮겨줘」 로컬 E4B need_time 수정 후보 (2026-10-28)

대상: x600 role-manager `4fee819c` 실서버 확인 결함 1(보고서 `2026-10-28_x600_4fee819c_실서버확인.md`).
후보: 로컬 커밋 `e78e038b062a6ea0f62931f0704c3eec1d9f849e`(부모 `4fee819cab43`, **push 안 함**).
worktree: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\fix-timemove-20261028-0554\rm`.
patch: `fix-timemove-20261028-0554\timemove-e78e038b.patch`, sha256 `a27f8f241a0291f6895cd76f445ab6362c2227bd1e642844583bcf07d90e0bc3`.

## 결론
- **원인은 로컬 생성 문법이다.** 모델은 시각을 낼 칸이 없었고, 서버가 칸을 못 읽은 것이 아니다.
  - x600 원출력 3/3이 같은 모양이다. Case 10108fc5·14dd1f31·5a96697a의 `customer_cases.state_json->decision->raw`를 SELECT로만 읽었다.
  - 모양: `action=change_time`, `time_edit.boundary=shift`, `scope=item`, `time=""`, `anchor_kind=none`, `anchor_time=""`, `minutes=30`, `relation`=before 2건·at 1건.
  - L05 생성 문법 `edit_intent.generation_variants`(53a116f0)가 한 일정 `shift` 갈래의 `time`과 `anchor_time`을 빈 문자열로, `anchor_kind`를 `none`으로 묶었다. 그래서 「shift·item·검증된 time = 새 시작」(c286b906 `time_ops`)과 맨 위 시작 시각 칸(`chat_edit.ops_for`)에 갈 답을 생성할 수 없었다.
  - 시각 안의 「30분」은 이동 크기가 아니다(`spoken_minutes`). 그래서 minutes가 None이 되고 `need_time`으로 되물었다.
  - 74b2b232(시험 1줄)와 064208bd(범위 옮기기 고정)는 관계없다. 유료 `paid_time_edit`(de712b2e)는 plain 스키마에만 쓰여 로컬 문법과 관계없다.
- **수정:** 한 일정 `shift` 옆에 시각을 낼 수 있는 갈래 2개를 더했다. 둘 다 `minutes=0`이다.
  - (a) `time_edit.time=HH:MM`.
  - (b) `anchor_kind=time`, `anchor_item=none`, `relation=at`, `anchor_time=HH:MM`.
  - `validate`가 (b)의 `anchor_time`도 인용 재계산으로 확인한다(`_shift_start_clock`).
  - 새 시작 시각과 이동 크기를 함께 낸 답은 문법 없는 유료 답이라도 해석 실패로 끝난다(Codex 조건).
  - 문장 낱말 규칙은 없다. 유료 plain 스키마와 SYSTEM 프롬프트는 바꾸지 않았다.
- **실E4B 8/8회를 썼다.** 수정 뒤 「오후 5시 30분으로 옮겨줘」는 1/1 성공했다(17:30~19:00).
  - (a)만 넣었을 때는 2/2가 여전히 `need_time`이었다. (b)를 넣은 판은 이 문장으로 1회만 쟀다.
  - 그래서 재현율이 좋아졌다고 확정할 수 없다(Codex도 같은 지적). x600 재확인이 필요하다.
- **빠른 관문 실패는 0이다.** 실제 오늘 10825건과 RELDATE_SHIFT_DAYS=37 10825건 모두 실패 0·오류 0이다. 새 시험 23건이 두 실행에 다 들어 있다.
- **chat_edit DB 시험은 66/66 통과했다**(비교 DB `gugu_replay_improved_20261025`, 느린 시험 1건 제외).

## 실E4B (로컬 `tripilot-pointer:e4b-ft`, `decide()` 직접 호출, num_ctx 12288)
- 조건: lease는 `timemove`, DB와 외부망은 막고 127.0.0.1:11434만 열었다. 합성 여행은 test12 모양으로, 북촌한옥마을을 선택해 두었다.
- 「base」는 같은 트리에서 새 갈래만 걸러낸 문법이다. sha가 4fee819c 문법(b36b43ea…)과 같음을 `pincheck.py`로 확인했다.
- **제품 시한(첫 조각 8초, 멈춤 5초, 최대 15초)이 아니라 측정용 시한(30/5/60초)을 썼다.**
  - 8회 모두 15초를 넘었다(26~41초). 조각 속도는 11.0~12.7/s로 평소(~30/s)의 절반 이하다.
  - 그래서 이 숫자는 판단 내용만 보여 준다. 로컬 응답 속도는 판단하지 않는다.

| # | 트리 | 문장 | 모델 칸 | 결과 |
|---|---|---|---|---|
| b1 | base | 오후 5시 30분으로 옮겨줘 | shift·time ""·minutes 30·relation before | need_time (x600 재현) |
| c1-1 | 후보(a만) | 오후 5시 30분으로 옮겨줘 | 같음 | need_time |
| c1-2 | 후보(a만) | 17:30으로 옮겨줘 | start·time 17:30·anchor_time 17:30 | 17:30~19:00 |
| c1-3 | 후보(a만) | 오후 5시 30분으로 옮겨줘 | shift·time ""·minutes 30 | need_time |
| c1-4 | 후보(a만) | 내일 오전 10시로 옮겨줘 | start·time 10:00·at_day tomorrow·대상 i4(경복궁) | 경복궁을 10-29 10:00~12:00으로 옮김. 선택한 북촌이 아니라 다른 일정이 대상이 됐다(관찰, base는 측정하지 않음) |
| c1-5 | 후보(a만) | 30분 늦춰줘 | shift·minutes 30 | 13:30~15:00 |
| c2-1 | 최종 | 오후 5시 30분으로 옮겨줘 | shift·time ""·**anchor_kind time·anchor_time 17:30**·minutes 0 | **17:30~19:00** |
| c2-2 | 최종 | 30분 늦춰줘 | shift·minutes 30 | 13:30~15:00 |

증거: `fix-timemove-20261028-0554\e4b\live-*.json`(raw_before_validation 포함), `live_decide_timemove.py`.

## 시험
- RED: 기준 4fee819c의 `edit_intent.py`에서 새 시험 파일이 11/19 실패했다(`out/red2-base.log`). 갈래가 막혀 있었고, `anchor_time` 인용 검사도 없었다.
- GREEN: 관련 묶음 148/148(`out/green2.log`), 이어서 105/105(`out/green3.log`, Codex 조건 시험 포함).
- 빠른 관문(`gate.sh`, 5 shard): 실제 오늘 10825 tests, 실패 0, 오류 0, skip 173. +37일도 10825 tests, 실패 0, 오류 0, skip 173(`guard_now=2026-12-04`).
  - 실행 전후 `edit_intent.py` sha는 af65b848…로 같다.
- `test_chat_decision_paid_schema::test_the_local_grammar_is_unchanged_by_the_paid_variants`의 문법 sha를 4be6948e…로 바꿨다(contract_correction). 새 두 갈래를 빼면 옛 값 b36b43ea…와 같다. 유료 갈래가 섞이지 않았다는 이 시험의 뜻은 그대로다.
- DB 시험(비교 DB `gugu_replay_improved_20261025`): `tests/e2e/test_chat_edit_web.py`, `test_chat_add_lodging_kind_web.py`, `test_decision_unit_web.py`를 돌렸다. `test_the_raw_coordinates_are_stored_and_logged_nowhere`는 환경 때문에 뺐다(전 tenant 표를 읽어 20분 이상 걸린다). 결과: 66 passed, 1 deselected, 실패 0, 1954.9초(`ev/db/e2e_chat/r.xml`, tenant `tm_1793137213_5514`).
  - 앞서 같은 DB 시험을 두 번 중간에 멈췄다(소스 수정 때문). tenant `tm_1793136550_15276`에 정리되지 않은 시험 행이 남았을 수 있다.

## Codex 판단 (`codex exec`, 글만 읽는 검토)
- 판정은 조건부 승인이다. 구조적 수정이고 키워드 규칙은 없다고 봤다.
- 조건 1: 유료 plain 경로에서 절대 시각과 이동 크기가 함께 오면 거절할 것. `validate`에 반영했다.
- 조건 2: plain 경로의 맞는 시각·틀린 시각, 기존 start+anchor_time, 장소 행동을 시험할 것. 시험 4건을 추가했다.
- 실E4B 1/1은 재현율 근거로 부족하다는 지적은 그대로 남는다.
- 증거: `codex\prompt.md`, `codex\answer.md`, `codex\log.txt`.

## 남은 일
- x600 재확인: 같은 3문장, 「내일 오전 10시로」, 「30분 늦춰줘」. E4B 경로(`model_path local`)에서 다시 확인해야 한다. 이번 실E4B는 로컬 하드웨어에서 잰 것이다.
- 「내일 오전 10시로 옮겨줘」에서 모델이 선택한 일정이 아닌 다른 일정을 대상으로 골랐다(c1-4). 이번 변경 범위 밖이고 base 비교가 없다. 별도로 확인해야 한다.
- push는 하지 않았다. role-manager 반영은 부모가 결정한다.
