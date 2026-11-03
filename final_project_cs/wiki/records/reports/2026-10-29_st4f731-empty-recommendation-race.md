---
type: report
title: ST4F-731 변경 없는 추천의 판 변경 경합 수정 후보
status: draft
domain: travel
impl_scope: cs
---

# ST4F-731 변경 없는 추천의 판 변경 경합 수정 후보

2026-10-29 KST. [실측] **격리 수정·검증 완료, 통합 HOLD입니다.** ST4F-729 증거 보존 HOLD와 보안 검사를 그대로 유지했습니다. 검증자는 현재 Codex 세션이며 독립 검토 승인·운영 수락은 미확보입니다.

## 선택과 협업 경계

최신 TeamFlow 전체 688건의 GET에서 미완료 102/688 = 14.8%였습니다. 담당자 빈 값인 high 항목 중 724는 T의 기존 보안 갱신 후보 통합 대기, 729는 명시적 보존 HOLD, 708은 앞선 독립 검증에서 새 결함이 없었습니다. 전체 `_coord` NOTICE를 대조하고 예약 없는 high 결함 731을 선택했습니다. 현재 세션 NOTICE에 격리 범위를 알렸으며 다른 작업자의 응답·독립 승인으로 취급하지 않았습니다. S3·589·597·EKS와 원본 제품 코드는 수정하지 않았습니다.

새 독립 clone 기준은 `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0`입니다. 원본 Git 명령·색인·설정 변경은 없습니다. 원격과 원본의 규칙·wiki·CS RULE·현재 `web-intakes` 계약과 731 기존 시험을 확인했습니다.

## 원인과 수정

[실측] `pipeline.autofix`는 추천 계산 중 판이 바뀌었을 때 변경 항목이 있으면 `edit`의 충돌 검사로 거절했습니다. **변경 항목이 없으면 그 검사를 거치지 않아** 이전 판의 `revision`과 결과를 성공 반환했습니다. `dry_run`에서는 새 판의 `view`와 이전 판의 바깥 `revision`이 섞일 수도 있었습니다.

변경 없는 분기에서 기존 `current_review`를 한 번 더 호출해 본인 접수·상태·판을 다시 확인합니다. 새 필드·오류 종류·업무 규칙을 만들지 않았고, 쓰기 잠금·고정/예약 보호·보안 검사는 유지했습니다. 제품 변경은 해당 분기 3줄, 회귀 시험은 단위·DB 각 1파일입니다. 새로운 공유 계약 변경이 아닌 기존 낡은 판 거절 계약의 누락 보완입니다.

## 실행 증거

| 검사 | 결과 |
|---|---|
| 새 단위 재현, 수정 전 | 실패 6/8, 정상 통과 2/8 |
| 수정 후 새 단위 + 기존 잠금 단위 | 12/12 = 100% |
| 실제 PostgreSQL 두 연결의 새 경합, 수정 전 | 결함 재현 2/2 = 100% |
| 수정 후 새 경합 + 기존 읽기 잠금 + 미리 보기 DB 시험 | 10/10 = 100% |
| `test_intake*.py` 단위 전체 | 1,063/1,063 = 100% |
| `tests/contract` | 367/367 = 100% |
| `tests/security` | 124/125 = 99.2%, 기존 XML 실패 1 |
| `scripts.verify_dod_v11` | 26/26 = 100% |
| 필수 3관문 | 2/3 = 66.7%, HOLD |
| ruff F·E9 / 패치 공백 검사 | 모두 exit 0 |

단위 시험은 계산 중 판·상태·접근 가능 여부가 바뀐 경우의 기존 오류 전파와 정상 빈 결과를 검사했습니다. DB 시험은 이 세션이 새로 만든 loopback 전용 PostgreSQL에 여행 시험 자료만 넣고, 다른 연결에서 판을 올린 뒤 409 `stale_revision`, claims/reviews 추가 없음, 변경된 판 유지까지 확인했습니다. 기존 시험으로 읽기는 쓰기를 기다리지 않음·쓰기끼리 대기·변경 있는 미리 보기 충돌·세이브포인트 보존을 확인했습니다. 실제 후보 대기 3초 이하 또는 운영 성능은 이번 실행의 측정 대상이 아닙니다.

