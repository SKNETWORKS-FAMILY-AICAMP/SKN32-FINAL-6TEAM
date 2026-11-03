---
type: report
title: EKS Linux 정밀 시간표 기대값 18건 정정과 전체 기준선 비교
status: draft
domain: travel
---

# EKS Linux 정밀 시간표 기대값 후속

**기존 실패 18/36 = 50.00% 해소, 후보 198/216 = 91.67% 통과·18실패·skip0. PR110 draft/HOLD는 유지합니다.** 실제 EKS fatal 원인은 이번 작업으로 밝혀지지 않았으며 운영 반영은0입니다. 기존 운영 baseline 성공2/3=66.67%·fatal1/3=33.33%는 그대로 보존하고, 전체 운영 검증 분모는 모릅니다.

## 원인과 수정 판단

지정 인계 `2026-10-29_eks-linux-full-original-reliability.md`, 루트/cs AGENTS·RULE·wiki 색인·개발 역할·Mobility 계약과 coord를 읽었습니다. main `57f3d2f004d0600f781599a6a92e8691b49bef82`를 no-hardlinks 격리 사본으로 복제했습니다. 담당은 Codex이며, 독립 Codex 검토자는 공식 CSV 원문을 별도로 읽고 수정값과 실제 후보 diff/XML을 검토했습니다. Mobility 담당 승인·Claude 검토·릴리스 승인을 받은 것으로 표시하지 않습니다. [독립 검토](../evidence/2026-10-29_eks-linux-precision-expectations/independent-review.md).

지배 그룹18/36=50.00%는 **2026-10-12 공식 도착초 계약 도입 후 남아 있던 평균시간 기대값**입니다. 현재 [공식 열차 도착초 계약](../../../final_project_cs/wiki/teams/mobility.md)은 유일한 편성·경로 대응 때 공식 예정 도착초를 사용하며 마지막에 분 단위로 올리도록 정합니다. 동일 날짜·출발·구간인 R-BASE-01은 이미14:04인데 R-BASE-02/MULTI-03은14:05인 모순도 있었습니다. 공식 CSV423107행의 SHA-256이 기존 자료/설치 보조표 근거와 일치하고, 관련 원문14행을 독립 검토했습니다. 예정 시간표 검증이며 실제 도착 정확도 보장이 아닙니다.

6개 회귀 JSON의18개 사례에서 기대 필드20개만 정확한 값으로 고쳤습니다. R-BASE-02는14:04·여유16, R-BUFFER-01/J-SLACK-02는 여유-2, R-ORIG-02는14:05:30을 올린14:06, MIX-03은 공식11:03+기존 이탈2분=11:05, CAR-09는14:04+기존 택시 올림17분=14:21입니다. J-WORST-03은24:45로 고치되 마진25와 막차 검사는 유지했습니다. 옛 산식 설명은 이력임을 명시하고 공식 원문 표본 fixture를 추가했습니다. [20개 필드 전후](../evidence/2026-10-29_eks-linux-precision-expectations/expectation-changes.json)·[원문 근거](../evidence/2026-10-29_eks-linux-precision-expectations/official-facts.json).

편집한6묶음92/92=100%에서 사례 수·순서·입력·기대 키·다른 단언이 보존됐습니다. 판정·사유·허용오차·마진·버퍼·막차·경고·대안 수/축·tie는 변경하지 않았습니다. 제품 코드·시험 코드·golden·precision 기능·마커·제외 조건 변경0입니다. [의미 비교](../evidence/2026-10-29_eks-linux-precision-expectations/semantic-verification.json).

## Linux 실행 결과

Linux ARM64 Python3.12.16/NumPy1.26.4에서 mock provider와 외부 연결 차단을 유지했습니다. 두 사본에 동일한 원본113/113=100%,289950471바이트를 실제 복사해 SHA-256을 확인했고, DATA_DIR도 같은 보존 사본을 가리켰습니다. 원본113파일의 재검산도113/113=100% 일치했습니다. 백업/과거 그래프를 버리거나 교체하지 않았습니다. [입력 비교](../evidence/2026-10-29_eks-linux-precision-expectations/input-comparison.json)·[원본 재검산](../evidence/2026-10-29_eks-linux-precision-expectations/original-input-readback.json).

| 실행 | 수정 전 | 후보 |
|---|---:|---:|
| 전체 Mobility층 | 180/216=83.33%·36실패·skip0 | 198/216=91.67%·18실패·skip0 |
| 기본 Mobility 관문 | 1606/1607=99.94%·1skip | 1606/1607=99.94%·1skip |
| 계약 | 368/368=100% | 368/368=100% |
| 보안 | 125/125=100% | 125/125=100% |
| 아키텍처 | 170/170=100% | 170/170=100% |
| DoD | 26/26=100% | 26/26=100% |

전체층 node 집합216/216=100% 동일, 새 기준선의 실패36건은 보존된 기존36건과 일치합니다. 정확히 검토한18건만 통과로 바뀌었고 새 실패0입니다. 기본 관문의 유일한 skip은 원본에도 없는 건물 출입구 자료가 필요한 기존 시험입니다. skip을 통과로 세거나 시험을 제외하지 않았습니다. 필수3/3=100% 통과와 전체층18실패를 구분합니다. [전체 비교](../evidence/2026-10-29_eks-linux-precision-expectations/comparison.json)·[관문과 skip 사유](../evidence/2026-10-29_eks-linux-precision-expectations/gate-summary.json).

