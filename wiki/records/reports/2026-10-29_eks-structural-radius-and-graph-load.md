---
type: report
title: EKS 반경 후보 구조 검증과 그래프 적재 병목 후속
status: draft
domain: travel
---

# EKS 반경 후보 구조 검증과 그래프 적재 병목 후속

2026-10-29 KST. **세 실험 모두 코드 통합·푸시·배포를 하지 않았습니다. 위도 가지치기는 정확한 예외 동작 차이로 기각했고, bulk 결과 변환과 좌표 해독은 실제 업무/적재 개선을 입증하지 못했습니다.** 넓은 반경의 복사·인덱스 변환 비용은 줄였지만, 임의의 반경·표 크기 임계값으로 예외와 작은 표 회귀를 숨기지 않았습니다. 기존 [독립 검토](2026-10-29_eks-latitude-independent-review.md)를 이어받은 자체 검증이며 새 독립 검토자 승인을 뜻하지 않습니다.

루트/CS AGENTS·RULE, wiki 목차·Mobility 계약·코드 경로·개발 역할, 데이터 README/REPORT, 실제 scratch `_coord` notice를 읽었습니다. 원본 Git 읽기는 `tools/safe_git.py`만 사용했습니다. 새 사본 `C:/_proj/eksstruct1029/repo`는 이전 독립 사본의 main `57f3d2f004d0600f781599a6a92e8691b49bef82`에서 `--no-hardlinks`로 만들었습니다. 팀 원격 main 재조회도 같은 해시입니다. 개인 origin main은 과거 별도 이력 `b0485d05…`이며 이를 제품 기준으로 혼동하지 않았습니다. 깨진 WindowsApps credential helper로 실패한 최초 조회 로그도 보존했고, 기존 서명본 동일 gh의 정상 helper를 명령 환경에만 지정해 읽기를 완료했습니다. 원본/전역 Git 설정 변경0입니다.

## 구조 실험과 기각 근거

실험은 `_PointIndex.near`만 바꾸고 scalar `BusRoutes.stops_near`는 기준 그대로 두었습니다. 모든 점이 위도 band에 들어오면 advanced indexing과 두 번째 인덱스 매핑을 생략하고, 결과는 NumPy scalar를 한 건씩 꺼내는 대신 선택 배열의 `tolist()`와 Python 인덱스를 사용했습니다. 분기는 `band.size == len(items)`라는 정확한 구조 조건이며 반경·건수의 새 수치 임계값이 아닙니다. NaN/무한 dy도 원 연산에 남기는 보수적 처리를 실험했습니다.

유한 극단78/78, 실제 정류장240/240 = 100%에서 거리·포함 경계·객체 순서/동일성이 같았습니다. 새 pytest 경계는 Windows6/6·Linux ARM64 6/6·QEMU Linux AMD64 6/6 = 100%입니다. AMD64는 실제 후보 클래스 AST와 NumPy1.26.4를 실행한 에뮬레이션이며 배포 이미지나 AMD64 전체 pytest 검증이 아닙니다.

그러나 `np.errstate(invalid='raise')`, 점 `(38, inf)`, 질의 `(37, inf)`, 반경1000에서 기준은 경도 `inf-inf`로 `FloatingPointError`를 내고, band 후보는 해당 행을 미리 빼서 빈 결과를 냈습니다. 거리 연산을 그대로 둔 bulk 대안은 기준과 같은 예외를 냈습니다. [재현 코드](../evidence/2026-10-29_eks-structural-radius-and-graph-load/alternative.py)·[결과](../evidence/2026-10-29_eks-structural-radius-and-graph-load/bulk-semantics.json). 유효 좌표의 제한된 출력 동등성과 오류 정책까지의 동등성을 구분합니다. 이 반례 때문에 구조 band 후보는 통합하지 않습니다.

## 별도 벤치마크

작성자 수치를 복사하지 않고 별도 AST 기준선·seed901737·실제 공개 정류장·1/16/1000/41820점·반경0/1/20/50/100/200km/무한대·모든 점 동위치 자료를 사용했습니다. 35조건, AB/BA 각5회, 각 측정3호출, 원시 시간·tracemalloc peak를 보존했습니다. 양쪽 플랫폼 각각35/35 = 100% 출력이 같았습니다. Peak는 RSS/EKS 최대 메모리가 아닙니다. 최초 다른 전체 시험과 겹친 진단은 `contended-*`로 따로 보존하고 아래는 자체 시험 종료 뒤의 순차 측정입니다. 머신의 다른 세션까지 독점한 측정은 아닙니다.

