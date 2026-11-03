---
type: handoff
title: EKS checking AMD64 해소·운영 기준 fatal HOLD
status: draft
domain: travel
---

# EKS checking 후속 인계

**병합·배포0, HOLD입니다.** [보고서](../records/reports/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal.md)·[집계](../records/evidence/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal/final-verdict.json)를 먼저 봅니다.

한 일 목록:

- root/cs 규칙·wiki·실제 release coordination 대조, 새 no-hardlinks `C:/_proj/ekscheckingcontinue1029/repo`에 checking 후보만 적용. 원본 제품/Git 설정 변경0.
- 실제 배포 Dockerfile의 AMD64 이미지에서51/51 = 100% 회귀 통과. 첫 dummy 설정 누락 실패 보존. CI40774763719와 PR40775273306 각각 필수3/3 = 100%, 전체13324통과/466skip/0실패.
- 전용 PG16.15·63915 전체출력/이벤트14/14·20쌍, 필수26/368/125 및 architecture170 통과. 자체 PG 종료·연결거부·자료 보존.
- Linux16 그대로16실패/0통과, 원인16/16 설명. taxonomy·금액 분해·버스/첫차/시계고정 probe 보존. gate/golden/precision 변경0.
- 전체 mobility_full 기준과후보 각각180/216 = 83.33% 통과/36실패, 결과216/216 = 100% 동등·새실패0. 공개자료61·제품52·시험163 해시 불변.
- 기존 운영 main57f3d2f004d0/CD40754585676 앱4/4 ready·public2/2 확인. 같은6항목 control3/3 성공은 cap미초과여서 따로 보존.
- 7일42항목 EKS 기준3회: review2/3 = 66.67%, fatal1/3 = 33.33%. 원래 실패코드 미수집, 원인 확정 못 함. 별도1회 코드/항목수 진단은 원래 실패를 지우지 않음. 진단 `{"first_at": {"accepted": 14.57, "progress": 17.35, "beat": 17.66, "stage:fatal": 138.2, "result": 139.24}, "total_to_get_s": 142.86, "status": "fatal", "fatal_code": "reading_model_failed", "fatal_detail_class": "model_unavailable", "assembled_items_n": null, "review_items_n": 0, "risk_status_counts": {}, "risk_code_counts": {}}`.
- [PR110](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/pull/110) draft/open·head3fda4eee2613d89d56a6d146989de8f96c229852, main 불변. 후보 배포/후측정0. 릴리스 예약 HOLD 해제.

다음 작업은 기존 운영 fatal의 원인·영향을 안전한 운영 로그/관측 경로로 판정하는 것입니다. 시각과 합성 접수 해시는 private before JSON에 남아 있으나 쿠키/CSRF/실제 ID는 저장하지 않았습니다. 허용된 경로가 없으면 권한을 넓히거나 다른 고객 자료를 읽지 말고 그 한계를 유지합니다. 실패를 무시하거나 성공 재시도로 원래3회 분모를 바꾸지 않습니다. 그 뒤에만 최신 main/coord와 모든 관문을 재확인하고 정상 보호 PR 병합·main CI·기존 CD·실제 digest/readiness 및 같은42항목 후보 후측정을 진행합니다. dormant `merge_when_validated.py`는 원래3회 전부 review가 아니면 mutation 전에 실패하므로 지금 실행하지 않습니다.

전체 운영 검증 분모 모름. direct pod/RDS·실제 SELECT/provider횟수·cold/warm 인과측정 미확보. 자료 삭제 승인 없으며 합성 guest7건·사본·PG·로그 모두 보존합니다. 상세 재현 명령/모든 원 로그는 `C:/_proj/ekscheckingcontinue1029`에 있습니다.

최종 문서 링크/JSON·기존 추적 텍스트 보안12/12 = 100%, 마지막 기존 운영 HTTP2/2 = 100% 확인. 합성 추가 진단은 reading_model_failed/model_unavailable이며 원래3회 실패를 덮지 않습니다. 새 문서 검증을 위해 격리 repo에 문서/증거를 stage했으나 커밋/PR head는 바꾸지 않았습니다.
