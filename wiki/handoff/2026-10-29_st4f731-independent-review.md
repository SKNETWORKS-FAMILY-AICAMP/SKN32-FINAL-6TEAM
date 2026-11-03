# ST4F-731 독립 검토 인계 — 2026-10-29

한 일: 양쪽 role-manager `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0` 확인, 새 격리 사본에 원 후보만 적용, 수정 전 RED 재현, 실제 PostgreSQL 격리·권한·응답 경합 독립 시험, 필수 관문 재실행, XML/스캐너 전후 해시 검산을 했습니다. **검토 REQUEST_CHANGES·보안 HOLD 유지**, 통합·커밋·push·배포·이슈 종결 0건입니다.

기존 집중 회귀22/22·intake단위1063/1063·계약367/367·DoD26/26=100%. 보안124/125=99.2%·필수2/3=66.7% HOLD. 독립 전체10/12=83.3%, 마지막 재확인 뒤 실제 edit 커밋으로 응답 revision1/view2가 두 모드 모두 재현됐습니다(안전 단언0/2=0%). 기본 READ COMMITTED 확인; REPEATABLE READ에서 stale 재조회는 작동하지 않습니다.

바뀐 원본 경로는 새 보고서·증거·이 인계와 두 목차의 추가 링크뿐입니다. 제품 코드는 원본에 적용하지 않았습니다. 기존 후보·원본 XML·각 스캐너 바이트를 유지했습니다. 다음 담당자는 짧은 최종 반환 경계에서 kept/changed/view/revision/권한을 일관되게 만들고 독립 반례를 통과시킨 뒤, 보안 HOLD를 별도로 해결해야 합니다. 장시간 추천 계산에 잠금을 다시 넣지 않습니다.

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f731-independent-review.md) · [증거 집계](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f731-independent-review/summary.json). 전체 사본·helper·로그·pgdata는 `scratch/st4f731-independent-20261029/`에 보존했습니다. 사용자 자료·운영 서비스 변경과 삭제는 없습니다. PG 정상 종료 확인은 보고서 증거의 `pg-stop.json`을 보십시오.
