---
type: report
title: 버스 scalar 후보 독립 검토와 최신 브랜치 통합 검증
status: draft
domain: travel
---

# 버스 scalar 후보 독립 후속 검증

2026-10-29 KST, 담당 Codex independent continuation. 기존 후보 작성 세션과 별개로 검토했습니다. 사용자 승인 범위는 독립 검증, 안전한 통합·양쪽 role-manager push이며 develop/main 또는 검증하지 않은 운영 변경은 포함하지 않습니다.

원본·격리 브랜치의 루트/CS 지침, RULE, wiki index 및 역할·이동 계약을 확인했습니다. R/V/S3/ST4F711/deploy NOTICE는 완료·소유 해제 상태입니다. 독자 NOTICE를 공유 `_coord`에 등록했습니다. 다른 작업자의 트리·공유 DB·원본 제품 코드 변경은 없습니다.

## 기준과 초기 발견

- 원본 HEAD `efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3`, 최신 양쪽 role-manager `3dd9bd70c9d1c598f70faad69cf755141cc4a041`. 원본은 최신 원격과 다르므로 동기화하지 않았습니다.
- PATH의 git 실행 WinError5는 기존 실행 가능한 MinGit 디렉터리를 해당 명령 PATH에 지정하여 해결했습니다. 원본 조회는 `tools/safe_git.py`로만 실행했습니다.
- 첫 clone은 Windows 긴 경로 때문에 checkout 실패했습니다. 실패 사본은 보존하고 짧은 `C:/_proj/busreview1029`에 새 독립 clone을 만들었습니다. 원본 설정·색인을 변경하지 않았습니다.
- 최신 bus_profile에는 이전 후보에 없는 `min_cell`이 있습니다. 이전 파일 전체를 옮기지 않고 최신 파일에서 `np.isnan(v)` → `math.isnan(v)` 한 표현식만 변경했습니다. vector 연산 `min_cell`의 `np.isnan`은 유지합니다.
- 제품 호출은 `walk`와 `candidates`의 스칼라 조회입니다. 로더는 `float32` ndarray를 만듭니다. 임의 complex/object/array 인자로 범위를 넓힌 일반 동등성은 주장하지 않습니다.

## 실행 중 기록

유효한 gzip 로더 입력의 ordered quantiles·n 부족·결측, 임의 IEEE float32 bit pattern(±0/subnormal/±inf/NaN 포함), 자정·48시·다중 요일·fallback 누적·막차 보조함수에서 반환값/예외/경고 동등 **32,939/32,939 = 100%**, 차이0입니다. 전후 로드 배열 바이트도 동일합니다. 원천 관측 자료·고객 자료 대신 seed 고정 합성 자료만 사용했습니다.

첫 pytest 실행은 필수 설정 누락으로 34 setup error였습니다. 시험용 dummy 설정을 지정한 후 전용 PostgreSQL16.15 `127.0.0.1:55497/busreview`를 새로 만들어 마이그레이션·프롬프트 등록·여행 seed를 실행했습니다. 초기 실패와 최종 결과는 별도로 보존합니다.

Mobility **1,481/1,607 = 92.16%**, skip126·deselected222·실패0; contract **367/367 = 100%**, skip0. 나머지 관문·독립 성능 측정은 실행 중이며 통합·push 완료로 세지 않습니다.

증거: `scratch/bus-independent-20261029/`의 `review.py`, `semantics.json`, `valid-synthetic.jsonl.gz`, `gates.py`, 실행별 log/XML. 원본 보고서·기존 벤치 결과는 덮지 않았습니다.

## 기존 성능 근거의 한계

기존 11회 AB/BA 결과는 같은 프로세스·고정 workload의 로컬 효과입니다. 각 cell 호출을 독립 표본으로 세면 안 됩니다. cell 인자의 `i%3`이 q와 min_days를 묶으며, 무작위 quantile 배열은 로더의 p10≤p50≤p90 조건을 만족하지 않습니다. walk는 모든 구간이 동일한 60초이며 fallback·자정 경로가 없습니다. 따라서 운영 대표성 또는 EKS 전체 접수 개선률로 일반화할 수 없습니다. 독립 측정은 유효한 로더 자료와 혼합 승차 경로에서 균형 무작위 전후 순서를 사용하고 paired 회차 원시값과 bootstrap 구간을 남길 예정입니다. OS 부하·동일 프로세스 자기상관·합성 workload 한계는 남습니다.


