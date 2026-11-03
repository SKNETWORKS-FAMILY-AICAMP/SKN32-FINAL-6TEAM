---
type: report
title: EKS 서빙 후속 — 버스 프로파일 단일값 검사 로컬 개선 후보
status: draft
domain: travel
impl_scope: 격리 사본 후보만, 운영 검증·통합·배포 없음
---

# 버스 프로파일 단일값 검사 개선 후보

작성 시각: 2026-10-29T02:33:10.311868+09:00. 담당 Codex root, 독립 검토자 independent_bus_cell.

버스 프로파일 `cell()`의 `np.isnan(v)`를 `math.isnan(v)`로 바꾼 한 표현식 후보입니다. **로컬 합성 시험에서 함수 시간이 줄었으며, EKS 전체 접수 속도 개선은 검증하지 않았습니다.** 원본 제품 코드·DB·모델·운영·원격 변경은 없습니다.

## 선택 근거와 범위

[10-28 독립 검증·병목 기록](2026-10-28_eks-release-independent-verification-and-bottlenecks.md), 루트·cs 지침/RULE, 두 wiki index, 인계 index, 역할·코드 위치·이동 계약·운영 현황을 읽었습니다. 공유 `_coord`의 R/V/Hspeed와 Codex 배포 후속·ST4F711 독립 NOTICE를 확인하고 고유 `Codex-eks-bus-cell-20261029-NOTICE.md`에 소유 범위를 등록했습니다. 다른 작업자의 트리에 쓰지 않았습니다. 이번 독립 검토자에게는 `independent/`만 배정했습니다.

V가 남긴 `base_post_2.prof`를 다시 읽었습니다. `bus_profile.walk` 26,261회, `cell` 341,293회·누적 약 2.059초였습니다. [프로파일 추출·원본 SHA256](../../../scratch/eks-bus-cell-20261029/prior-profile-extract.json)을 남겼습니다. 동시 실행이 포함된 과거 로컬 cProfile이므로 시간 합산이나 운영 귀속 근거로 쓰지 않습니다. 운영의 확인 단계 약 19초가 이 함수 때문이라는 주장도 하지 않습니다.

이 후보는 float32 배열의 단일 원소에 NumPy ufunc를 호출하는 비용만 줄입니다. 자료·배열·시간대·최소 관측일·결측 처리·누적 순서·대체 규칙을 바꾸지 않습니다. 값이 NaN이면 None, 다른 값이면 기존과 같은 Python float입니다. 로더는 기존 float32 형식이며 새 캐시·패키지·DB 연결 풀·준비 상태 변경이 없습니다. 입력·출력·공유 계약 변경도 없습니다.

원본 Git 조회 진입점 `python tools/safe_git.py rev-parse HEAD`는 현재 PATH의 git 실행 권한 오류(WinError5)로 실패했습니다. 우회 Git 조회나 색인 변경은 하지 않았습니다. 따라서 커밋 기준 동일성을 주장하지 않고, 읽은 원본의 app/config/tests·설정 1,461파일을 두 격리 사본으로 복사하고 [SHA256 manifest](../../../scratch/eks-bus-cell-20261029/source-manifest.json)로 고정했습니다. `.env`·DB·고객 자료·datasets를 복사하지 않았습니다.

## 같은 환경 전후 측정

Windows 11 10.0.28000, Python 3.12.15 AMD64, NumPy 1.26.4. 동일 interpreter·동일 프로세스에 전후 모듈을 별도로 올려 동일 float32 자료와 동일 호출 인자를 넣었습니다. 워밍업 후 순서를 AB/BA로 번갈아 11회 측정했습니다. seed 20261029. 고객 입력 대신 고정 합성 버스 자료만 썼습니다. 독립 검증이 끝난 뒤 최종 측정을 실행했습니다. OS의 다른 부하는 제어하지 않았습니다.

| 측정 대상 | 회차당 호출 | 변경 전 중앙값 | 변경 후 중앙값 | 감소율 | 후보가 빠른 회차 |
|---|---:|---:|---:|---:|---:|
| cell 단일값 조회 | 524,288 | 1.299574초 | 1.081628초 | 16.77% | 11/11 = 100% |
| 24구간 전체 walk | 2,000 | 0.210970초 | 0.176613초 | 16.29% | 11/11 = 100% |

