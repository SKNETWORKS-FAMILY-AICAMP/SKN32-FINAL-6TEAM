---
type: report
title: EKS 위도 가지치기 독립 검토
status: draft
domain: travel
---

# EKS 위도 가지치기 독립 검토

2026-10-29 KST, Codex. **운영 배포 HOLD입니다.** 원 후보를 작성한 세션과 별도로 최신 원격 main `57f3d2f004d0600f781599a6a92e8691b49bef82`을 확인하고 새 격리 사본 `C:/_proj/ekslat-review1029/localrepo`에서 패치를 적용했습니다. 원본 코드·Git 색인·서비스·고객 데이터는 변경하지 않았습니다. 원 후보의 손상된 한글 설명을 추측해서 복원하지 않고 패치·JSON·실행 결과를 확인했습니다.

루트/CS AGENTS·RULE, wiki 목차·Mobility 계약·담당 경계, 원 보고서와 인계, 실제 조정 위치 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_coord/Codex-eks-deep-20261029-NOTICE.md`를 읽었습니다. 조정 문서는 후보 작성자의 자기 검토만 완료했고 운영 HOLD이며 코드 통합 예약이 없음을 확인합니다. 원본 `_coord` 경로에는 해당 폴더가 없습니다.

검토 중간 근거: `geo.meters`와 NumPy 기존 식 모두 `hypot(dx,dy)`를 사용합니다. 따라서 같은 부동소수점 연산으로 얻은 `abs(dy)`가 반경보다 크면 제외할 수 있습니다. 새 업무 임계값은 추가하지 않았고 `111_320`은 기존 거리식의 단위 환산 상수입니다. 경도·극지방·날짜변경선에 대한 기존 평면 근사의 지리적 정확도를 개선하거나 인증하는 변경은 아닙니다. 포함 경계는 `<=`를 유지하고 입력 순서·동일 거리 정렬·행 객체 동일성을 비교했습니다.

독립 유한 극단 좌표·반경 비교 78/78 = 100%, 실제 정류장 41,820행에 대한 새 seed 812904의 scalar/NumPy 비교 240/240 = 100% 일치했습니다. 의심했던 NaN 위도·무한 경도 조합의 차이는 재현되지 않았습니다. invalid 입력 전반의 예외·NumPy 경고 정책 동일성까지 보장한 결과는 아닙니다.

원 프로토콜의 새 실행은 실제 서울 자료·3 OD·AB/BA·2회 반복·12쌍·fresh Planner·고정 시각/4인·그래프 prewarm·네트워크 연결 차단입니다. 경로 전체 직렬화 값 12/12 = 100% 일치, 중앙값 0.499344→0.416311초(16.63% 감소), 개선 쌍 11/12 = 91.67%입니다. 원 보고서의 17.60%와 별개 측정입니다. 로컬 Windows/Python 3.12.15 결과이며 EKS CPU·throttling·RDS·provider·접수 전체 시간의 인과 개선은 미측정입니다. OD 범위가 좁고 cold load를 제외하므로 서비스 전체 성능으로 일반화하지 않습니다.

기본 이동 시험 1,486/1,612 = 92.18%, skip126 및 별도 deselect222입니다. 아키텍처 170/170 = 100%입니다. 기본 전체층 제외는 `mobility/conftest.py`의 의도된 기본 동작이며 skip과 구분합니다. 실제 자료를 연결한 추가 실행과 필수 관문은 아래 후속 결과로 보완합니다. 최초 추가 실행은 CLI `DATA_DIR` 없이 설정 변수만 제공해 자료를 찾지 못한 환경 실패를 보존했습니다. 최초 필수 관문도 격리 DB 생성·스키마 준비 이전 결과로 성공 처리하지 않습니다.

전체층 첫 실패 `test_earliest_v1.py::test_full_earliest_on_late_gives_earliest_arrival[ntower_namdae]`는 최신 HEAD 원래 두 메서드를 AST로 끼운 독립 baseline 실행에서도 실패했습니다(0/1 = 0%). 후보가 만든 회귀로 확정하지 않습니다. 전체층의 나머지 실패를 자동으로 같은 원인으로 묶지 않습니다.

증거 원본과 실행 스크립트는 `C:/_proj/ekslat-review1029/`에 보존합니다. 비밀값은 보고하지 않으며, 고객/provider 조회·유료 호출·push·배포는 하지 않았습니다. 원격 Git 읽기는 수행했습니다. 로컬 격리 PostgreSQL만 새로 만들었고 운영 DB를 사용하지 않았습니다.

## 최종 결과 — 05:30 KST

**기하·출력 동등성과 제한된 로컬 실익은 확인했습니다. 필수 관문은 3/3 = 100% 통과했으나 출시·배포 승인은 HOLD입니다.** 전체층 실패·미실행 및 Linux/EKS 검증이 남습니다. 새 제품 코드 결함을 확정하지 않았으며, 이 결과를 모든 입력에서 빨라진다는 보장으로 해석하지 않습니다.

| 독립 실행 | 결과 |
|---|---|
| DoD, DB 준비 후 | 26/26 = 100%, exit0 |
| 계약, DB 준비 후 | 368/368 = 100%, exit0 |
| 보안, DB 준비 후 | 125/125 = 100%, exit0 |
| 아키텍처 | 170/170 = 100%, skip0 |
| 새 독립 회귀 | 2/2 = 100%; HEAD 대조 78+240건 및 객체 순서·포함 경계 |
| 기본 이동 | 1,486/1,612 = 92.18%, skip126; 별도 deselect222 |
| canonical 전체층 fail-fast | 실행 8/216 = 3.70%; 통과7·실패1·미실행208, live6 제외 |
| 해당 실패의 HEAD 대조 | 같은 1/1 = 100% 실패 재현 |
| 제품 환경 성능 측정·배포 | 각각 0, EKS 검증 범위의 분모 모름 |

명령은 CS cwd에서 `python -m scripts.verify_dod_v11`, `python -m pytest tests/contract -q -rs`, `python -m pytest tests/security -q -rs`, `python -m pytest tests/architecture -q -rs`, `python -m pytest tests/unit/travel/mobility -q -rs`입니다. 전체층은 `DATA_DIR=C:/_proj/final_workspace/datasets/mobility/processed`, `ACOP_MOBILITY_DATA_DIR` 빈 값으로 `python -m pytest tests/unit/travel/mobility -m "mobility_full and not live" -x -vv`를 실행했습니다. 인터프리터·환경 구성·JUnit 인자는 증거의 runner 파일이 보존합니다. HEAD 대조는 `baseline_plugin.py`로 최신 HEAD에서 추출한 원래 두 메서드만 끼웠습니다. 작성자 저장 baseline과 HEAD 원문은 줄바꿈 정규화 후 일치합니다.

최초 DB 없는 관문의 계약 353/368 = 95.92%(실패12·오류3), DoD 하위 시험 실패·오류, 보안 진단 87/88 = 98.86%(오류1)는 삭제하지 않았습니다. 새 전용 PostgreSQL 16.15·loopback55753에 `eksdeep` DB를 만든 뒤 main CI 순서인 `python -m app.infrastructure.db.migrate`, `python -m scripts.register_prompts`, `python -m scripts.seed_travel`을 실행하고 세 관문을 다시 통과시켰습니다. 검증 뒤 이 세션이 만든 PostgreSQL은 정상 종료했으며 자료는 보존했습니다.

건너뜀126은 모듈별로 plan39·수집 스크립트38·regression gate21·verify55 6·taxi link5·taxi fallback4·정밀시간표4·나머지9입니다. 이유는 주로 git 밖 자료·수집 스크립트와 설정된 경로 부재입니다. 222개 제외 중 216개가 non-live 전체층이며 live6은 실행하지 않았습니다. 원 보고서의 기본 시험만으로 실제 자료 전체층 통과를 주장할 수 없습니다. `ACOP_MOBILITY_DATA_DIR`만 켠 최초 추가 실행은 1,490/1,828 = 81.51%, skip337·실패1(자료 경로)입니다. CLI `DATA_DIR`와 전역 서버 계산기를 함께 켠 비정규 진단 실행은 다수 실패 후 중단했으며 완료 집계·통과율을 만들지 않았습니다. 전역 켜짐을 제거한 canonical 전체층은 fail-fast 및 HEAD 실패 대조까지만 완료했습니다. 나머지208건을 통과로 세지 않습니다. 다른 진단 실패의 원인은 미확정입니다.

새 밀도 합성 측정은 n=1/16/1000/41820, 반경0/1000/200000m, AB/BA×3, 회당10호출입니다. 41,820점·1000m는 2.442→0.191ms였지만, 200000m는 56.539→74.203ms(31.24% 증가)였습니다. 단일점도 추가 인덱싱 비용이 있습니다. 이는 실제 서울 OD 측정과 별도이며, 성능의 유효 범위가 희소한 위도 band임을 보여줍니다. 이 진단을 근거로 임의 임계값·분기·표본 맞춤 보정은 추가하지 않았습니다.

자료 identity25/25 = 100%를 파일에서 다시 해시해 작성자 근거와 대조했습니다. 정류장·시간표와 두 실제 그래프 입력을 포함합니다. 실제 A/B의 모든 쌍에서 시간·요금·후보 순서 등을 포함한 전체 출력 해시가 일치하지만, API·SSE·DB·provider 경로를 재생한 시험은 아닙니다. 로컬·합성·운영의 수치를 합산하지 않습니다.

남은 출시 조건은 canonical 전체층 실패의 별도 처리와 나머지 non-live208건 실행, Linux/amd64 및 실제 배포 NumPy 조합의 동등성·밀도/메모리·cold/warm 측정, 동일 업무 전후 EKS stage/prefill·CPU/throttling·DB 대기/timeout 측정입니다. 기존 원격 main이 바뀌면 다시 대조해야 합니다. 현재 검토는 어떤 배포·push도 허용하거나 수행하지 않았습니다.

[정확한 실행 요약](../evidence/2026-10-29_eks-latitude-independent-review/review-summary.json) · [시험 집계와 skip 사유](../evidence/2026-10-29_eks-latitude-independent-review/test-summary.json) · [실제 A/B](../evidence/2026-10-29_eks-latitude-independent-review/confirm-benchmark-pairs.json) · [파일 manifest](../evidence/2026-10-29_eks-latitude-independent-review/manifest.json) · [인계](../../handoff/2026-10-29_eks-latitude-independent-review.md).
