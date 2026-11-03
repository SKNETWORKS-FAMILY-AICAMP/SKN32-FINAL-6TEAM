---
type: report
title: EKS Linux 전체 원본 자료 기준선 재현과 시각·정밀표 원인 경계
status: draft
domain: travel
---

# EKS Linux 전체 원본 자료 신뢰성 후속

2026-10-29 KST. **PR110 draft·배포 HOLD, 운영 fatal 원인 미확정**입니다. 지정 [reader 관측 인계](../../handoff/2026-10-29_eks-reader-observability-boundary.md)와 현재 PR110 본문을 읽고, 운영 로그 권한을 늘리는 대신 Linux 기준선을 재현했습니다. 전체 운영 검증의 분모 모름. 원래 운영 baseline review2/3=66.67%·fatal1/3=33.33%는 변경하지 않았습니다.

## 한 일 목록과 자료 완전성

- root/cs AGENTS·RULE, 양쪽 wiki 색인, 개발 역할, Mobility 계약, datasets README·Mobility REPORT·공식 정밀표 REPORT, 이전 Linux37·checking16·reader 관측 보고와 실제 coordination notice를 읽었습니다. 새 no-hardlinks 사본 `C:/_proj/ekslinuxreliability1029/repo`는 배포 main `57f3d2f004d0600f781599a6a92e8691b49bef82`입니다. 원본 Git·제품·설정·색인은 변경하지 않았습니다.
- 이전 공개 입력 61파일은 기존 cohort의 입력이지 **로컬 전체 원본 113파일과 같지 않았습니다.** 추가52파일에는 과거 그래프·다른 판의 보행 그래프·백업·복구 판이 있습니다. 어느 것을 폐기하거나 최신판으로 교체하지 않았습니다. 기존61파일 198,774,816바이트를 먼저 그대로 대조하고, 원본 `datasets/mobility/processed/mobility`의 **113/113=100%, 289,950,471바이트**를 별도 `full-original/processed/mobility`로 복사해 원본 전후/사본 SHA256을 확인했습니다. 백업까지 보존한 파일 완전성이며, 모든 그래프 판을 동시에 제품에서 사용한다는 뜻은 아닙니다. 원자료 CSV는 원본에서 읽기만 했습니다. [전체 manifest](../evidence/2026-10-29_eks-linux-full-original-reliability/full-original-inputs.json).
- Linux ARM64 Python3.12.16/NumPy1.26.4에서 네트워크 연결을 차단하고 mock 설정으로 실행했습니다. DB/listener 생성, 실제 모델/provider 호출, 운영 접수·상태 변경은0입니다. 이번 검증을 새 AMD64·EKS 이미지 검증으로 부르지 않습니다.

## 같은 216개 단언과 원인 분리

61파일 cohort와 전체113파일 cohort 각각 **180/216=83.33% 통과, 36실패, skip0/error0**입니다. node별 결과 **216/216=100% 일치**, 이전36실패 집합과도 일치하고 새 실패0입니다. 자료 전체 공급으로 이36건이 해결되지는 않았습니다. 기존 precision·단언·golden·정밀도·허용오차·게이트·제외 마커는 변경하지 않았습니다. [집계와 시각 차이 경로](../evidence/2026-10-29_eks-linux-full-original-reliability/summary.json)·[전체 원본 XML](../evidence/2026-10-29_eks-linux-full-original-reliability/full-original.xml)·[61파일 XML](../evidence/2026-10-29_eks-linux-full-original-reliability/baseline-full-v2.xml).

| 원인 분류 | 실패 / 36 | 이번 확인·남은 수락 |
|---|---:|---|
| 정밀 시간표와 기대값 불일치 | 18/36=50.00% | 원래 단언18건 실패 유지. 반환값을 바꾸지 않는 관찰기로 실제 MISS·선택 구간·공식 도착초 근거를 보존. 이전 precision 비활성 진단의 통과를 이번 수정으로 세지 않음 |
| 벽시계가 전체 결과 비교에 포함 | 2/36=5.56% | 정상 끼어들기 비교와80건 스레드 결과의 차이는 departure_context/captured_at 경로뿐. 같은 원본 단언/음성 대조/싱글턴 보호를 유지한 시계 고정 대조 2/2=100% 통과. 제품에서 시각을 제거하거나 고정하지 않음 |
| 택시 기대값·현재 산식/예산 | 7/36=19.44% | 기존 독립 금액 분해와 같은 실패, Mobility·매니저 도메인 수락 남음 |
| 경로/이유 봉투 기대값 | 7/36=19.44% | 현재 버스 대안·이유 봉투·earliest 조건의 기존 실패 유지, 계약 수락 남음 |
| 계획 golden | 2/36=5.56% | 시각만의 차이가 아닌 현재 경로·departure_context 차이. 덮어쓰기/재생성0 |

