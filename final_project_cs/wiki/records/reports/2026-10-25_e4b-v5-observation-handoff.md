# E4B v5 관찰 인계 — 완결 아님 (2026-10-25 06:10 KST)

## 결론

기존 유일 `proc_f11a51b230be`는 **running / field-baseline**입니다. 원계획 baseline4+improved4 **8/8=100%** 정상 review·GET reload를 실제 결과에서 재검산했습니다. 6단계 중 exit0 확인 **2/6=33.33%**, 채팅 실행행 **18/476=3.78%**입니다. **완료·개선·운영품질 성공으로 표현하지 않습니다.**

관찰 시각 `2026-10-24T21:10:12.484724Z`: field baseline18/23=78.26%, improved0/23, probe baseline0/215, improved0/215. 양쪽 완료 쌍0이므로 전체582행은 현재 blocked582, fixed/regression/same/unknown 각0입니다. 이는 의미 평가 결과가 아니라 짝 재생 대기 상태입니다.

## 실제 문제를 찾았습니다

- 실제 HTTP200 16/18, HTTP500 **2/18**. 두500의 안전한 사례 가명은 `field-10f350522264c50e01af`, `field-d1925ee26e9631ecc9c1`입니다. 양쪽 모두 tokenizer `cl100k_base.tiktoken`의 외부 asset 로드를 시도하다 차단/연결 실패했습니다. HTTP200만 보고 전체 성공으로 판정하지 않습니다.
- 정확 runtime의 `tiktoken/load.py`는 캐시 미존재 때 requests.get을 사용합니다. 원래 system Temp와 profile scratch의 예상 캐시 key `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`는 둘 다 없었습니다. 별도 `tokenizer_dependency_probe_v5.py`에서 requests를 실제 네트워크 이전에 거부하여 동일 asset 의존성을 재현했습니다(exit0: **예상 실패 확인**, 모델/DB/네트워크0). `tokenizer_dependency_probe_v5.json` 참조. 모델 의미품질 실패가 아니라 **평가환경 dependency blocker**로 분리합니다.
- 18행 중 `decision_failed`4행은 구조화 모델 출력의 근거 검증 ValueError와 실제 실패 안내입니다. HTTP200이어도 정상 질문 해결이 아닙니다. 실행은 지속 중이고 stage fatal이나 episode crash는 현재0입니다.
- 실행 중 runner/환경/캐시를 바꾸거나 중단하지 않았습니다. tokenizer 부재가 남은 일부 경로에서도 재발할 수 있습니다. 현재 배치의 실패행을 보존하고, 완료/실패 후 실제 미완료 효과만 별도 고유 runner로 복구하는 범위를 부모가 결정해야 합니다. 외부 다운로드·임의 tokenizer 대체·문자수 토큰 추정은 하지 않았습니다.

## 비공개 실출력 의미 검토

첫13행의 질문/실답을 비공개로 검토했습니다. 고객 원문/응답 전문·DB ID는 이 보고서/CSV에 싣지 않습니다.

| 가명·실근거 | 관찰·판정 |
|---|---|
| `field-318a26e9d9d00ce1f564` / baseline results 첫행 | 실제 status answered·saved=false·claims_done=false. 제목과 등록 장소가 다르다는 설명 뒤 등록된 장소 기준 상세를 답했습니다. heuristic `제목과 장소 다름` 태그만으로 질문 미응답/reader 결함으로 확정할 수 없습니다. |
| `field-b4578cdf6b049089b510` / baseline results 3행 | 실제 status escalated / reason decision_failed, 변경하지 않았다는 실패 안내입니다. 근거 없는 완료는 아니며 구조화 모델 실패입니다. improved 결과가 없어 전후 개선판정 대기입니다. |
| `field-cd292f6b43df6e2b0b96` / baseline results 12행 | 실제 status adjusted·saved=true·claims_done=true. 앞서 도착한 장소를 가리키는 후속 발화지만 원래 pending/대화 상태가 완전하지 않아 현재 장소 선택의 정오·후속 문맥상실을 확정하지 않습니다. |
| `field-dd0912be51027c64a430` / baseline results 13행 | 실제 edit_refused. 역사 일정과 현재 처리시각/잠금 조건이 섞인 비교이므로 시각 통제 검증 없이 제품 회귀로 확정하지 않습니다. |

위는 **실제 baseline 전 상태**이며 improved 후 상태는 미생성입니다. 전후 예시나 gold를 생성하지 않았습니다. 명확한 공유 제품 hunk 수정을 요구할 재현 반례가 아직 확정되지 않아 제품 candidate 수정0·추가 모델 재시험0입니다.

