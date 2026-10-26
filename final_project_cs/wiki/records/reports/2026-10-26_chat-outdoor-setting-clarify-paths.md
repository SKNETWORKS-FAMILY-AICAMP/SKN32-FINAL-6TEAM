# 2026-10-26 채팅 「실내를 야외로 바꿔줘」 — c34bd376 x600 대체 목록 되묻기 경로

상태: 로컬 후보(role-manager c34bd376 기준) · mock 재생 시험 · 실 E4B 확인까지. 푸시·x600 배포·로컬 serving 반영은 아니다.

## 증상 (x600, role-manager c34bd376, 여행 db6f7452, 2026-10-26 05:11)

선택 없이 「실내를 야외로 바꿔줘」 → 16.0초 뒤 「말씀을 정확히 알아듣지 못했어요. 다음 중 하나인가요? 1) 북촌한옥마을 2) 광장시장 3) 국립중앙박물관 … 다른 곳으로 바꿔 줘」.

## 확정한 경로

- 선택지 칸이 `label/message/action/item_id` 뿐 → `trip_messages._clarify_with_choices` 의 대체 목록(식사·활동, 셋까지)이다. 모델 후보(`fact`·`to_version` 포함)가 아니다.
- 머리말이 「알아듣지 못했어요」 → 그 시점 `_setting_swap(decision)` 이 None.
- 팀 요청(`required_input_schema.x-conversation.request`, 저장 원본 그대로)에 `setting` 이 없다 → `_dispatch_decision` 에서 `requested_setting(raw)` 도 None(할 일 clarify 에서도 조건이 있으면 싣는다). 다음 턴에 고른 박물관의 다른 안(CU · 올리브영)도 실내·야외로 걸러지지 않았다.
- `place_setting` 은 스키마 필수(엄격 모드 `strict_schema` 와 `validate_structured` 모두)이고 indoor/outdoor 는 인용이 고객 문장에 없으면 `edit_intent.validate` 가 실패시킨다(그러면 「해석하지 못했어요」 답이 난다). 따라서 **최종 해석의 `place_setting.want` 는 any** 였다.
- 한 칸씩 바꾼 원출력 재생(모델 호출 0)에서 x600 응답과 같은 모양이 나오는 것은 모두 `want=any` 인 것뿐이다: clarify·후보 없음 / 버려지는 후보만 / apply_change + 다른 활동 근처 기준(재확인이 후보를 지움). `want=outdoor` 면 같은 해석이 「어느 일정을 야외 장소로 바꿀까요?」 + 활동 셋이다(로컬 E4B 결과와 같다).
- 어떤 모델이 냈는지(`decision.model_path`)는 조회하지 않았다. 16초(로컬 우선 대기보다 김)와 로컬 E4B 미재현으로 유료 넘김(gpt-6-luna) 경로로 보이나 **미확인**이다. 유료 호출은 하지 않았다.

## 고친 것 (낱말 매칭 없음 — 칸 · 일정 종류 · 장소 기록만)

1. 원인 쪽(모델이 칸을 비움): `edit_intent.schemas` 의 `place_setting` 에 칸 설명(「action과 무관하게, clarify여도 채운다」)을 붙였다 — `strict_schema` 가 그대로 보낸다. 해석 지시(`edit_intent.SYSTEM`)에도 한 줄을 더했다.
2. `decision_unit.guard_setting_target`: 조건은 있는데 대상 없이 apply_change/propose_alternatives 를 고른 해석은 대상 되묻기(`setting_untargeted`)로 돌린다 — 전에는 팀이 조건 없이 모든 활동을 「어느 일정을 다른 곳으로 바꿀까요?」로 물었다.
3. `trip_messages._clarify_with_choices`: 조건이 있는데 바꿀 수 있는 활동이 하나도 없으면 식사가 든 대체 목록 대신 「지금 일정에서 야외 장소로 바꿀 수 있는 활동 일정을 찾지 못했어요」로 묻는다.

조건이 비어 있는 해석(`want=any`)을 고객 문장의 낱말로 되살리지 않는다(검증기 약화 · 낱말 규칙 금지). 그 경우의 대체 목록은 계약 그대로다.

## 검증

(아래 결과는 작업 폴더 `cache/scratch/outdoor-diag4-20261026-051953/evidence/` 에 있다)

- RED → GREEN: 새 시험 `tests/unit/travel/test_chat_setting_clarify_paths.py` 9건 — 수정 전 4 실패(스키마·지시 1, 대상 없는 조건 바꾸기 2, 활동이 없을 때 식사 목록 1) · 5 통과(x600 경로 재생 3 + 같은 해석의 outdoor 대조 1 + 조건 없는 대상 없음 유지 1) → 수정 후 9/9. 관련 묶음(place_setting · swap_targets · clarify_candidates · openai strict) 64/64.
- 빠른 관문(tests/architecture · contract · unit · security, `not live and not db and not slow`): 9,379 통과 / 실패 0 / 오류 0 (skip 173, deselected 677) — `evidence/gate.xml`. ruff F/E9 바뀐 파일 · app+tests 모두 통과.
- 실 E4B(tripilot-pointer:e4b-ft) 2회(lease outdoor-diag4, live 카운터 전후 동일):
  - 「실내를 야외로 바꿔줘」(선택 없음): 원출력 `place_setting=outdoor/「야외로」` → 「어느 일정을 야외 장소로 바꿀까요?」 북촌 · 박물관 · N서울타워(식사 없음), 요청 `setting=outdoor`.
  - 용산가족공원으로 바꾼 뒤 「야외로 바꿔줘」: 「용산가족공원은(는) 이미 야외 장소예요. 어느 일정을 야외 장소로 바꿀까요?」 북촌 · N서울타워 · 용산가족공원.
- 유료 모델(gpt-6-luna)이 바뀐 칸 설명 · 지시로 `want=outdoor` 를 내는지는 호출하지 않아 **미확인**이다 — x600 배포 뒤 같은 문장으로 다시 확인해야 한다(그때 `decision.model_path` 와 해석 원출력의 `place_setting` 을 함께 본다).
