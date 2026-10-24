# F3 미해결 인계 — 원문 probe 수락 실패 유지

2026-10-25 05:24 KST. **NOT_ACCEPTED / DESIGN_REVIEW_REQUIRED**. 이 수정은 완료·배포 가능한 패키지가 아닙니다. 새 독립 설계 검토를 위해 현재 diff·재현·타임라인만 보존합니다.

## 대상과 변경

- 원후보: `remaining_non_db_integration/repo`, 입력 tree `e94caecf05c9af750b45bef4bdc4e64395caaf8b`.
- 새 사본: `remaining_non_db_f3_fix/repo`; 기존 후보·원본은 수정하지 않았습니다.
- `llm_failover.py`의 `_hedged` / `_attempt`만 최소 수정했습니다. 요청별 `dispatch_lock`으로 성공 publication, 각 시도 claim, caller 종료를 조정합니다. 전역 lock·I/O lock·예산 API 변경은 없습니다.
- 원 독립 `test_fresh_concurrency.py`는 SHA256 `66d43e0fb476bb6eb35b3e73a572dc95b0557d6227d883b8404e362bbaf7738e` 그대로 보존했고 영구 회귀 사본도 동일 바이트입니다. 원 7개 독립probe도 그대로입니다. 별도 경계 시험2개는 publication 선행/claim 선행의 정상 호출 경로를 검증합니다.

## 정확 RED 및 현재 실패

- `red-exact.xml`: 원문3개 모두 최종 `paid == []` assertion(90행)에서 실패, API 대역1회씩.
- `final-exact15.xml` 및 `final-exact15-timeline.xml`: 원문15개 중12통과/3실패. 실패는 아래3개 모두 **원 probe 81행 `assert paid_called.wait(3)`**입니다. 최종90행에는 도달하지 않습니다.

```text
test_fresh_concurrency.py::test_no_paid_dispatch_if_local_is_queued_between_recheck_and_thread_start[0]
test_fresh_concurrency.py::test_no_paid_dispatch_if_local_is_queued_between_recheck_and_thread_start[1]
test_fresh_concurrency.py::test_no_paid_dispatch_if_local_is_queued_between_recheck_and_thread_start[2]
```

`exact-timeline.json`은 원 시험/공급자/Event/scheduler를 고치지 않은 `sys.setprofile`/`threading.setprofile` 관측입니다. 각 iteration에서 다음 순서가 실제 기록됐습니다.

1. caller가 두 번째 `Thread.start` override에 진입, local release.
2. local worker가 요청별 lock 안에서 `settled.set()` 후 `results.put` 호출.
3. 원 probe의 `Observed.put`이 **정식 publication 경로**의 `super().put`을 마친 뒤 published Event를 설정하고 반환.
4. API worker가 같은 요청별 lock의 `claim_dispatch`에 진입: settled=True, 반환=False.
5. API worker가 `(False, 'cancelled')`를 queue에 넣고 종료. paid-provider-call 프로파일 사건0건.
6. caller는 시험의 `Thread.start` override 안에서 paid_called Event가 설정되기를3초 기다리다가 AssertionError. 이 예외가 start → _hedged → text → 시험86행으로 전파됩니다.

따라서 현재 수정을 통과시키지 못하는 직접 경로는 추가 유료 전송이 아니라 **scheduler override가 유료 호출 Event를 반드시 기다리는 경로**입니다. 그 Event를 설정하는 원문 유일한 경로는 api()의 `paid.append('avoidable'); paid_called.set()`입니다. 이 branch를 실행하면90행의 `paid == []`와 충돌합니다. 이 관측을 이유로 원 시험을 완화·삭제하거나 예외를 삼키는 제품 우회를 추가하지 않았습니다. 원문3개 GREEN이라는 요구는 충족하지 못했으므로 F3는 수락 미해결입니다. 새 세션은 이 경로와 요구를 독립적으로 검토해야 합니다.

