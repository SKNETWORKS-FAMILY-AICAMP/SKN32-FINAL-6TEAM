---
type: report
title: ST4F-731 후보 독립 검토 — 응답 revision 경합 잔존
status: draft
domain: travel
impl_scope: cs
---

# ST4F-731 후보 독립 검토

2026-10-29 KST. **검토 결과는 REQUEST_CHANGES이며 보안 HOLD를 유지합니다.** 계산 중 변경을 거부하는 부분 개선은 확인했지만, 마지막 재확인 뒤 응답을 읽는 경합이 남습니다. 병합·커밋·push·배포·이슈 종결은 하지 않았습니다.

## 발견한 결함

**[P2] 빈 추천의 재확인과 응답 view가 같은 판을 보장하지 않습니다.** 후보 `pipeline.py:1122`의 `current_review`가 반환된 뒤 다른 연결에서 실제 `pipeline.edit(..., check=False)`가 revision 2를 커밋하게 했습니다. 적용과 미리 보기 모두 HTTP 200, 바깥 `revision: 1`, `view.revision: 2`를 반환했습니다. 미리 보기의 view는 `pipeline.py:1124`, 적용의 view는 `entry/trip_api.py:1978`에서 나중에 읽습니다. 단순 revision SQL 변경만 사용한 반례를 실제 편집 경로로 다시 검증한 결과도 **2/2 = 100% 재현**입니다. 기존 후보 시험은 계획 계산 안에서만 변경을 주입해 이 구간을 놓칩니다.

수정 담당자는 잠금 없는 긴 추천 계산을 유지하면서, 최종 상태·접근 권한·판 검사와 응답 view가 한 판에 속하도록 반환 경계를 정리해야 합니다. 바깥 revision만 최신 값으로 바꾸면 이전 판으로 계산한 kept/changed가 최신 판의 결과처럼 보이므로 충분하지 않습니다. 새 시험은 409 또는 일관된 한 판의 응답을 요구하며, 현재 후보에는 두 모드 모두 실패합니다. 이 검토에서는 제품 수정안을 추가하지 않았습니다.

## PostgreSQL 격리 확인

독립 PostgreSQL 16.15를 `127.0.0.1:55517/st4f731`에 새로 만들었습니다. DB identity·실제 data_directory가 이번 scratch 아래인 것을 단언했으며 유일한 DATABASE 환경 주소도 이 클러스터였습니다. 원본·공유·운영 DB는 사용하지 않았습니다. 앱 연결과 서버 기본 격리 수준은 `read committed`입니다.

기본 수준에서는 계산 중 별도 연결이 커밋한 revision·상태·customer·tenant 변경을 두 모드에서 거부했습니다(**8/8 = 100%**). 조회 동안 다른 연결의 쓰기에 1초 lock_timeout을 두어 긴 추천 계산이 접수 행 잠금을 쥐지 않는 것도 확인했습니다. 그러나 최종 재확인 이후 새 view SELECT는 다음 커밋을 보므로 위 불일치가 생깁니다.

