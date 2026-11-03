# EKS 버스 프로파일 단일값 검사 — 격리 후보 인계

2026-10-29T02:33:10.311868+09:00

한 일: 기존 프로파일 병목 재확인 → 1,461파일 해시 고정 격리 전후 사본 → `np.isnan(v)`를 `math.isnan(v)`로 한 표현식 수정 → 동일 환경 11회 교대 측정 → 별도 작업자 독립 검증 → 증거 보존·wiki 기록. 이번 범위 6/6 = 100%.

로컬 합성 cell 1.300→1.082초(16.77% 감소), 24구간 walk 0.211→0.177초(16.29% 감소). 독립 시험 7,528/7,528 = 100%. **운영 접수 전체 속도는 미검증.** 원본 제품 코드·DB·고객·모델·운영·원격 변경과 push·배포·삭제 0.

[보고서](../records/reports/2026-10-29_eks-bus-profile-scalar-performance.md) · [후보 패치](../../scratch/eks-bus-cell-20261029/candidate.patch) · [원시 측정](../../scratch/eks-bus-cell-20261029/benchmark-result.json) · [독립 검토](../../scratch/eks-bus-cell-20261029/independent/review.md).

다음 담당자는 현재 대상 브랜치와 대조 후 격리 통합·필수 관문·실제 EKS 이미지에서 재측정해야 합니다. 이번 Git 진입점은 실행 권한 오류로 실패해 snapshot SHA256으로 고정했습니다. 운영 확인 전 운영 속도 개선이나 배포 완료를 선언하지 않습니다. `_coord/Codex-eks-bus-cell-20261029-NOTICE.md`에 작업 경계를 기록했습니다. 다른 작업자의 트리는 수정하지 않았습니다.