실제41820점·200km 결과:

| 별도 실행 | 기준 → 실험 | 시간 변화 |
|---|---|---|
| windows-independent-bench | 28.822 → 24.250 ms | -15.86% |
| linux-independent-bench | 13.586 → 13.177 ms | -3.02% |
| windows-bulk-bench | 31.502 → 28.755 ms | -8.72% |
| linux-bulk-bench | 16.614 → 15.122 ms | -8.98% |

구조 band는 넓은 반경31.24% 회귀를 이 표본에서 피했지만 작은 표에서는 추가 검사 비용으로 다시 느려졌습니다. 이 결과로 모든 입력·EKS 성능을 보장하지 않습니다. Bulk 대안은 원래 거리 연산·경계·오류를 유지하며 넓은 결과의 Python 객체 생성 비용을 줄였지만, 좁은 실제 업무의 큰 개선은 입증하지 못했습니다.

이전 독립 검토자의 실제 Planner 프로토콜도 bulk 대안으로 재생했습니다. 고정 시각·3 OD·AB/BA·2회·각 fresh Planner·실제 두 보행 그래프 prewarm·네트워크 차단입니다. 전체 직렬화 출력 12/12 = 100.00% 일치, 중앙값 0.440260 → 0.456907초, 빠른 쌍 5/12 = 41.67%입니다. 이 재실행을 별도 검토자의 새 승인이나 API/SSE/DB/EKS 전체 성능으로 부르지 않습니다. [원시 쌍](../evidence/2026-10-29_eks-structural-radius-and-graph-load/bulk-confirm-benchmark-pairs.json).

## 전체층·보안·기존 건너뜀

| 실제 실행 | 결과 |
|---|---|
| 필수 관문 | 3/3 = 100%: DoD26/26, 계약368/368, 보안125/125 |
| 아키텍처 | 170/170 = 100% |
| Windows 기본 이동, CLI 실제 자료 연결 | 1557/1607 = 96.89%, skip50; 별도 deselect222 |
| Linux canonical non-live 전체층 | 216/216 = 100% 실행; 통과179/216 = 82.87%, 실패37, skip0; 별도 deselect1619 |
| 기준 메서드로 대표 실패 재실행 | 3/3 = 100% 같은 실패 재현; 전부 기존 원인이라는 결론은 아님 |
| 자료 경로 보완 추가 시험, 각 OS | Windows12/13·Linux12/13 = 92.31%, 각각 skip1 |
| 새 경계 pytest | 각 Windows/Linux6/6 = 100% |
| ruff F/E9, diff --check | exit0 |
| 변경·실험 소스 추가 보안 탐지 | 4/4 = 100% 검사, 발견0 |

canonical 명령은 `DATA_DIR=<원본 공개 processed>`·`ACOP_MOBILITY_DATA_DIR=''`, `python -m pytest tests/unit/travel/mobility -m "mobility_full and not live" -q -rs`입니다. Linux는 WSL ARM64·Python3.12.16·요구 버전 NumPy1.26.4이며 실제 입력 전체층을 첫 실패 뒤에도 끝까지 실행했습니다. Windows3.12.15/x64 중복 전체층은 Linux 완료 후 장시간 동시성 구간에서 중단했습니다. 해당 로그·소유 PID 기록을 보존했고 완료로 세지 않았습니다. `test_threads_8x80`이라는 이름과 달리 실제 상수는 8스레드·총80건입니다. 처음 진행 설명의640건을 이후 정정했습니다.

최초 Linux 설정 누락으로 경계6오류·전체층 collection 오류가 났던 로그/XML도 보존했습니다. 준비 완료 후 결과만 위 표에 썼으며 실패를 삭제하지 않았습니다. 전체층37건은 시간표/분 단위 기대, 계획 golden/재방문 동시성, 택시 자료 기대, mixed/fallback, 사본 자료 부재가 섞여 있습니다. 원문과 식별자는 [집계](../evidence/2026-10-29_eks-structural-radius-and-graph-load/suite-summary.json)에 전부 있습니다. 기준 대조는 `ntower_namdae`, `real-R-BASE-02`, `only_blocked_stations` 3건만 수행했습니다. 나머지 실패를 자동으로 기준선 결함으로 분류하지 않습니다.

