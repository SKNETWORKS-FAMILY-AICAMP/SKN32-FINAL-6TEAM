# 잔여 HTTP500 동일반례 수정·실재생 v8 — 2026-10-25

## 결론

tokenizer환경31/31 복구 후 재생50행은 HTTP20048/5002였습니다. 잔여2행은 같은 가명 `chat-fb67010f419c5ce60276`의 baseline/improved이며, 별도 정상 API·실E4B trace 재생2/2에서 동일 TypeError를 다시 확인했습니다. 기존 baseline과 frozen improved는 보존했습니다.

새 소유 candidate의 `itinerary_changes.plan_fresh_alternate` 한 곳에 5줄 guard를 넣고, 동일입력을 다시 정상API·실E4B로 순차재생했습니다. **baseline HTTP500(원래 결함 유지), 수정 improved HTTP200/needs_check, 장소 위치 확인불가 안내, 일정 무변경 실제저장 재조회, 완료주장 없음**을 모두 확인했습니다. **제품 robustness 1사례 수정이며 요청한 대안을 찾아 해결했다는 뜻은 아닙니다.** 의미판정은 unknown238·blocked344/582 유지합니다.

## 정확 원인·최소 수정

`POST /v1/web/trips/{id}/messages` → web_message → handle_trip_message → _run_decision → Case/controller/activity Team → conversation_work._fresh_plan → plan_fresh_alternate → activity_candidates:388 → distance_m:168. original의 latitude/longitude가 모두 None, 후보 좌표는 float인 상태에서 math.radians(None)이 발생했습니다. 장소 참조자료가 없는 부분재구성환경이 원인 입력을 드러냈지만, 모름을 처리하지 않고 500을 낸 것은 제품 경계 결함입니다. 이를 실제 역사적 고객 장소의 원래 좌표가 없었다는 주장으로 바꾸지 않습니다.

최소수정은 origin 좌표가 하나라도 없으면 기존 NoChange/needs_check 계약으로 명시적 확인불가·무변경을 반환하는 것입니다. 없는 좌표를 만들거나 거리0·임의 대안·잘못된 no_alternate를 내지 않습니다. shared candidate/product/source/정상API·웹은 수정하지 않았습니다. 부모는 별도 fixed_candidate의 patch 한 hunk만 검토·통합해야 합니다.

## RED→GREEN·실제 비교

- 정확 plan_fresh_alternate 함수 반례: 위도/경도 모두 없음·위도만 없음·경도만 없음 3 subcase에서 동일 TypeError RED 확인 후 동일 테스트 1 method/3 subcase GREEN.
- 실제 API/E4B trace2회 + 수정 뒤 paired2회. 입력hash 양쪽·전후 동일. v7 50 + v8 4 = 총54 local dispatch/complete, paid0.
- 원래 test_fresh_alternate.py 15개를 변경 없이 별도 FunctionTestCase로 실행: 수정 전후 모두 통과3/15·composition_unbound setup오류12/15·assertion실패0. pytest 미설치 시도도 보존. 이 제한을 15/15 회귀 통과로 보고하지 않습니다.
- 원래 frozen source hash 전부 재검증, 불일치0. 비교DB2개만 쓰고 복원0, 원문/credential 다운로드묶음 미포함.

## 남은 일

ctx8192에 닿아 잘린 기존 실제 응답231개는 별도 open. shared hunk ownership/정상 caller 입력·출력 공간 경계 TDD와 재생이 필요합니다. 4사례 증거대조는 골든 의미정답이 아니며, pending/events/cassette/gold 부재와 원문불일치126·부재5를 유지합니다. 고객질문 전체해결·대안찾기·후속문맥은 인증하지 않았습니다.