각 회차는 전후 반환값을 비교했습니다(22/22 = 100%). cell은 유효·NaN·최소 관측일 부족을 섞었고, walk는 24구간 전부 프로파일로 계산됐는지도 단언했습니다. [스크립트](../../../scratch/eks-bus-cell-20261029/benchmark.py) · [최종 원시값·환경·소스 해시](../../../scratch/eks-bus-cell-20261029/benchmark-result.json). 최초 후보의 불필요한 CRLF 변환은 독립 검토에서 발견되어 LF로 바로잡았고, 중간 파일과 최초 측정도 보존했습니다. 위 표는 수정 후 최종 소스의 재측정입니다.

재현 명령(원본 코드에서 시험하지 않습니다):

```powershell
& C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/date_risk_env_312/Scripts/python.exe -B C:/_proj/final_workspace/scratch/eks-bus-cell-20261029/benchmark.py
& C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/date_risk_env_312/Scripts/python.exe -B C:/_proj/final_workspace/scratch/eks-bus-cell-20261029/independent/verify.py
```

재실행 시 기존 결과 파일을 별도 이름으로 먼저 보존해야 합니다.

## 독립 검증

| 검사 | 결과 |
|---|---:|
| float32 셀·NaN·±inf·관측일 부족·요일·시각·분위·잘못된 인자의 값/예외 동등성 | 7,200/7,200 = 100% |
| 합성 전체 walk 무작위 동등성 | 300/300 = 100% |
| 기존 test_bus_profile_unit의 14시험 × 전후 2판 | 28/28 = 100% |
| 합계 | 7,528/7,528 = 100%, 실패·건너뜀 0 |

[독립 검토](../../../scratch/eks-bus-cell-20261029/independent/review.md) · [시험 코드](../../../scratch/eks-bus-cell-20261029/independent/verify.py) · [결과](../../../scratch/eks-bus-cell-20261029/independent/results.json). 기존 단위시험은 독립 실행기로 함수 호출했으며 전체 pytest 관문 실행으로 표현하지 않습니다. 1,461개 baseline 항목 모두 동일, candidate는 bus_profile.py 하나만 달랐습니다. 두 파일 모두 LF이며 차이는 한 표현식입니다. 최종 후보 SHA256: `66ee9286fc85938f9df2b71415394a09d706391e751f0fcb8a70b4d7a1191973`.

## 인계와 남은 검증

- [격리 후보](../../../scratch/eks-bus-cell-20261029/candidate/final_project_cs/app/domains/travel_ops/instances/mobility/engine/bus_profile.py) · [패치](../../../scratch/eks-bus-cell-20261029/candidate.patch). 원본 소스 일치는 [보존 확인](../../../scratch/eks-bus-cell-20261029/original-preservation.json)에 기록했습니다.
- 통합 담당자는 현재 대상 브랜치에서 같은 float32 단일값 호출 경로인지 대조하고 패치를 격리 통합한 뒤 현재 필수 관문(DoD·contract·security)을 실행합니다. 이번 사본은 커밋 고정 clone이 아니므로 통합 완료로 취급하지 않습니다.
- EKS 이미지의 Python/NumPy 버전에서 같은 벤치마크를 재실행해야 합니다. 운영 효과를 판정하려면 승인된 합성 계획·동일 환경·단계 로그·같은 측정 절차로 전후를 비교하고 기존 운영 쓰기/고객 보호 경계를 지켜야 합니다. 이번에는 운영 접수·고객 조회·운영 API·AWS 호출·DB 연결·유료 모델 호출이 모두 0입니다.
- EKS readiness·DB 연결 약 142회·공개 뒤 작업의 운영 기여도는 미확인 상태입니다. 이 작은 CPU 개선으로 해당 병목이 해결됐다고 판단하지 않습니다. 전체 성능 개선률의 분모는 모름입니다.
- 이번 범위의 재현·후보·전후 측정·독립 검증·증거·wiki 인계 6항목은 6/6 = 100%입니다. 통합·필수 관문·운영 확인은 후속 작업이며 완료로 세지 않습니다. push·배포 0, 삭제 0. 사본·중간 결과·합성 fixture를 모두 보존했습니다.
