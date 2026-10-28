# 버스 scalar 독립 검토 인계 — 2026-10-29

한 일: 최신 role-manager의 `min_cell`을 보존하며 scalar NaN 검사 한 표현식을 격리 통합했습니다. 독립 합성32,939·실제공공셀50,000/사슬480·후보추정1,152·전후pytest34씩 동등, 필수관문3/3=100%입니다. 원본 제품 코드 변경0. 상세 제외·통계·통합 영수증은 [보고서](../records/reports/2026-10-29_bus-scalar-independent-continuation.md)를 봅니다.

변경 묶음: CS mobility/engine/bus_profile.py 한 표현식 + 이 보고서·검증 evidence·wiki 연결. 실제 데이터·키·고객 자료는 공유하지 않았습니다. EKS 전체 접수 성능·Linux 이미지·운영 수락은 미확인, develop/main·수동배포0. 실제 원격 결과는 보고서 후속 절로 확정합니다. 사본·실패·PG data는 보존하고 자체 PG는 종료했습니다.

양쪽 role-manager 검증 source `3e3b4b7b9f7424d66e1a6b0713883cf20d72f33e`, push/readback2/2=100%. 후속은 문서 영수증만, EKS 전체 성능·운영 수락은 별도입니다.