원본 공개 processed61파일을 새 사본으로만 복사하고 각 해시와 원본 불변을 확인한 뒤, 기본 skip 중 스크립트 외12건과 전체층의 자료 부재1건을 같은 assertion으로 재실행했습니다. 12통과·건물 출입구 자료 부재1skip이며, 이 중 전체층의 passenger-car 자료 부재 실패1건은 보완 후 통과입니다. 최초 전체층179/216 결과를 소급해 고치지 않습니다. 기본 skip의 나머지38건은 현재 수집 스크립트 자체가 없어서 재실행하지 못했습니다. 자료 복구·삭제·테스트 단언 축소·제외 추가는 하지 않았습니다. [공개 입력 해시](../evidence/2026-10-29_eks-structural-radius-and-graph-load/supplement-public-inputs.json).

필수 관문은 새 전용 PostgreSQL16.15·loopback55763·`eksstruct` DB에 CI와 같은 migrate/register_prompts/seed_travel 후 실행했습니다. 준비물은 합성 여행 자료뿐입니다. 자체 PG는 정상 종료했고 기존 다른 DB/서비스는 사용하지 않았습니다.

## 다른 큰 병목: 그래프 첫 적재

기존 실제 프로파일의 `_load`55.608/67.117초 = 82.85%, 그 안 `decode_polyline`13.695/67.117초 = 20.40% 구간을 조사했습니다. 서로 중첩된 누적 시간이라 합산하지 않습니다. 현재 코드에 백그라운드 router warm이 이미 있으므로 미구현 기능처럼 다시 제안하지 않습니다. EKS에서 요청이 준비보다 먼저 들어왔는지는 확인하지 못했습니다.

해독기의 좌표 두 축 루프를 펼치는 별도 실험은 기존 ord·비트 연산·반올림 순서·오류를 유지합니다. 공개 두 그래프861922/861922 = 100% 전 좌표열이 기준과 같고, 잘못된 문자열·빈 입력·0/음수/무한 정밀도 등60/60 = 100%도 결과 또는 예외 클래스/메시지가 같았습니다. 보정값·임계값·비안전 직렬화·새 데이터는 없습니다. 표본5만 간선의 AB/BA 원시 시간은 별도 보존했습니다.

더 나아가 실제 `road_graph_v2`를 매번 새 GraphRouter로 `warm(foot)`하는4쌍을 측정했습니다. OS 파일 캐시는 데워져 있고, topology 해시와 이후 경로 비교는 시계 밖입니다. 적재 배열·격자와 실제2 OD의 전체 경로 출력은 4/4 = 100.00% 일치했습니다. 중앙값 6.799138 → 8.351763초(+22.84%)입니다. [실제 적재 원시 쌍](../evidence/2026-10-29_eks-structural-radius-and-graph-load/graph-load-pairs.json). 단독 해독 미세 측정의 이득이 실제 적재 이득으로 이어지지 않았고 표본에서는 회귀했습니다. 제한된4쌍으로 본질적 회귀율을 단정하지도 않으며, 이 대안 역시 기각·미통합하고 별도 후보 함수와 근거만 남겼습니다. EKS 전체 접수 개선·배포 검증이 아닙니다.

## 보존과 다음 단계

고객/provider/유료 모델 호출·운영 변경·push·배포·자료 삭제는 각각0입니다. 원본 제품 코드·Git 색인/설정·기존 보고서·다른 작업자 사본은 변경하지 않았습니다. 패키지 설치는 자체 Linux 환경/다운로드 경로에만 했고, 공개 processed 사본은 자체 clone에만 추가했습니다. 실제 EKS CPU/throttling·RDS·pod 신규 기동·API/SSE 부하는 측정하지 않았습니다. 전체 운영 검증 분모는 모릅니다.

출시 전에는 남은 실제 전체층 실패를 각각 기준선과 분리하고, 누락 자료의 정식 공급 경로를 확보해야 합니다. 그래프 적재 대안을 추진한다면 새 후보를 최신 main 위에 만들고 독립 검토·전체 관련 시험·배포 AMD64 이미지·대표 cold/warm/RSS·동일 업무 EKS 측정을 완료해야 합니다. 현재 결과는 그 승인이나 자동 배포 허가가 아닙니다. 모든 사본·PG 자료·중단 로그는 `C:/_proj/eksstruct1029`에 보존합니다. [최종 요약](../evidence/2026-10-29_eks-structural-radius-and-graph-load/final-summary.json)·[manifest](../evidence/2026-10-29_eks-structural-radius-and-graph-load/manifest.json)·[인계](../../handoff/2026-10-29_eks-structural-radius-and-graph-load.md).
