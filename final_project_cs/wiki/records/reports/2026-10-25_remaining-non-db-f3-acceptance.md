---
type: report
title: F3 독립 설계·시험 타당성 검토와 격리 수락
description: 원 제품 결함과 원문 시험의 인과 모순을 분리하고 동등 스케줄로 old RED new GREEN을 확인한다
status: draft
tags: [release, documentation]
domain: neutral
---

# F3 독립 설계·시험 타당성 검토

## 현재 판정

[실측] 새 `remaining_non_db_f3_acceptance/repo`만 사용합니다. old tree는 `e94caecf05c9af750b45bef4bdc4e64395caaf8b`, 검토 입력은 미수락 진단 tree `268805134abf627b98c31016591af62a592ec84b`입니다. 기존 후보·원본·DB는 변경하지 않습니다. 담당은 독립 F3 검토 세션이며 이전 제품 수정 작성자와 분리됩니다. 이 문서는 이전 미수락 기록을 지우거나 당시 판정을 소급 변경하지 않습니다.

## 원문 시험의 인과 모순

[실측] 원문 `test_fresh_concurrency.py:69-90`에서 `paid_called`는 새 unset Event이며 이를 설정하는 유일한 경로는 84행 `paid.append('avoidable'); paid_called.set()`입니다. `paid`를 지우는 코드가 없습니다. caller의 두 번째 `Thread.start` override는 81행에서 이 Event가 반드시 설정되기를 기다리고, 90행은 `paid == []`를 요구합니다. 따라서 모든 assertion을 정상 통과하는 실행은 불가능합니다. 이는 무한 제품 deadlock이 아니라 시험 장벽의 3초 timeout/AssertionError이며, 제품이 이 assertion을 삼켜서는 안 됩니다.

[실측] 원문은 바이트 그대로 보존·재실행했습니다. SHA256 `66d43e0fb476bb6eb35b3e73a572dc95b0557d6227d883b8404e362bbaf7738e`. old는 유료 대역 호출 후 최종 `paid == []` 실패, new는 유료 진입을 막아 81행 `paid_called.wait(3)` 실패입니다. 같은 nodeid라도 원인이 다릅니다. 원문 실패는 GREEN/skip/xfail로 바꾸지 않습니다.

## 독립 동등 스케줄 회귀

[실측] 새 `tests/unit/infrastructure/test_llm_f3_acceptance.py`는 caller 최종 empty queue 확인 뒤 API Thread.start 직전에 local을 release하고, 실제 정식 queue enqueue 완료를 기다린 후 API worker를 실행합니다. caller가 queue를 소비하기 전에 worker 종료 Event를 기다립니다. 종료는 provider 성공 여부와 무관하게 실제 target의 finally에서 관측합니다. 제품 `_attempt`·claim·provider 반환값·예외는 교체하지 않습니다.

[실측] 같은 시험 바이트를 old/new 양쪽에 실행했습니다. old **0/3 = 0%**, 세 건 모두 `paid == []`에서 `['avoidable']`로 RED. new **3/3 = 100%** GREEN. local 반환·기존 winner/path·paid 0·취소 outcome·caller-only 예산·정확 owned worker join·inflight 0·breaker permit 반환을 모두 요구합니다. 원문의 paid-zero 기대를 완화한 것이 아니라, 그 기대를 깨야만 풀리는 시험 장벽을 독립 관측으로 대체한 별도 시험입니다. 원문은 그대로 남습니다.

## 코드 검토 판정과 한계

