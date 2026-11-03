---
type: report
title: ST4F-731 최종 응답 경합 수정·실제 PostgreSQL 검증
status: draft
domain: travel
impl_scope: cs
---

# ST4F-731 최종 응답 경합 수정

2026-10-29T05:34:19.821500+09:00. **격리 수정·자가 검토 완료, 보안 HOLD 유지.** 원본 제품 코드·고객/운영 DB·원격 브랜치 변경, 커밋·push·배포·이슈 종결은 0건입니다. 별도 독립 검토 승인으로 표시하지 않습니다.

## 재현과 수정

[이전 독립 검토](2026-10-29_st4f731-independent-review.md)의 실제 edit 반례를 새 사본에서 다시 실행해 적용·미리 보기 **2/2 = 100%** 재현했습니다. 마지막 current_review 반환 후 별도 연결의 실제 edit(check=False)가 revision 2를 커밋하면 HTTP 200, revision 1/view.revision 2였습니다. 바깥 revision만 바꾸는 수정은 하지 않았습니다.

추천 계산은 접수 행을 잠그지 않습니다. 계산 뒤 최종 SELECT FOR UPDATE가 tenant·customer·상태·요청 revision을 확인하고, 같은 트랜잭션에서 edit와 view 확보까지 수행합니다. API의 늦은 view SELECT와 `done.get("view") or …` 폴백을 제거하고 pipeline 결과를 그대로 반환합니다. 기존 변경 미리 보기의 savepoint/rollback과 바깥 요청 판·view 가상 다음 판 계약은 유지합니다. 빈 추천은 양쪽 revision이 일치합니다.

스냅샷 격리에서 최종 잠금 조회가 받는 PostgreSQL SerializationFailure(40001)는 stale_revision 409로 전달합니다. 자동 재시도·최신 판으로 결과 재명명·격리 수준 변경은 없습니다. 오류가 트랜잭션 경계 밖으로 전달돼 롤백됩니다. 모든 직렬화 오류 위치를 포괄하는 일반 재시도 정책을 도입한 것은 아닙니다.

[설계](../evidence/2026-10-29_st4f731-response-fence/design.md), [기준선 대비 누적 6파일 패치](../evidence/2026-10-29_st4f731-response-fence/ST4F-731-correction.patch)를 남깁니다. 공통 intake/API 구현·자가 검토 담당은 이번 Codex 세션이며, 매니저·해당 API 소비자 독립 검토는 별도 남습니다. 공개 필드·권한·DB 구조 변경은 없습니다.

## 실제 DB와 시험

전용 PostgreSQL 16.15 `127.0.0.1:55518/st4f731`, 실제 data_directory가 이번 scratch/pgdata인 것을 확인했습니다. 이전 클러스터·공유·운영 DB를 재사용하지 않았습니다. 기본 READ COMMITTED이며 REPEATABLE READ·SERIALIZABLE을 명시한 연결도 시험했습니다. 외부 장소·이동 서비스는 기존 fixture double이므로 실모델·실서버·실화면 수락은 아닙니다.

| 실행한 검증 | 최종 결과 |
|---|---|
| 수정 전 실제 edit 후 응답 불일치 재현 | 2/2 = 100% |
| 최종 단일 프로세스 실DB 회귀 | 29/29 = 100%, 실패·오류·skip 0 |
| 전체 intake 단위 | 1,063/1,063 = 100% |
| 결함 변이 탐지 | 3/3 = 100%, 실패 단언 5/5 = 100% |
| 계약 최종 복귀 후 재실행 | 367/367 = 100% |
| 보안 최종 복귀 후 재실행 | 124/125 = 99.2%, 기존 XML 1실패 |
| DoD | 26/26 = 100% |
| 필수 관문 | 2/3 = 66.7%, HOLD |

실DB 회귀는 계산 중 revision·상태·customer·tenant 커밋 거부(두 모드), 최종 재확인 뒤 실제 edit 커밋 거부(두 모드), 세 격리 수준의 계산 중 revision 변경 거부, 기존 미리 보기·읽기 잠금 회귀를 포함합니다. 새 writer 스레드는 응답 구성 중 실제 edit를 시도합니다. 별도 연결의 lock_timeout probe로 최종 행 잠금을 확인하고, 응답 뒤 writer가 커밋한 판·제목이 보존되는 것을 변경 유무×두 모드 4조합으로 확인했습니다. 다른 2조합은 추천 계산 중 먼저 커밋한 실제 edit를 낡은 추천이 덮지 않음을 검사합니다. 긴 plan 안의 별도 writer에 1초 lock_timeout을 두어 계산 중 잠금 부재도 확인했습니다.

