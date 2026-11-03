---
type: report
title: EKS 경로 후보 1ab3f0d88 독립검토
status: draft
domain: travel
---

# EKS 경로 수정 독립검토

검토 기록 시각: 2026-10-29T21:13:04.713442+09:00

후보 `1ab3f0d882bc80d0ea437116d6301d0760084f68`의 독립 실행을 마쳤습니다. **전체 이동 223/223 = 100.00%**, 빠른 층 **1629/1630 = 99.94%**(기존 자료 부족 skip 1건), 저장·출발·고정·시각 경계 **89/89 = 100%**입니다. 세 층은 일부 겹치므로 합산하지 않습니다. 기준 `47549aa4e867db108d28aeaaff4465253998d9c6`에서 지정 세 실패를 **3/3 = 100% 재현**했습니다. PR110 draft/HOLD를 유지합니다. 통합·배포 승인이 아닙니다.

## 범위와 원본 보존

중단 로그 `deleg_d6c4a15e/task-0.log`와 [기존 후보 인계](../../handoff/2026-10-29_eks-remaining3-fix.md)를 이어받았습니다. 검토 담당은 Codex이며 후보 구현과 별개입니다. 루트/cs AGENTS·CLAUDE·RULE, wiki·개발 역할·Mobility 현재 계약 및 인용된 저장 문맥 계약, 데이터 README/REPORT와 실제 Hermes `_coord` EKS/Hspeed NOTICE15개를 확인했습니다([해시](../evidence/2026-10-29_eks-route-fix-independent-review/coord-read.json)). 담당자 수락이나 통합 예약을 대신 주장하지 않습니다.

기존 `/root/eksremain3r_1029/wt-tip`과 `wt-bisect`, Python3.12 가상환경, 기존 공공데이터를 재사용했습니다. 새 clone·전체 데이터 복사·원본 제품 코드 수정·삭제·Git 색인/설정 변경·DB·운영·권한·외부 메시지·push·배포는 0건입니다. 후보 변경 5/5파일 = 100%가 커밋 blob과 같습니다. 실제 입력은 113개 자료+빈 `.gitkeep` 1개, 289,950,471바이트이며 해시를 남겼습니다. 자료 원문을 이번 evidence로 복제하지 않았습니다.

## 검토 결과

1. **후보 번호는 같은 route/context 안의 식별값입니다.** `settle_head`는 판정 순서를 바꾸므로 `_mixed_one`의 자리 번호와 최종 표시 ID가 바뀔 수 있습니다. 공개 ID는 `options.make_id`가 결과 목록에서 부여하며 전역 영구 경로 ID가 아닙니다. 현재 wiki의 「같은 문맥의 option id로 선택」 계약과 일치합니다. 실제 사고 재생의 route/context를 JSON 왕복한 뒤 option_id·eta·원 legs·check.legs 일치를 기준·후보 각각 확인했습니다. 기준 `bus_1` → 후보 `subway_bus_1`입니다. 같은 표시 번호가 새 묶음에서 재사용되는 합성 반례에서도 observer는 옛 저장 legs만 검증하고 context를 바꾸지 않았습니다(**4/4 = 100%**). 기존 고정 항목/문맥 폐기/시각 경계 시험도 위 89개에 포함했습니다. 실제 DB 저장·고객 고정 여행 운영 확인은 수행하지 않았습니다.

2. **첫차 하한은 시간표 관측이 아닌 모델 제약입니다.** 실제 자료 717노선·41,103구간 중 거리 있는 구간은 **41,103/41,103 = 100%**입니다. 301 seq53의 best/worst 승차는 기준 04:04/04:07 → 후보 **05:22/05:39**, 710 seq20은 04:05/04:09 → **04:21/04:27**입니다. 모든 표본 결과 등급은 `추정`이며 evidence는 공표 기점시각과 프로파일/거리÷속도를 구별합니다. 기존 시험에서 관측 우선·미상 경고·첫차/막차 추정 모순 no_data·p90 사슬 실패·운행일 경계를 확인했습니다. 거리 완전성은 정류장별 첫차 관측 정확도를 증명하지 않습니다. p50·p90은 물리적으로 보장된 최초 통과 하한이 아니므로 “실제로 이 시각 이전 승차 불가를 검증”했다고 표시하면 안 됩니다. 이 모델을 바탕으로 골든 통과한 것과 실제 새벽 첫차 검증은 구분해야 합니다. 새 현장/공개 정류장별 관측은 확보하지 않았습니다.

3. **P2: 정책 변경의 판 식별이 충돌합니다.** 새 첫차 정책과 경고가 rules 파일에 들어갔지만 `rules_version`은 양쪽 모두 `v0.9.2`이고 실제 저장 context의 `input_basis` 전체도 동일합니다. 새 정책 evidence도 `mobility_rules@v0.9.2`를 가리킵니다([실제 표본](../evidence/2026-10-29_eks-route-fix-independent-review/public-data-candidate.json), [두 snapshot](../evidence/2026-10-29_eks-route-fix-independent-review/snapshot-candidate.json)). `departure_context.input_basis`/observer의 `basis_changed` 검사는 이 정책 차이를 구분하지 못합니다. 옛 구간 오선택 결함을 뜻하지는 않으나 정책 판 추적과 무효화에 빈틈이 있습니다. 통합 담당은 현재 wiki 계약에 모델 추정·미상 처리·실시간 우선·적용 제외를 명시하고, 규칙 판/이력 또는 내용 식별을 어떻게 갱신할지 정리한 뒤 전후 문맥 대조 시험을 붙여야 합니다. 이번 검토는 제품 계약·정책판을 임의로 바꾸지 않았습니다.