## 최종 독립 판정 (2026-10-29 KST)

**최신 role-manager에 한 표현식만 통합하는 로컬 검증 관문은 통과했습니다.** EKS 전체 접수 개선·Linux 이미지 성능·운영 수락은 미검증입니다. x600 자동 배포가 role-manager push를 소비할 수 있음을 확인했고, 이번 사용자 승인에 따라 검증한 소스만 양쪽 role-manager로 fast-forward 반영할 예정입니다. develop/main·수동 배포·AWS 호출은 하지 않습니다. 최종 원격 영수증은 후속 절에서 별도 기록합니다.

| 독립 검증 | 결과 |
|---|---:|
| 로더·float32 비트·walk·막차 보조함수 동등성 | 32,939/32,939 = 100% |
| 실제 후보 생성 ride_estimator·캐시 재조회 | 각각 1,152/1,152 = 100% |
| 실제 공공 버스 프로파일 셀 표본 | 50,000/50,000 = 100% |
| 실제 정류장 사슬 walk | 480/480 = 100% |
| 변경 전 기존 bus profile pytest | 34/34 = 100% |
| 변경 후 동일 pytest | 34/34 = 100% |
| 전체 Mobility 회귀 | 1,481/1,607 = 92.16%, skip126·실패0·제외222 |
| 필수 contract | 367/367 = 100%, skip0 |
| 필수 security | 125/125 = 100%, skip0 |
| 필수 DoD 항목 | 26/26 = 100%, 미측정·시험없음0 |
| 추가 여행 통합 | 23/39 = 58.97%, skip16·실패0 |
| 필수 통합 관문 | 3/3 = 100% |
| 변경 파일 ruff F/E9·diff 공백 검사 | 2/2 = 100% |

시험 수를 중복 합산하여 제품 전체 통과율로 만들지 않았습니다. Mobility의126 skip은 실시간표/그래프/수집 스크립트가 없는 환경입니다. 추가 통합16 skip은 `SEMANTIC_SYNTHETIC_DATABASE_URL`, `PARTIAL_NOTICE_SYNTHETIC_DATABASE_URL`, `DINING_RADIUS_SYNTHETIC_DATABASE_URL` 및 공개 식당 준비물이 필요한 별도 고정15544 DB 계약입니다. 그 가드를 우회하거나 다른 작업자의 DB를 쓰지 않았습니다. 이번 버스 프로파일의 변경 전후34·독립 실제 프로파일 및 후보 생성 비교에는 skip이 없습니다.

실제 원천 프로파일은 40,776×2×4×24 float32입니다. 두 로더의 배열 바이트·index·ends·meta가 동일하며 원천 파일 SHA256은 전후 `b2000c11503010c9b1a66b4c02eb0237374a09c9563f75b83ab67b231b28a074`로 같습니다. 정류장명·원천 레코드·고객 자료는 공유 증거에 내보내지 않았습니다. 실제 데이터 비교는 기존 관측 사실의 최신성·예측 정확도 평가가 아닙니다. NaN은 None, 그 밖의 scalar는 같은 float 비트이며 기존 양자화·누적 순서·fallback·min_cell 캐시는 유지됩니다.

최신 기준 파일 SHA256 `781db9b88a7c0965f42ce4abf02e460e4dcbb86cc0b5228d880c2b539952a799`, 후보 `ab9196583f4444c61fe093dc87adafc4dd77ae4fc58703e1b71bbf0ebe3392db`. 기존 보고서의 후보 파일 전체와 해시가 다른 것은 최신 `min_cell` 구현을 보존했기 때문입니다. 최종 code diff는 기존 `math` import를 쓰는 NaN 검사 한 표현식뿐입니다. constructor에 arbitrary object/complex/고차원 인덱스를 넣는 비계약 호출의 일반 동등성까지 주장하지 않습니다.

## 독립 성능 측정