명시적인 `REPEATABLE READ` 연결에서는 같은 계산 중 커밋이 재확인에 보이지 않아 이전 revision으로 성공합니다. 독립 시험은 이 차이를 **2/2 = 100% 관측**한 것이며, 두 격리 수준에서 stale 방어가 통과했다는 뜻이 아닙니다. `get_connection`은 격리 수준을 지정하지 않고 DB 기본값을 따릅니다. 운영 DB의 실제 기본값은 이번 범위에서 조회하지 않았습니다. [PostgreSQL 16 공식 격리 문서](https://www.postgresql.org/docs/16/transaction-iso.html)의 SELECT 스냅샷 설명과 일치합니다.

## 이번 실행 결과

| 검증 | 결과 |
|---|---|
| 후보 변경 제거 후 기존 새 회귀 재현 | 실패 8/10, 통과 2/10 = 20% |
| 후보 복귀 후 집중 단위·실DB·읽기잠금·미리보기 회귀 | 22/22 = 100% |
| 독립 전체 시험: 경합 방어·격리 관찰 | 10/12 = 83.3%, 응답 일관성 2실패 |
| 독립 실제 edit 경로로 마지막 경합 재검증 | 안전 단언 0/2 = 0%, 반례 재현 2/2 = 100% |
| 전체 intake 단위 | 1,063/1,063 = 100% |
| 계약 | 367/367 = 100% |
| 보안 최종 재실행 | 124/125 = 99.2%, 보존 XML 검사 1실패 |
| DoD 최종 재실행 | 26/26 = 100% |
| 필수 관문 | 2/3 = 66.7%, HOLD |

최종 집계에서 skip은 없습니다. 독립 전체 통과 10건에는 REPEATABLE READ의 방어 부재를 관측한 시험이 포함되므로 안전성 통과율로 일반화하지 않습니다. 최초 독립 시험은 잘못된 상태값·없는 소유자 때문에 DB 제약/teardown 실패가 있었으며 수정 뒤 다시 실행했습니다. 최초 로그와 중단된 초기 실행도 scratch에 보존했습니다. 첫 Git 실행 경로 접근 실패, 중단한 로컬 clone 시도, CRLF 때문에 생긴 helper 준비 실패도 제품 실패로 세지 않았습니다.

후보를 잠깐 제거하는 RED 실행 뒤 원 바이트로 복귀·검산했습니다. RED 실행과 겹쳤던 초기 보안/DoD 결과에 의존하지 않도록 원 후보를 복귀한 뒤 최종 보안과 DoD를 다시 실행했습니다. 계약과 전체 intake 단위도 후보 원문에서 실행했습니다.

## 기준선·보존·인계

팀과 개인 role-manager는 작업 전후 모두 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`로 확인했습니다. 기존 후보의 3파일 패치만 새 격리 사본 `scratch/st4f731-independent-20261029/repo3`에 적용했습니다. 원본 제품·Git 색인·sparse 설정은 변경하지 않았습니다. 현재 원본과 원격 문서의 차이는 통합하지 않았습니다. 원본/원격의 프로젝트 지침, RULE, wiki 계약·역할, `_coord` NOTICE 48개를 읽고 기존 729 HOLD 및 다른 담당 경계를 유지했습니다.

보존 XML SHA256은 원본과 격리 사본 모두 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`이며 전후 불변입니다. XML 수정·가림·이동·추적 해제·허용 예외는 없습니다. 보안 탐지기도 각 위치의 시작 바이트를 그대로 유지했습니다. 원본과 원격 탐지기는 작업 시작부터 서로 달랐으며, 검증에는 원격 HEAD 탐지기를 사용했습니다. checkout 줄바꿈 차이를 제외한 HEAD 일치와 각 위치의 전후 원시 해시는 별도로 남겼습니다. **새 허용 목록·분류·스캐너 약화 0건**입니다.

[실행 집계](../evidence/2026-10-29_st4f731-independent-review/summary.json), [실제 편집 반례](../evidence/2026-10-29_st4f731-independent-review/real-edit-boundary.log), [독립 시험 원문](../evidence/2026-10-29_st4f731-independent-review/independent-real-edit.py), [보존 검산](../evidence/2026-10-29_st4f731-independent-review/preservation-final.json), [DB identity](../evidence/2026-10-29_st4f731-independent-review/db-identity.json)를 보존합니다. 전체 실행 helper·원시 실패·보안 원시 로그·최종 DoD JUnit·pgdata·중단한 사본은 `scratch/st4f731-independent-20261029/`에 그대로 남깁니다. 보안 원문을 새 추적 문서에 복제하지 않았습니다.

남은 일은 응답 경합 수정 → 새 독립 시험 재실행 → 보존 원칙을 지키는 별도 보안 차단 해소 → 최신 기준선 필수 관문 → 권한 있는 통합 판단입니다. 실모델·실화면·운영 수락은 이 검토 범위가 아니며 전체 제품 수락 분모는 모릅니다. 본 이슈에 남은 결함과 관문 확인을 우선해 다른 미담당 이슈는 시작하지 않았습니다.


## 실행 재현 진입점

이번 scratch에서 `python verify.py`는 후보 바이트를 보관한 뒤 RED/복귀/GREEN을 순서대로 실행했습니다. `run.py`는 setup.json의 준비된 Python 3.12·격리 cwd·비공개 환경을 사용하며 로그를 scratch에 남깁니다. 저장한 테스트 원문 두 판과 helper를 함께 보존했습니다.

실행한 핵심 명령은 다음과 같습니다(루트 cwd 기준).

```powershell
python scratch/st4f731-independent-20261029/verify.py
python scratch/st4f731-independent-20261029/run.py independent-final -m pytest tests/e2e/test_independent_st4f731.py -q --tb=short
python scratch/st4f731-independent-20261029/run.py real-edit-boundary -m pytest tests/e2e/test_independent_st4f731.py -k noop_preview -q --tb=short
python scratch/st4f731-independent-20261029/intake_units.py
python scratch/st4f731-independent-20261029/run.py contract -m pytest tests/contract -q --tb=short
python scratch/st4f731-independent-20261029/run.py security-final -m pytest tests/security -q --tb=short
python scratch/st4f731-independent-20261029/run.py dod-final -m scripts.verify_dod_v11 --evidence-dir C:/_proj/final_workspace/scratch/st4f731-independent-20261029/dod-final-evidence
```

독립 전체 최초 최종 실행은 SQL writer 판, 마지막 두 반례 실행은 실제 edit writer 판입니다. 두 시험 원문을 각각 보존했으며 현재 격리 파일은 실제 edit 판입니다. DB는 종료됐으므로 다시 실행하려면 이번 전용 클러스터만 기동해야 합니다. 공유 DB 주소로 바꿔 실행하지 않습니다.