4. **모양 균형·판정 상한 유지, 최적성 보장은 아닙니다.** `_mixed`와 `_mixed_sources`가 같은 지연 재정렬을 사용하고 같은 모양 자리·운행 시간 안/밖 묶음·정규운임 대안 우선·동률 생성순서를 유지합니다. 판정 상한은 늘지 않지만 materialize는 늘 수 있습니다. 서로 다른 등급의 추정치를 비교하는 유한 후보 탐색이므로 모든 가능한 실제 최적 경로를 찾는 보장은 아닙니다. 후보·정답·공공데이터를 수정해서 통과시키지 않았습니다.

## 성능

동일10경로, 각 warmup1회+3회 중앙값 합계는 **24.099 → 26.576초**입니다. 전후 블록 실행에 전체층/빠른층 시험이 함께 돌았으므로 확정 회귀율이나 EKS 성능으로 일반화하지 않습니다. 구체화는 경로당 0~2회 늘었습니다. 추가 확인한 ABBA(각 블록 warmup1+5회)의 혼합 표본 중앙값은 다음과 같습니다.

| 표본 | 기준(초) | 후보(초) |
|---|---:|---:|
| only_blocked | 0.222 | 0.323 |
| mixed_blocked_earliest | 0.806 | 1.036 |

이 표본의 추가 탐색 비용은 숨기지 않습니다. 기존 보고의 25.5→23.5초를 독립 재현한 것으로 보지 않습니다. 성능 수락 예산은 미확보이며 운영 지연·reader fatal과의 인과도 입증하지 않았습니다. 기능 회귀 전체층에는 `test_threads_8x80` 동시성 스트레스가 포함됩니다. 이번 전체층 pytest 시간은 1,032.72초이고 동시성80건 시험은 704.667초입니다. 이전 후보 기록 687.42초/457.666초와 환경 부하를 통제한 쌍대 측정은 아니므로 속도 개선을 주장하지 않습니다. 실제 프로파일·시각·각 실행은 [summary](../evidence/2026-10-29_eks-route-fix-independent-review/summary.json)와 raw bench/perf JSON에 있습니다.

## 재현과 한계

- 명령: `/root/eksstruct1029-py312/bin/python /mnt/c/_proj/eksfix3_1029/run_full.py independent-review-full cand`; 같은 runner의 `MARK='not live and not mobility_full'` 빠른층, `MARK='not live'` 저장/출발 경계, `tip` 지정3개 기준 실행. 정확 인자·실행 전후 SHA·시간은 각 `*-exit.json`입니다.
- pytest는 offline_guard_v2·mock LLM·DB 연결 불가 환경입니다. 제품 모델·외부 API·운영 고객 호출은 없습니다. 실데이터는 기존 공공자료의 로컬 재생입니다. DB·화면·운영 통합 관문 완료를 주장하지 않습니다.
- 검토 probe 첫 시도는 검토용 `inspect.py`가 Python 표준 모듈을 가려 import 실패했습니다. v2에서 스크립트 경로를 제거해 해결했고 실패 로그도 보존했습니다. 제품 결함이 아닙니다. 보고 생성 준비 v2~v4도 PowerShell 기본 인코딩으로 문자열이 깨져 구문 검사를 통과하지 못했으며 실행하지 않았습니다. UTF-8 명시 생성판으로 고쳤고 준비 파일을 보존했습니다.
- 새 검토 scratch `C:/_proj/eks-independent-1029` 226,282바이트, 새 공개 검토 evidence 548,895바이트(작성 시 집계)입니다. 이외 테스트 임시 경로는 `/root/eksfix3_1029/pytest-independent-review-*`이며 실제 own pytest temp는 fast 535,663바이트·boundaries 9,801바이트(du -sb)이며 full/base3는 temp를 만들지 않았습니다. 기존 사본·자료는 보존합니다. [disk_guard inventory](../evidence/2026-10-29_eks-route-fix-independent-review/disk-inventory.json)는 등록0·미등록0으로 나옵니다. 이것이 기존 모든 WSL 사본을 자동 추적한다는 뜻은 아닙니다. 큰 산출물·새 clone은 만들지 않았습니다.

## 인계

구현 논리와 저장 구간 보존은 위 범위에서 통과했지만 무조건 ship 승인으로 바꾸지 않습니다. 매니저/Mobility 담당은 P2 정책판 추적·현재 wiki의 모델 처리 명시, 성능 표본 비용의 수락, 최신 통합판의 관련 회귀를 확인해야 합니다. 정류장별 실제 첫차 정확도와 EKS reader fatal은 여전히 미확인입니다. PR110 draft/HOLD 유지, 통합·push·배포·권한 변경 0건입니다.