초기 별도 scheduler-join 보조 사본8/8은 원문을 대체하는 수락 증거가 아닙니다. 사용자 steering 후 영구 회귀는 원문으로 복원했고 보조 사본/실행은 이력 증거로만 남겼습니다.

## 원자성 경계 및 유지 한계

- publication이 claim보다 먼저이면 첫 호출/재시도 취소. claim이 먼저이면 그 시도는 논리적으로 시작한 것으로 허용합니다. provider 호출 직전 스케줄 지연이 있더라도 기존 claim을 물리 취소하지 않습니다.
- queue put은 publication과 같은 lock 안입니다. queue 소비는 승자 공표의 선행 조건이 아닙니다. caller만 최종 경로를 기록합니다. 예외 unpack와 finally 종료도 같은 lock입니다.
- worker 지연, local/API 동시성, contextvars, caller-only admission, inflight 회수, stream/image/warm 제외는 기존 회귀로 확인하며 실제 provider는 사용하지 않습니다.
- `CallBudget.reserve`는 DB used를 올리는 admission이며 bool callback에는 commit/refund가 없습니다. 미사용 예약이 다음 fallback을 budget_exhausted로 막는 characterization은 유지·통과했습니다. 금전/전송당 엄격 상한은 이번 수정 범위가 아닙니다. reserve/commit/release와 저장소 계약은 별도 설계가 필요합니다.

## runner 실패 분리

`final-boundaries.log`의 두 점은 완료 XML을 뜻하지 않습니다. pytest 종료 처리에서 JUnit의 platform.node → platform.uname → Windows shell fallback → NUL open이 기존 write guard에 차단되어 XML에는 선언만 남았습니다. wrapper는 subprocess.run 완료 후 XML을 읽었으며 조기 read/timeout이 원인은 아닙니다. 이 최초 runner는 pytest rc를 parser 전에 별도 저장하지 않은 결함이 있어 해당 결과를2통과로 집계하지 않습니다. 최초 손상 XML/로그는 보존했습니다.

새 `metadata_plugin`은 JUnit hostname을 실제 `socket.gethostname`으로 읽도록만 바꿉니다. socket/DB/bind/child/write guard는 해제하지 않았습니다. 새 prefix `final-boundaries-retry1`에서 pytest rc0, 정상 XML2/2를 확인했습니다. 이후 runner는 parser 전에 `*-process.json`에 실제 rc·동결 전후 hash를 먼저 기록합니다.

## 정확 분모 보완

`final-combined955` 단일 실행은 회귀331 + 관문607 + 원 독립7 + 새 독립8 + 새 경계2 = 955개입니다. 이전 원집합945의 UUID4·historical/guard3이 이 선택에서 빠졌음을 집합 대조로 발견했고, 반복 실패/큰 suite 재실행 없이 별도 `closure-missing7` 정상 완료7/7로 보완했습니다. 따라서 이전 요청집합(기존945 + 새 독립8 + 경계2)은 정확955개 중948통과/3실패/4bind차단이며, 별도 원 독립7은7/7입니다. 두 완료 실행의 고유 합집합은962개 중955통과/3실패/4bind차단입니다. **962개 단일 실행이라고 주장하지 않습니다.** 반복 실행은 합산하지 않으며 nodeid-manifest.json에서 원문ID·분류·선택 집합을 보존합니다.

## 인계 범위

완료 수락을 주장하지 않습니다. 실행 결과·정확 분모·동결 hash·diagnostic patch 정역 tree 검산은 scratch의 `FINAL.json`, `nodeid-manifest.json`, `REPRODUCE.md`를 참조합니다. 4개 HTTP bind 차단은 그대로 미검증입니다. DB는 라이팅 에이전트 세션 소유이며 DB/서비스/실모델/외부API/push/배포는 실행하지 않았습니다. 다음 작업은 새 세션의 원문 probe 및 dispatch 선후 계약 설계 재검토입니다.