최종 확인 호출 제거·revision 비교 제거·FOR UPDATE 제거를 각각 주입했습니다. 앞의 두 변이는 실제 재확인 후 edit 반례 각 2건, 마지막은 실DB lock probe 1건에 잡혔으며 fixture 오류가 아닙니다. 매번 후보 바이트로 복귀했고 최종 원문 SHA256을 대조했습니다. 변이 실행과 최종 관문 실행은 겹치지 않습니다.

[실행별 testcase 집계](../evidence/2026-10-29_st4f731-response-fence/summary.json), [변이·복귀 해시](../evidence/2026-10-29_st4f731-response-fence/mutations.json), [DB identity](../evidence/2026-10-29_st4f731-response-fence/db-identity.json)를 보존합니다. 위 표는 격리 표본의 실행 결과이며 전체 제품 수락 분모는 모릅니다.

## 보존과 한계

원본과 격리 사본의 기존 XML SHA256은 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`로 전후 동일합니다. XML 수정·가림·이동·추적 해제·허용 예외·스캐너 약화 0건입니다. 원본과 원격 HEAD 탐지기는 시작부터 서로 달랐으며 각 위치의 시작 바이트를 유지했습니다. 검증에는 이전 독립 검토와 같은 원격 HEAD 탐지기를 사용했습니다. [전후 검산](../evidence/2026-10-29_st4f731-response-fence/preservation-final.json).

초기 시험 준비 오류(BOM, worker 실행 문맥, SQL fence를 모르는 object 연결 double, fixture import lint)를 바로잡은 뒤 재실행했습니다. 최초 독립 시험과 초기 thread 시험이 같은 전용 DB에서 겹쳤으므로 최종 실DB 묶음은 단일 프로세스로 다시 실행했습니다. 초기 단위 전체 로그는 기존 helper 재실행으로 덮였으며 실패 수·원인·콘솔 관찰을 diagnostics에 남겼습니다. 다른 초기 원시 로그와 최종 전체 로그는 scratch에 보존합니다. [진단 기록](../evidence/2026-10-29_st4f731-response-fence/diagnostics.json).

격리 HEAD는 이전 검토와 같은 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`입니다. 새 원격 fetch·최신 브랜치 통합을 하지 않았으므로 최신 원격 수락을 주장하지 않습니다. 최종 패치 역적용 --check와 git diff --check, 수정 범위 ruff는 통과했습니다. 원본 색인·sparse·Git 설정을 변경하지 않았습니다.

`C:/_proj/final_workspace/scratch/st4f731-correction-20261029/`에 실행 helper·제품 수정 전 사본·시험 원문·원시 로그·새 repo·pgdata를 모두 남겼습니다. 전용 DB는 정상 종료했고 포트 연결 거부를 확인했습니다. 새 추적 증거에는 보안 원시 로그/XML을 복제하지 않았고 기존 탐지기로 새 파일 전체를 검사했습니다. [증거 manifest](../evidence/2026-10-29_st4f731-response-fence/manifest.json).

## 재실행과 다음 작업

루트 cwd에서 다음 helper를 사용했습니다. 전용 DB가 종료됐으므로 재실행하려면 이 scratch의 클러스터만 시작하고 identity를 재확인해야 합니다. 공유 DB 주소로 바꾸지 않습니다.

```powershell
python scratch/st4f731-correction-20261029/run.py concurrency-final -m pytest tests/e2e/test_independent_st4f731.py tests/e2e/test_st4f731_response_fence.py tests/e2e/test_intake_autofix_empty_race.py tests/e2e/test_intake_read_lock.py tests/e2e/test_intake_autofix_dry_run.py -q --tb=short --junitxml=../../concurrency-final.xml
python scratch/st4f731-correction-20261029/intake_units.py
python scratch/st4f731-correction-20261029/run.py contract-restored -m pytest tests/contract -q --tb=short
python scratch/st4f731-correction-20261029/run.py security-restored -m pytest tests/security -q --tb=short
python scratch/st4f731-correction-20261029/run.py dod-final -m scripts.verify_dod_v11 --evidence-dir C:/_proj/final_workspace/scratch/st4f731-correction-20261029/dod-final-evidence
```

남은 일은 별도 독립 검토, 보존 원칙을 지키는 기존 보안 차단 해소, 최신 기준선 통합·재검증과 권한 있는 반영 판단입니다. 이 세션은 안전하지 않은 push나 운영 쓰기를 진행하지 않습니다.

? ?? ??? ?? ?????? ?? ?? ???? ???? ?? ??? ??? ??????. ??? scratch? ??? ? ???? ?? ??? ?? ?? ???? ?????, ?? ???? ? ??????? ?? ??????. ?? ?? XML? ??????? ?? ?? ??? ????.