- [실측] `llm_failover.py:594-619, 680-698`: 요청별 lock이 success publication(terminal flag와 queue put)과 매 시도의 claim을 직렬화합니다. publication 선행이면 첫 호출/재시도가 거절됩니다. caller queue 소비가 필요 없습니다. I/O·예산·Thread.start 동안 lock을 보유하지 않습니다.
- [실측] claim 선행은 이미 논리적으로 시작한 시도로 허용합니다. `test_llm_overflow_f3_boundaries.py`의 두 방향이 이를 검증합니다. claim과 provider 진입 사이에 local publication이 발생하면 **실제 provider 진입은 그 뒤일 수 있습니다**. 이것은 물리 전송 취소·전송당 엄격 상한의 증거가 아닙니다. 그런 강화 계약은 별도 설계 대상입니다.
- [실측] 성공은 동일 lock 안의 queue 순서로 전달되며 caller만 `_record`합니다. 늦은 loser는 기존 winner/path를 덮지 않습니다. worker의 BaseException은 결과로 전달되고 caller에서 재발생하며 caller finally는 요청을 닫습니다. 시작 실패 시 slot/permit 반환을 유지합니다. 공급자 I/O 완료 시 slot은 publication보다 먼저 회수되므로 `inflight == 0`만으로 enqueue 완료를 추정하면 안 됩니다. 새 회귀는 실제 enqueue를 관측합니다.
- [실측] bool 예약은 refund/commit이 없어 paid 0이어도 quota 1을 소비하고 다음 fallback을 막을 수 있습니다. 기존 characterization을 유지합니다. fail-open 저장소 정책·SDK 내부 재시도·실제 과금·실제 DB·물리 취소는 이번 F3 수락 범위가 아닙니다.
- [실측] 기존 F3 제품 수정 바이트는 검토 입력과 동일합니다. 원문3실패만을 이유로 새 제품 우회나 assertion 삼키기를 추가하지 않았습니다. 검토 범위에서 추가 제품 반례는 확인하지 않았습니다.

## 최종 실행 근거

[실측 2026-10-25 05:41 KST] `single-final`은 **한 pytest 실행 965개**, 958통과/원문 시험모순3실패/기존 bind4차단, 29 deselected, warning 1(기존 Starlette/AnyIO deprecation), rc1입니다. raw 통과율 **958/965 = 99.27%**이며 raw 전체 GREEN을 주장하지 않습니다. 실행 대상은 이전 단일955 + 누락했던 UUID/historical/guard7 + 새 독립회귀3입니다. 다른 실행을 합산한 수치가 아닙니다. 유효하고 허용된 범위는 958/958 = 100%이며 원문3·차단4는 전체965 분모에서 유지합니다.

[실측] `single-nodeids.json`의 collected/report는 각각965, 고유 nodeid965입니다. `single-final.xml`, `single-final-process.json`에 실제 rc와 동결 코드·시험 전후 hash를 보존했습니다. 새 회귀3/3, 기존 publication-first/claim-first2/2, 원 독립7/7, 원 fresh 나머지5/5, UUID/historical/guard7/7을 포함합니다. 이 부분 수치는 전체에 이미 포함되므로 더하지 않습니다. 별도 `red-independent`3실패와 `green-independent`3통과, `original-unchanged`3실패도 합산하지 않습니다.

[실측] `single-timeline.json`은 원문3건과 새 회귀3건 모두 local enqueue 뒤 API claim=False, `(False, 'cancelled')` enqueue, provider 진입0을 기록합니다. 원문3건은 그 상태에서도 81행의 불가능한 Event 요구 때문에 실패합니다. 원문을 skip/xfail/수정하지 않았습니다. 최종 문서화 후 tracked 전체 접근성·변경줄 보안·patch 정역 tree 검사를 별도 수행하며 결과는 외부 `FINAL.json`에 둡니다.

**판정: F3 logical publication-before-unclaimed-dispatch 제품 수정은 scoped 수락·새 patch 승인 검토 가능입니다.** 원문3건은 테스트 인과 모순이며 현재 제품 미해결3건으로 세지 않습니다. 단, 기본 시험 전체 GREEN·물리 첫 전송 억제·과금 정확성·실 provider/DB·4개 HTTP transport·원본 통합/배포 수락은 아닙니다. DB/외부API/실모델/서비스·소켓 실기동/push/배포 금지는 유지했습니다. 이전 diagnostic patch는 계속 미수락 기록으로 남기며 새 combined patch는 old tree 위 대체 입력이지 이전 patch 뒤 순차 적용할 파일이 아닙니다.

## 관계

- [현재 failover 계약](../../external/llm-failover.md)
- [이전 미수락 기록](2026-10-25_remaining-non-db-f3-unresolved.md)