## 분모·무결성

- 원분모 고유582, 실제 중복 episode key0·원계획 중복 key0. frozen source 및 checkpoint 입력 hash 불일치0.
- operator439행 locator: exact308 / 원문불일치126 / raw없음5 그대로. 실패 exact subset215만 승인 재생 대상입니다. 원계획4는 별도8실행 부록이며582에 더하지 않습니다.
- 문맥 결손 **겹치는 분모**: pre_request_state_not_compiled439, pending_history_not_frozen439, lookup_cassettes_absent462, registration_state_and_cassettes_not_frozen120, field pending_state_unknown23/case_events_absent23/places_reference_absent23/per_turn_gold_needs_review23. 합산하면 안 됩니다.
- corrected v5 현재 모델 dispatch29 / complete28, known prompt143389 / completion7475토큰. 진행중 호출/진단까지의 최종 비용·토큰은 별도 마지막 account_all_models 실행 전 미마감입니다. paid0, unknown 토큰을0으로 보정하지 않습니다.
- 현재 field 중앙값27초를 남은458행에 단순 적용하면 약206.1분입니다. probe 속도/실패경로가 달라지는 **추정일 뿐 ETA/SLA가 아닙니다**. 의미 없는 poll 반복 대신 정확 handle을 부모에게 유지합니다.

## 프로세스 인계의 실제 상태

`process_manage list`에서 exact handle 소유 `20261024_213155_36cd5c`(부모), shell PID21044, running을 확인했습니다. 원래 `handoff_v5.json`의 **handed_off** 증거는 유지했습니다. 이 child에서 재handoff 요청은 `not a running process you own`로 거절됐습니다. 직후 exact poll은 running이므로 종료가 아니라 **부모 소유이기 때문**입니다. 새 child로 소유권 자체가 넘어왔다는 거짓 주장은 하지 않습니다. 완료 통지 수신자는 기존 부모이며 이 child가 완료 통지를 소비하지는 못했습니다.

## 다운로드 가능한 안전 산출물

profile scratch `local-e4b-replay-20261025/observation-v5-20261024T211012484724Z/`:

- `comparison_snapshot.csv`, `comparison_snapshot.json`: 고유582행 현재 판정·원인·locator/문맥 결손, 원문 없음.
- `observation.json`: 단계·실행행·HTTP·모델 예산·중복·동결 hash 검산.
- `turn_metadata.json`: 가명·상태·실제 질문/답변 SHA256·비공개 output handle. 전문 없음.
- `plan_appendix.json`: 실제 원계획8행 review/reload 부록.
- `score_metadata.json`, `sha256.json`: 기계 태그와 위 안전 산출물 hash.

이 snapshot은 mutable stage aggregate를 건드리지 않습니다. 실행 중 `aggregate_v5.py`를 중복 실행하지 않았습니다.

## 완료 후 정확 재개

cwd: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/local-e4b-replay-20261025`

1. `process_manage poll proc_f11a51b230be` 완료결과/exit와 `longrun_checkpoint_v5.json`을 읽습니다. 재기동·DB 재복원 금지.
2. 6단계 exit0, field23+23/probe215+215 실행행을 확인한 뒤 기존 runtime `python.exe -B observe_v5_readonly.py --finalize`를 실행합니다. 이 helper는 완료 관문이 충족되지 않으면 즉시 거부하고, 충족되면 **aggregate_v5.py → closeout_v5.py → account_all_models.py**를 실제 순서대로 실행 후 독립 중복/582 검산합니다.
3. `aggregate_v5.py`의 `real_replay_completed`는 현재 코드상 항상 false입니다. active hash-pinned script는 고치지 않았습니다. 6 exit·정확 count·`closeout_v5.execution_complete`를 실행완결 근거로 사용하고 의미 완료와 분리해야 합니다. dict overwrite 집계가 중복을 숨길 수 있어 별도 검산을 추가했습니다.
4. stage 실패면 첫 미완료 효과와 HTTP 실패행을 확인하고 최초로그 보존 뒤 새 고유 runner만 사용합니다. 현재 tokenizer 의존성 실패는 별도 분모로 남기고 운영품질 성공으로 승격하지 않습니다.

baseline pin `325ba25d88c91ce97da61f2bda635e5888fe3b40`, 기존 비교DB2개, 승인 local E4B ctx8192/concurrency1 유지. source/shared acop_cs/정상 API `proc_d8c262acf08d`/localhost·LAN 웹 변경0. 수정은 새 관찰 helper·evidence·문서뿐입니다.