정밀 연결/선택편성 경계23/23=100% 통과. 별도 음성 대조에서 정밀표 연결을 제거하면 수정한 원래18개 시험18/18=100%가 실패했습니다. 이 실험은 제품 수정이나 canonical 통과에 합산하지 않았으며, 옛 평균시간 계산의 재유입을 새 기대값이 잡는다는 증거입니다. [음성 대조 XML](../evidence/2026-10-29_eks-linux-precision-expectations/precision-negative-control.xml).

실행은 `python -m pytest tests/unit/travel/mobility -m "mobility_full and not live" -q -rs --tb=short`, 기본 `python -m pytest tests/unit/travel/mobility -q -rs`, `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`, `python -m pytest tests/architecture -q`, `python -m scripts.verify_dod_v11 --evidence-dir ...`입니다. 실제 명령에는 바깥 연결을 차단하는 검증 플러그인과 JUnit 경로가 추가됩니다. DB 관문만 전용 루프백 시험 DB를 허용했습니다. [실제 명령/종료값](../evidence/2026-10-29_eks-linux-precision-expectations/commands.json).

## 준비 실패도 보존

첫 전체 기준선179/216=82.87%·37실패는 DATA_DIR만 공급하여 저장소 상대경로를 직접 읽는 그래프 시험1건이 추가 실패한 실행입니다. 동일113파일을 사본 안에도 공급한 뒤 원래 시험1/1=100%, 이후 전체216건을 다시 실행했습니다. 초기37건을 새 제품 실패나 정정18건에 섞지 않았습니다.

DB 미제공 관문 실패, 첫 정밀 경계19통과/4skip, 첫 기본 관문1568통과/39skip도 보존했습니다. Git 밖 `_tago_checked.py`를 원본에서 양쪽에 동일하게 복사해38개 기존 시험을 실행했고 추적 중 수집 코드는 덮지 않았습니다. DoD 최초 PG 실행14/26=53.85%는 토크나이저 자산 부재 때문에 외부 다운로드를 시도하다 차단된 결과입니다. 기존 로컬 cl100k_base의 SHA-256이 설치 로더 기대값과 일치함을 확인해 고유 캐시로 복사한 후, 외부 차단을 유지한 재실행은 양쪽26/26=100%입니다. 로컬 토크나이저 왕복2/2=100%, 실제 모델 호출0입니다. 잘못 선택한 Python 환경·PowerShell 인코딩/인자 전달·사본 파일 존재 검사 중단도 기록했습니다. [준비 실패](../evidence/2026-10-29_eks-linux-precision-expectations/preparation-attempts.json)·[토크나이저 검산](../evidence/2026-10-29_eks-linux-precision-expectations/tokenizer-provenance.json).

## 보존과 다음 작업

소스 수정은 `C:/_proj/eksprecision1029/candidate`, 브랜치 `fix/linux-precision-expectations-20261029`, 로컬 소스 커밋 `3e5a60af6a83d630250a210020b936895b2d7609`입니다. 기준선은 별도 `/repo`에 보존했습니다. 모든 XML·로그·실패 시도·실행 스크립트·113파일 사본·수정 전 fixture는 `C:/_proj/eksprecision1029`에 남겼습니다. 전용 시험 PG는 종료하고 원래 클러스터와 별도 보존 사본을 유지했습니다. [PG 보존](../evidence/2026-10-29_eks-linux-precision-expectations/pg-preservation.json).

남은18/36=50.00%는 시각 비교2·택시7·경로/이유7·계획 golden2입니다. 실패 node를 비교 JSON에 모두 남겼으며 단언 제거·golden 재생성·precision 끄기로 닫지 않았습니다. 독립 검토는 이번 기대값 정정 범위이며 공통 릴리스/도메인 담당 승인은 별도입니다. 다음 작업은 이18건의 계약·근거 대조이고, 실제 EKS fatal은 기존 허용된 reader 관측 근거 확보 전까지 원인 미확정/HOLD입니다. 이번 검증을 AMD64 이미지·EKS 운영 검증으로 부르지 않습니다.

원본 제품/Git 설정·색인 재구성·자격증명·권한·workflow·운영 데이터·운영 모델·push·merge·배포 변경0입니다. 기존 원본 자료와 이전 인계/보고를 그대로 보존했고, 이번 보고·인계·색인 상태만 추가했습니다. coord에는 범위·완료/잔여·HOLD를 기록하며 통합 예약이나 승인을 받았다고 표시하지 않습니다.

문서 부록 보존: 보안 시험 원시 XML2개는 탐지기 양성 표본을 시험 id에 담아 직접 검사에서 각각5건을 탐지했습니다. 원시 바이트는 실행 폴더와 양쪽 로컬 증거 폴더에 그대로 보존하고 커밋에는 집계·SHA256·보존 경로를 기록합니다. 검사기 예외·보안 시험 제외·원시 자료 삭제/수정은0입니다. [게시 범위와 해시](../evidence/2026-10-29_eks-linux-precision-expectations/evidence-publication-scope.json).

문서 검증: 게시 대상 새 보고·인계·증거33/33=100% 직접 검사·JSON/XML/링크 정상. 로컬 원시 보안 XML2개는 위 범위 기록대로 보존하고 게시 대상에서 분리했습니다. 전체 staged 공백 검사 exit2는 원시 XML의 후행 공백이며 바이트를 유지했습니다. Markdown/JSON 공백 검사는 exit0입니다. [검증 범위](../evidence/2026-10-29_eks-linux-precision-expectations/validation.json).