Python3.12.15/NumPy1.26.4 Windows. seed102904, 유효한 gzip 로더 자료(ordered quantiles), 3회 warmup, workload마다 균형 무작위 AB/BA 30쌍, pair마다 출력 일치 확인입니다. cell은 회차49,152 호출이며 인자 조합을 독립 추출했습니다. mixed walk는 회차640호출, 길이가 다른 사슬·p10/p50/p90·시각 경계·한쪽 결측·fallback·48시 중단을 섞었습니다. 전용 DB·검증 러너 종료 뒤 측정했습니다. 다른 OS 부하는 통제하지 않았습니다.

| workload | baseline 중앙값 | candidate 중앙값 | 회차별 감소율 평균 | paired bootstrap 평균 95% 구간 | 빠른 회차 |
|---|---:|---:|---:|---:|---:|
| cell | 0.126404초 | 0.106139초 | 14.96% | 13.61~16.27% | 30/30 = 100% |
| mixed walk | 0.067100초 | 0.060575초 | 8.65% | 6.75~10.52% | 29/30 = 96.67% |

bootstrap20,000번, 회차를 표본 단위로 사용했습니다. 호출49,152개나640개를 독립 통계 표본으로 세지 않았습니다. 이 구간은 이 프로세스·합성 분포에서의 경험적 불확실성입니다. 같은 프로세스의 자기상관·OS 스케줄링·다른 요청 분포·Linux/EKS 차이는 포함하지 못합니다. 따라서 운영 성능의 신뢰구간이나 인과적 EKS 지연 감소율로 읽지 않습니다. 기존 단순 walk16.29%에 비해 현실적인 혼합 경로에서는 평균8.65%였으며 전체 접수 개선률의 분모는 모름입니다.

## 재현·보존·위험

명령(격리 CS cwd, CI의 mock/dummy 설정과 새 전용 DB 지정): `python -m pytest tests/unit/travel/mobility -q`, `python -m pytest tests/contract -q`, `python -m pytest tests/security -q`, `python -m scripts.verify_dod_v11`, `python -m pytest tests/integration/travel -q`. 독립 스크립트는 아래 evidence에 연결했습니다. 원시 실패·log/XML·fixture·PG data는 원본 `scratch/bus-independent-20261029/`에 보존합니다. 초기 긴 경로 clone도 삭제하지 않았습니다.

전용 PG55497은 자기 pgdata를 지정한 pg_ctl로 종료했습니다. 뒤늦게 새 ST4F597 독립 작업자의 같은 포트 NOTICE를 확인하여 즉시 자기 NOTICE에 사용 종료·재시작 금지를 기록했습니다. 다른 작업자의 프로세스·DB·파일에는 쓰지 않았습니다. 원본 소스·색인·refs·sparse 설정은 변경하지 않았습니다. `.env`·키·고객 입력·실제 자료 레코드를 사본이나 공유 evidence에 복사하지 않았습니다. 원본 자료 삭제·폴더 정리·운영 API 쓰기·유료 모델 호출0입니다.

남은 위험: EKS 런타임·전체 접수 성능은 별도 동일 환경 검증이 필요합니다. readiness·DB 연결142회·공개 뒤 작업은 이번 변경으로 해결됐다고 볼 수 없습니다. 이번 변경은 새 의존성·스키마·캐시·권한·알림 계약을 도입하지 않습니다. 기존 보고서는 당시 상태로 보존합니다.

[검증 집계](../evidence/2026-10-29_bus-scalar-independent/summary.json) · [의미 동등성](../evidence/2026-10-29_bus-scalar-independent/semantics.json) · [실제 자료 집계](../evidence/2026-10-29_bus-scalar-independent/real-profile.json) · [원시 성능 회차](../evidence/2026-10-29_bus-scalar-independent/performance.json).

공유 보안 XML의 parameter node id에 검사기 자체의 가짜 공개IP·웹훅·개인키 머리글 표본이 포함되어 추가 보안 스캔이 탐지했습니다. 실제 키 유출은 없으며 공유 XML의 parameter 이름만 fixture 번호로 바꿨습니다(시험 수·결과 유지). 원시 XML은 로컬 scratch에 보존했습니다. manifest는 Git의 줄바꿈 정규화 이후 staged blob SHA256이며, 위 소스 SHA256은 측정 당시 working-copy 바이트입니다.
