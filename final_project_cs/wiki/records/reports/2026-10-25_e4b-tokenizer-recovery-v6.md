# E4B tokenizer 캐시 실제 복구 및 후속 재생 인계

관찰 시각: 2026-10-24T21:19:29.899659+00:00

## 결론

**무네트워크 tokenizer 복구는 완료했습니다. 실API·실E4B 양쪽 4행 재검증은 기존 유일 배치 완료 뒤 자동 수행하도록 실행·부모 인계했으며 아직 완료가 아닙니다.**

- 기존 설치 자산을 발견하여 정확 설치 loader 기대 SHA256과 일치하는 1,681,126바이트를 별도 고유 cache로 복사했습니다. 다운로드·고객원문 외부전송 0입니다.
- `TIKTOKEN_CACHE_DIR=C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\local-e4b-replay-20261025\tokenizer-recovery-20261024T211338Z-692b5cfc\cache`
- SHA256 `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`; cache key `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`.
- 원래 두 입력의 missing-cache RED를 HTTP 이전 차단으로 재현하고, 같은 입력의 baseline/improved 실제 `app.core.context.count_tokens` 및 encode/decode 4/4=100% 통과했습니다. socket·HTTP·DB·모델 접근을 거부한 별도 fresh process이며 blocked event 0, 네트워크·DB·모델 호출 0입니다. 토큰수는 각 69·8, 원문은 증거에 출력하지 않았습니다.

## 현재 기존 배치 진행

| stage | 실행/예정 | 진행률 | HTTP500 |
|---|---:|---:|---:|
| plans-baseline | 4/4 | 100.0% | 0 |
| plans-improved | 4/4 | 100.0% | 0 |
| field-baseline | 23/23 | 100.0% | 3 |
| field-improved | 12/23 | 52.1739% | 0 |
| probe-baseline | 0/215 | 0.0% | 0 |
| probe-improved | 0/215 | 0.0% | 0 |

단계 exit0 3/6=50.00%; 채팅 35/476=7.3529%. 원계획8행은 채팅분모에 더하지 않습니다.

## 원인·분류

- 원래 HTTP500 두 가명 `field-10f350522264c50e01af`, `field-d1925ee26e9631ecc9c1`의 정확 저장 예외·입력hash·원출력 handle은 `recovery_plan.json`에 보존했습니다. requests/adapters.py:729의 ConnectionError와 공식 `cl100k_base.tiktoken` URL입니다. 저장 예외 자체가 기존 runner에서 잘려 있어 완전 traceback으로 과장하지 않습니다.
- 현재 새 확인: baseline23행에서 같은 dependency HTTP500은 3행입니다. 추가 `field-493a04ceb8123fb70dac`도 같은 원인으로 보존했고, 원래2개 재생 큐에는 아직 포함하지 않았습니다.
- 캐시 부재는 **평가환경 실패**입니다. 구조화 출력 validation/decision_failed 및 질문 해결 실패는 별도 제품·모델 품질 검토 대상이며 이번 캐시 복구로 해결됐다고 하지 않습니다. 원문locator·gold·pending/history 불완전은 **unknown** 그대로입니다.

## 장기 실행과 안전 경계

- 기존 `proc_f11a51b230be` parent-owned running을 재확인했습니다. 3/23의 국소 의존성 실패이며 모든 경로의 stage 무효가 예측된 것은 아니므로 정상 중단·재시작하지 않았습니다. 기존 script/env/cache/ledger/output 변경0, DB 재복원0입니다.
- `proc_227989a6c1f3`: `continue_tokenizer_recovery_v6.py` 실제 실행, `waiting_existing_batch` readback, **handed_off** 응답 확인. 현재 모델 호출은0이며 30초 조건대기만 합니다. 부모가 완료통지를 받습니다.
- continuation은 기존6stage exit0와 정확 PID22032 종료 및 pinned input hash 일치를 확인한 뒤에만 새 고유 runner를 baseline→improved 순차 실행합니다. 동일 검증 cache·원래 두 입력, 기존 비교DB2개만 사용합니다. local11434 E4B digest `ef0a580aca375aa9bf4547558b9b41910e5f85769b5ad3e9e99ee13af71a1025`, ctx8192, concurrency1, paid/실알림0의 원 guard를 유지합니다.
- 기존 배치가 비정상 종료·blocked이면 continuation은 모델을 호출하지 않고 정확 blocker checkpoint와 비영 exit를 남깁니다. DB/준비를 자동 반복하지 않습니다.
- 완료 시 `continuation_checkpoint.json`, `paired_real_results_safe.json`의 4행 HTTP200·동일 입력hash·tokenizer exception 부재를 확인하고 실제 응답 상태를 검토합니다. HTTP200은 역사적 의미 성공/개선 확정이 아닙니다. 원 배치 최종집계는 기존 `observe_v5_readonly.py --finalize` 관문을 사용합니다.

## 새 파일

profile scratch `local-e4b-replay-20261025/`: `repair_tokenizer_isolated_v6.py`, `tokenizer_preflight_v6.py`, `prepare_recovery_v6.py`, `guarded_run_cache_v6_adb5deed.py`, `continue_tokenizer_recovery_v6.py`, `report_recovery_v6.py`, `tokenizer_recovery_v6_pointer.json`, `handoff_tokenizer_recovery_v6.json` 및 고유 recovery evidence/cache 디렉터리입니다.
모든 기존 pinned 입력 무변경 12/12=100%. 제품 코드·패키지·원env·공용DB·기존 cache 변경 없음.