명령은 격리 CS cwd의 `python -m pytest tests/unit/travel/test_intake_autofix_empty_race.py tests/unit/travel/test_intake_read_lock.py -q`, `python -m pytest tests/e2e/test_intake_autofix_empty_race.py tests/e2e/test_intake_read_lock.py tests/e2e/test_intake_autofix_dry_run.py -q`, `test_intake*.py` 목록 전체, 필수 관문 세 명령, `python -m ruff check --select F,E9`입니다. 준비된 Python 3.12 환경을 사용했습니다.

최초 단위 수집은 환경 변수 미설정, 최초 계약/DoD 및 넓은 단위 수집은 sparse 의존성 누락으로 실패했습니다. 환경·추적된 Composer 공통 인프라/eval/knowledge 경로를 준비하고 필요한 시험을 재실행했습니다. 쇼핑몰 평가·데이터는 실행하지 않았습니다. `pg_ctl` 파이프 상속으로 대기한 준비 runner만 중단하고 파일 로그로 재개했습니다. 최종 로그와 초기 실패 로그 모두 작업 폴더에 보존합니다.

## 보존과 통합 인계

기존 728 XML SHA256 `4139dd065887867094dd053a5e9de007697efe039a57a64b200dd15584bd3a0a`는 원본/clone 모두 동일합니다. 해당 파일의 가리기·이동·삭제·추적 해제·검사 예외는 없습니다. 검사기도 HEAD 바이트 그대로이며 새 변경 파일 3/3 = 100%에 기존 검출기를 적용해 통과했습니다. 기존 XML 실패를 이번 수정 탓으로도, 해결된 것으로도 보고하지 않습니다.

[패치](../evidence/2026-10-29_st4f731-empty-recommendation-race/ST4F-731.patch), [시험 집계](../evidence/2026-10-29_st4f731-empty-recommendation-race/summary.json), [보존 확인](../evidence/2026-10-29_st4f731-empty-recommendation-race/preservation.json), [manifest](../evidence/2026-10-29_st4f731-empty-recommendation-race/manifest.json)를 보존합니다. 실행 helper·전체 원시 로그·트래커 조회 원문·격리 DB·코드 수정 전 사본은 `scratch/teamflow-continue-20261029-044902/`에 있습니다. 원시 보안 로그와 트래커 비공개 원문은 추적 산출물에 복사하지 않습니다.

매니저 통합 담당자는 최신 기준선과 패치를 대조하고 영향받는 공통 intake 경로를 검토해야 합니다. **현재 필수 보안 관문 실패가 남아 있으므로 병합·커밋·push·배포는 하지 않았습니다.** 원본 제품 코드·고객 데이터·운영 DB 변경 0입니다. 화면 변경이 없어 새 브라우저 검증은 수행하지 않았고 실제 모델·실제 서버·운영 수락과 전체 제품 시험 분모는 미확보입니다. 이슈 종결은 하지 않습니다.

## 관계

- [729 보존 판정·708 이전 검증](2026-10-29_st4f729-policy-review-and708.md)
- [기존 낡은 판 거절 API 계약](../../external/rest-endpoints/web-intakes.md)
- [CS 통합 규칙](../../../RULE.md)

## 최종 재조회

[실측] TeamFlow 설명 근거 추가 1회 후 개별 GET과 전체688건을 다시 조회했습니다. 바뀐 이슈는731 하나이며 desc·updatedAt만 변경, review·미담당 유지·종결0입니다. 남음102/688=14.8%. [트래커 영수증](../evidence/2026-10-29_st4f731-empty-recommendation-race/tracker-receipt.json)과 [전체 재조회·DB 종료](../evidence/2026-10-29_st4f731-empty-recommendation-race/final-readback.json)를 보존합니다. 이 세션 PostgreSQL은 정상 종료했고 포트가 닫힌 것을 확인했습니다. pgdata·로그·사본은 모두 보존했습니다.