시각 대조는 원인 분리이며 canonical 실패2건을 닫은 것이 아닙니다. 전체113파일을 사용한 기존 정밀표/선택 열차 경계 시험 **23/23=100%, skip0**도 확인했습니다. 새 테스트 완화나 제품 수정 없이 수행했습니다. [18건 실제 MISS·선택 근거](../evidence/2026-10-29_eks-linux-full-original-reliability/precision18.json)·[원본 CSV 대조 지지 범위](../evidence/2026-10-29_eks-linux-full-original-reliability/oracle-support.json).

18건 중 선택 구간16건과 대안2건 모두 해당 도착초가 공식 원본 행에 대응함을 **18/18=100%** 확인했습니다. MIX-03은 원래 단언11:06에 대해 열차2169의 성수11:03 도착+하차 후2분=11:05, MULTI-03은 원래 최단 도착14:05에 대해 열차2252의 잠실14:04입니다. 두 원래 단언은 별도 재생에서도 실패로 보존했습니다. [대안의 실제 선택 구간](../evidence/2026-10-29_eks-linux-full-original-reliability/alternatives-origin.json). 이는 도착초의 출처 대응 확인이며 환승/여유/대안 전체 기대값의 독립 승인이나 실운행 정확도100%가 아닙니다.

## 공식 CSV 전체 대조의 정확한 한계

공식 압축 CSV 해제 SHA256은 보조표 source_sha256과 같습니다. **423,107행 전체**를 읽고 2·3호선 **104,614행 전체**를 노선·요일·방향·열차코드·역·도착초·출발초의 다중집합으로 대조했습니다. 원값 그대로 일치하는 것은 **104,613/104,614=99.9990%**입니다. 교대 토요일 하행 열차3305의 도착 `00:00:00` 한 칸이 보조표에서는 null입니다. 현 `seconds()`가0초를 받지 않는 동작과 맞지만 원값 무변경이라고 주장하지 않습니다. 0초→null 정규화를 명시하면 **104,614/104,614=100%**, 추가/누락0입니다. 이것만으로 운영 운행 정확도나36실패 해결을 주장하지 않습니다. [원시 차이와 정규화](../evidence/2026-10-29_eks-linux-full-original-reliability/source-normalization.json). 이 차이의 의미는 Mobility 자료 담당 검토 대상으로 남기며 원본/보조표는 바꾸지 않았습니다.

## 실패한 준비 시도·보존·담당

최초 네트워크 차단기가 RuntimeError를 던져 runtime의 자료 부재 처리로46건이 skip됐습니다(145통과·25실패·46skip). 이 실행은 재현 준비 오류로 보존하고 canonical 집계에 합치지 않았습니다. OS의 연결불가 OSError를 쓰고 명시적으로 외부 라우터를 끈 뒤 같은 단언216개를 skip0으로 재실행했습니다. 최초 CSV 감사의 요일코드 END 매핑 누락과0초/null 차이 실패, 대안 직접 helper의 CLI 자료 경로 초기화 누락, 집계 스크립트 괄호 오류와 그 뒤 의존 파일 부재도 준비 실패로 남겼습니다. 제품 실패/통과로 세지 않습니다. 기다리기만 하던 자체 부모 프로세스2개는 cmdline·자식없음을 확인하고 병렬 검증으로 재배치했으며 실행 중 시험·다른 작업자 프로세스는 중단하지 않았습니다.

담당은 Codex입니다. `_coord/Codex-eks-linux-reliability-20261029-NOTICE.md`에 범위와 HOLD를 게시했습니다. **Mobility 담당은18개 정밀표 기대와0초 정규화·현재 경로/요금/golden 수락, 매니저는 릴리스 관문·독립 검토 연결을 검토할 필요가 있습니다.** 연락 확인·승인·상시 인명 배정을 받은 것으로 표시하지 않습니다. 자체 검증이며 독립 검토자 미배정, main 통합 예약 없음입니다. 모든 사본·원본 XML·관찰기·실패 시도·해시는 `C:/_proj/ekslinuxreliability1029`에 보존하며 삭제0입니다.

다음은 원본18개 기대와 공식 근거의 사례별 수락 및 결정적 시계 fixture의 검토입니다. 시험/golden 갱신을 자동 승인하지 않습니다. 전체113파일과 기존61파일의 결과가 같다는 사실만으로 서비스 정확도를 승인하지 않습니다. 운영 reader는 기존 허용된 앱 로그의 좁은 category 집계가 확보되기 전까지 원인 미확정/HOLD입니다. **자격증명·권한·workflow 생성/변경·dispatch·push·병합·배포0**입니다. [최종 읽기·113파일 재검증](../evidence/2026-10-29_eks-linux-full-original-reliability/final-readback.json)·[인계](../../handoff/2026-10-29_eks-linux-full-original-reliability.md).

문서 검증: 새 보고/인계/증거 직접 검사16/16=100%, JSON/XML/링크 정상입니다. 전체 staged 공백 검사 exit2는 원시 pytest XML 두 파일의 후행 공백만 보고했습니다. 원시 증거를 보존하며 문서·JSON 범위 공백 검사 exit0과 구분합니다. 전체 저장소 보안/통합 관문을 새로 통과했다고 주장하지 않습니다. [검증 범위](../evidence/2026-10-29_eks-linux-full-original-reliability/validation.json).
