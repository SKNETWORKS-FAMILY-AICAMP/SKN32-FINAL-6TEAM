---
type: report
title: HOLD 1 — EKS 정밀 잔여18 건별 재판정(보존 bundle 복원·재실행)과 PR110 상태
status: draft
domain: travel
---

# HOLD 1 — EKS 정밀 잔여 18건 재판정 (2026-11-02 23:05 – 11-03 01:20 KST)

**결론: 18/18 = 100% 판정을 마쳤습니다. 근거 부족으로 남긴 건은 0/18 = 0%입니다.**

| 판정 | 건수 |
|---|---|
| 기대값 정정 | 14/18 = 77.78% (택시7·시각2·스키마1·남산타워 버스3·자전거 golden1) |
| 제품 결함 | 4/18 = 22.22% (새벽 첫차1·혼합 선택2·자전거 기본 golden1 — 결정 58 위반) |

- 보존 bundle을 격리 사본에 복원했습니다. 후보 끝 `1ab3f0d88`에서 전체층은 223/223 = 100%, 기본 Mobility층은 1629/1630 = 99.94%(기존 자료 부재 skip 1건)입니다. 같은 216개 노드 기준으로 18개가 통과로 바뀌었고 새 실패는 0개입니다.
- **통합·운영 반영은 하지 않았습니다(수락·승인 대기).**
  - 후보 사슬 10커밋은 로컬 전용입니다. 푸시하지 않았습니다.
  - 제품 결함 4건의 수정은 공유 계약(첫차 정책 v0.9.3 wiki 문안·rules 판올림)이 팀 wiki에 아직 없습니다. Mobility 담당 승인이 필요합니다.
- **PR110은 draft/OPEN이고 head는 `3fda4eee`입니다. main `57f3d2f`는 그대로입니다. HOLD를 유지합니다.** 병합·푸시·ready·배포는 0건입니다.

작업 주체: 라우팅 세션 36cd5c의 하위 세션. 사용자 지시를 총괄 5fbd35ab가 배정했습니다. 판정 검토로 Codex CLI 0.163.0과 1회 논의했습니다(도구 실행 없음, 결론 일치). 독립 담당자 승인이나 통합 예약은 아닙니다.

## 1. 복원과 보존 경계

**보존물 검증**
- `backups/proj-root13-final-20261102/KEY-ARTIFACTS.sha256` 18/18 = 100% 일치(bundle 4개·DB 보관본 4개·candidate 메타 10개).
- DB 보관본은 이번 범위(Mobility 전체층·기본층·non-db 관문)에서 쓰지 않았습니다. 시험 PG를 띄우지 않았습니다.

**격리 사본**
- `bash tools/guarded_clone.sh <golden 전체 bundle> C:/_proj/final_workspace/.tmp/clones/hold3-eks-precision-r18 36cd5c …`
- 첫 checkout은 Windows 긴 경로 때문에 실패했습니다. 사본 `.git/config`에만 `core.longpaths=true`, `core.autocrlf=false`, `core.eol=lf`를 넣고 다시 체크아웃했습니다. Linux 기록과 줄 끝을 맞추기 위해서입니다.
- precision·remaining·independent bundle을 fetch했습니다. 모든 bundle을 받은 뒤 `57f3d2f004d0`가 사본에 있습니다.
- 사슬(전부 직선형): `57f3d2f` → `3e5a60af6`·`acf0fadcd`·`346a57d4d`(precision) → `7484a180e`·`ee8ca8807`(remaining) → `513ab4cc0`(golden) → `52f933e82`·`56fc3ce15`·`47549aa4e` → `1ab3f0d88`(independent).

**입력 자료**
- 원본 `datasets/mobility/processed/mobility`에서 기준 113개 파일(289,950,471 B)을 복사했습니다. 원본은 읽기만 했습니다.
- 10-29 `inputs.json`과 대조해 원본 113/113, 사본 113/113의 sha256이 일치했습니다.
- 시험 하나(`test_public_graph_has_all_three_unambiguous_non_passenger_exceptions`)가 저장소 상대경로로 자료를 읽습니다. 그래서 자료를 사본 `datasets/` 아래(gitignore 대상)에 두었습니다.
- 버스 수집 스크립트 17개도 원본에서 덮어쓰지 않는 복사로 넣었습니다. 처음 기본층 실행에서 skip 38건이 이 준비 누락 때문이었습니다. 그 결과는 남겨 두고 다시 실행했습니다.
- 사본의 tracked diff는 0입니다.

**실행 환경**
- WSL Ubuntu(aarch64)의 기존 venv `/root/eksstruct1029-py312`를 읽기 전용으로 썼습니다(Python 3.12.16, NumPy 1.26.4, pytest 8.4.2). `-B`, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` 설정이라 `/root/eks*`에는 쓰기가 없습니다.
- 외부 차단: 기존 `offline_guard_v2`(10-29 보존본), 접속 불가 DB URL, mock LLM, 더미 설정값.
- Windows Python 3.12 venv(`date_risk_env_312`)와 지정 mingit 경로는 scratch에서 이미 사라졌습니다. Hermes git 사본을 scratch에 복사해 `safe_git.py`에 썼습니다.

**원본 상태**
- 원본 `C:/_proj/final_workspace`는 `safe_git.py rev-parse`·`log`만 실행했습니다. HEAD는 `efeb873a`이고, 쓰기·checkout·fetch는 0건입니다.
- 운영 DB·서비스·x600·EKS 쓰기는 0건이고, 모델 실호출도 0건입니다.

## 2. 재실행 결과

| 실행 | 결과 |
|---|---|
| T0 `346a57d4` 전체층(`-m "mobility_full and not live"`) | 197/216 = 91.20%. 실패 19건 = 인계 18건 + 자료 배치 준비 1건 |
| 위 준비 1건 재실행(자료를 저장소 상대경로에 둔 뒤) | 1/1 통과. 그래서 잔여는 **정확히 인계한 18건**입니다 |
| 18노드 귀속 행렬 `ee8ca8807` | 13/18 통과 |
| 〃 `513ab4cc0` | 14/18 |
| 〃 `52f933e82` | 15/18 |
| 〃 `56fc3ce15` | 15/18 |
| 〃 `47549aa4e` | 15/18 |
| 〃 `1ab3f0d88` | 18/18 = 100% |
| T1 `1ab3f0d88` 전체층 | **223/223 = 100%**. 공통 216 노드에서 실패→통과 19(18+준비1), 새 실패 0. 추가 7건은 택시 구성금액 검사 |
| T1 기본 Mobility층 | 1629/1630 = 99.94%. skip 1건은 건물 출입구 자료 부재(기존과 같음). 첫 실행은 1591 통과·39 skip(수집 스크립트 준비 누락)이었고, 결과를 보존했습니다 |

**빠른 관문(T1, 두 날짜: 실제 오늘 + `RELDATE_SHIFT_DAYS=37`)**
- 방식: travel 4 shard + non-travel 1 shard, `not live and not db and not slow`, 네트워크·DB 차단. 각 날짜에서 10982/11005 = 99.79% 통과, 실패 14, skip 9.
- 실패 6건은 core의 `network/database denied`입니다. **base main `57f3d2f`의 같은 shard에서 두 날짜 모두 같은 6건**이 나옵니다. 사슬은 Mobility 파일 18개만 바꿨습니다(`git diff --stat 57f3d2f 1ab3f0d88`, wiki 제외).
- 실패 8건은 `deploy/test_worker_shutdown` 하위 프로세스 기동 10초 초과였습니다. T1의 같은 shard를 두 날짜 모두 다시 돌리면 2528 통과·6 실패로 base와 같은 집합입니다. 그 파일만 단독으로 돌리면 40/40입니다.
  - 따라서 이 8건은 부하에 따른 일시 현상으로 보고, 첫 결과도 지우지 않고 보존했습니다.
  - 이 판단은 2회 재현에 근거합니다. 원인을 확정하지는 않았습니다.
- contract·security·architecture의 PG 필요 시험과 DoD는 이번에 돌리지 않았습니다. 10-29 기록에는 계약 368·보안 125·아키텍처 170·DoD 26이 있습니다.

## 3. 건별 판정 (18/18)

판정 기준: (A) 기대값 정정 = 현재 계약상 제품이 맞고 시험 기대가 낡음, (B) 제품 결함 = 현재 계약 또는 제품 자체 규칙 위반, (C) 근거 부족. golden 자동 재생성·허용오차 확대·시험 제외·skip 추가는 없었습니다(사슬의 diff에 `--ignore`·skip·마커 추가 없음).

| # | 시험 | 처음 통과한 커밋 | 판정 | 근거 |
|---|---|---|---|---|
| 1–7 | `test_regression_cases::test_full[car-CAR-02/03/03b/04/05/07/11]` | `7484a180` | **A** | 아래 「택시 7건」 |
| 8–9 | `test_plan_concurrency_v1::test_interleave_injection`, `::test_threads_8x80` | `7484a180` | **A** | 아래 「시각 2건」 |
| 10 | `test_earliest_v1::test_full_default_leg_unchanged_without_flag` | `7484a180` | **A** | 아래 「스키마 1건」 |
| 11–13 | `test_earliest_v1::…[ntower_namdae]`×2, `::test_full_plan_puts_earliest_in_skipped` | `7484a180` | **A** | 아래 「남산타워 버스 3건」 |
| 14 | `test_plan_bike_v1::test_golden_bike` | `513ab4cc` | **A** | 아래 「자전거 golden」 |
| 15 | `test_plan_concurrency_v1::test_bike_not_called_by_default` | `52f933e8` | **B** | 아래 「자전거 기본 golden」 |
| 16 | `test_earliest_v1::test_full_earliest_waits_for_first_train[after_last_holiday]` | `1ab3f0d88` | **B** | 아래 「새벽 첫차」 |
| 17–18 | `test_mixed_v1::test_full_earliest_uses_mixed_when_stations_blocked`, `test_station_fallback_v1::test_full_only_blocked_stations_is_no_service` | `1ab3f0d88` | **B** | 아래 「혼합 선택 2건」 |

**택시 7건 (A)**
- 옛 기대값은 9월의 미터 하한입니다. 예: CAR-02 8000 = 옛 「주간 기본금액 × 1.2」 할증 방식.
- 현재 계약:
  - 팀 wiki `teams/mobility.md` 「택시 과소추정 원인 수정 기준 (2026-10-12)」: 실제 조각 중점의 방향별 속도, 신고 심야 기본금액.
  - 2026-10-08 예산 여유 37%(최소 1000원, 100원 올림).
- 이번에 제품 import 없이 [재계산 코드](../evidence/2026-11-02_hold3-eks-precision-remaining18/taxi_recheck.py)를 새로 짰습니다. fixture 기하와 원본 TOPIS 프로파일만으로 계산했습니다. 거리는 7건 모두 3988.4 m, 저속은 0/225/391/229/0/924/0초입니다.
- 총액 11100·10300·11100·14400·9200·13500·9200이 새 기대값과 **7/7 = 100% 일치**합니다. [결과](../evidence/2026-11-02_hold3-eks-precision-remaining18/taxi_recheck.json)
- 사슬은 금액 7필드만 바꿨습니다. 거리·저속·미터·여유 단언 7개를 추가했고, 입력은 바꾸지 않았습니다.

**시각 2건 (A)**
- 서로 다른 호출의 실제 `departure_context.captured_at`을 같다고 비교한 시험 결함입니다.
- 두 시험 안에서만 시계를 고정했습니다. 전체 결과 동등 비교를 유지하고, 고정된 시각 값을 명시적으로 단언합니다.

**스키마 1건 (A)**
- 10-12 무폴백 인계에서 `arrive_late`에 `left_out`(탈락 근거)을 의도적으로 보존하기로 했습니다.
- 시험은 키 집합을 정확히 `{code, reason, left_out}`로 바꾸고, 비어 있지 않은 행 스키마를 단언합니다. `earliest`가 없어야 한다는 단언은 유지했습니다.

**남산타워 버스 3건 (A)**
- 원본 `bus_seg_profile` 4행(각 n=70)으로 별도 산술을 했습니다(10-29 산식의 경로만 바꾼 [사본](../evidence/2026-11-02_hold3-eks-precision-remaining18/bus_recheck.py)).
  - 접근 6 + 대기 5 + 승차 8 + 이탈 3 = 22분, 마진 15분 → 원래 목표 12:13에 11:36→11:58로 성립합니다. 재실행 값이 같습니다.
- 원래 입력은 「성립」으로 단언합니다. 별도 12:06 목표는 실패·최소 목표 12:07·slack −1로 잠갔습니다. 늦은 경로 검사를 없애지 않았습니다.

**자전거 golden (A)**
- v1 golden에는 직선 138.5 m × 1.4 = 194 m·4분의 합성 도보가 들어 있었습니다. 이는 10-12 「직접 도보의 근거 없는 대체 계산 금지」 계약 위반입니다.
- v1과 새 v2를 구조로 비교했습니다. [diff 12줄](../evidence/2026-11-02_hold3-eks-precision-remaining18/bike_v1_v2_diff.txt) 차이는 다음 셋뿐입니다.
  - 그 경로와 해당 항목 삭제
  - `skipped` 1건 추가(`arrive_late`, `walk_source_unavailable`, 자전거 left_out)
  - 뒤 항목 번호 당김
- v1 바이트는 보존됐습니다. `departure_context` 제외 규칙은 기존 `test_plan_v1`과 같습니다. 출력을 복사해 golden을 다시 만든 것이 아니라, 계약 변환 한 건으로 설명됩니다.

**자전거 기본 golden (B, 잔여 공백 있음)**
- 시험 쪽 정정: 기존에 검토된 `plan_example_out_all_v2`(10-14, `test_plan_v1`이 쓰는 것)를 그 golden을 만든 런타임(로컬 그래프, 실시간 끔)에서 비교하도록 바꿨습니다. 시계도 고정했습니다.
- 그 뒤에도 남은 실패는 제품 결함입니다. 혼합 요청에서 자전거가 `departure_context`·`more_options`에서 고를 수 있는 후보로 나왔습니다. 결정 58(본인 9/27: 섞어 주면 left_out에 이유만)과 어긋납니다. `52f933e8`/`56fc3ce1`이 `plan.py`를 고쳤고, `47549aa4`가 직접 단언을 추가했습니다.
- **잔여 공백(Codex도 지적)**: 기본 런타임(`local_router=False`)의 출력은 이제 어떤 검토된 golden과도 비교되지 않습니다.
  - 이번 [탐침](../evidence/2026-11-02_hold3-eks-precision-remaining18/probe_7b.json)에서 golden 런타임 출력은 all_v2와 같았습니다.
  - 기본 런타임은 경로 4/4 = 100%(all_v2 기준)와 3/4(all_v1 기준)에서 다릅니다. 예: `dinner_to_lotte_mart`를 기본은 `subway_1`로 계획하고, golden 런타임은 계획하지 않습니다.
  - 기본 런타임 기대값은 Mobility 담당이 검토해 정해야 합니다. 임의로 만들지 않았습니다.

**새벽 첫차 (B)**
- 제품은 710→301을 03:49에 출발한다고 냅니다. 710은 03:50에 기점을 떠나는데, 약 12 km 하류의 중간 정류장(seq 20)에서 04:00 승차를 허용했습니다. 중간 정류장에 첫차가 언제 도달하는지 확인하지 않아 실현 불가능한 탑승을 성립으로 판정했습니다.
- `1ab3f0d88`이 첫 통과 하한을 추가했습니다. 산식은 기점 첫차 + 누적 프로파일(최선 p50, 최악 max(p90, p50))이고, 프로파일이 없으면 거리/속도 모델을 씁니다.
- 수정 전 `47549aa4`에서는 실패, `1ab3f0d88`에서는 통과입니다.
- 이 정책의 계약 문안은 미커밋 v0.9.3 patch([10-29 기록](2026-10-29_eks-route-policy-full-recheck.md))에만 있습니다. 팀 main wiki에는 없습니다. **결함 판정은 B이고, 정책·rules 판올림은 승인 대기입니다.**

**혼합 선택 2건 (B)**
- `MIX_VERIFY_MAX=3` 아래에서 판정 자리가 다음 두 곳에 쓰였습니다.
  - 구체화 뒤 추정이 52.2분에서 89.1분으로 늘어난 rail+bus 맨 앞 후보
  - bus+bus 후보
- 그래서 판정받지 못한 8→5→2016(10:09 출발·54분)이 선택된 320→2412(10:08·58분)보다 제품 자체 `_rank` 규칙(늦게 떠나도 되는 것 우선)에서 앞서는데도 선택되지 않았습니다([원인 귀속](2026-10-29_eks-remaining3-shape-c-causality.md)).
- `1ab3f0d88`의 `settle_head`가 같은 모양 안에서 순서를 다시 매깁니다. 판정 상한은 바꾸지 않았습니다. 수정 전 실패, 수정 후 통과입니다.

**Codex 1회 논의** ([질문](../evidence/2026-11-02_hold3-eks-precision-remaining18/codex_prompt.md)·[답](../evidence/2026-11-02_hold3-eks-precision-remaining18/codex_answer.md)): 그룹별 A/B 판정이 위와 같고, C로 낮출 그룹은 없다는 의견이었습니다. 추가로 두 가지를 지적했습니다.
- 자전거 기본 golden에서 비교 런타임을 바꾼 것은 가림 위험이 있습니다. 위 잔여 공백으로 기록했습니다.
- 새벽 첫차는 미병합 계약이어도 결함 판정 B가 맞습니다. 통합 전에 정책 범위·p50/p90·대체 계산·결측 처리·rules 판을 승인받아야 합니다.

## 4. 원격 상태 (읽기 전용, gh CLI)

| 대상 | 값 |
|---|---|
| PR110 | OPEN · **draft** · head `3fda4eee2613` · base main · mergeable · 마지막 갱신 2026-10-28T22:17:46Z |
| main | `57f3d2f004d0` |
| role-manager | `fab3da50ab97`. main보다 17커밋 앞서고 38커밋 뒤처집니다. Mobility 차이는 `bus_profile.py`의 한 줄(`np.isnan`→`math.isnan`)입니다 |
| develop | `3463b30c657d`. main보다 0커밋 앞서고 33커밋 뒤처집니다 |
| 후보 사슬 | 10커밋, 로컬 전용(push 0). 기반은 main이고 role-manager가 아닙니다 |

[원격 상태 JSON](../evidence/2026-11-02_hold3-eks-precision-remaining18/remote-state.json). PR110에 대한 병합·ready 전환·댓글·push는 0건입니다. reader fatal(HOLD 2)은 이 항목 범위가 아니고, HOLD를 유지합니다.

## 5. 상태 구분

| 항목 | 상태 | 비율 |
|---|---|---|
| 18건 판정 | **완료** | 18/18 = 100% |
| 판정 근거 재실행(전체층·귀속 행렬·기본층) | **완료** | 223/223 = 100%, 행렬 7커밋 중 7개 실행 |
| 빠른 관문 두 날짜(non-db) | **완료**. 사슬로 생긴 새 실패 0 | 10982/11005 = 99.79% ×2. base와 같은 6건, 일시적 8건은 재실행에서 해소 |
| 제품 결함 4건 수정의 통합 | **수락·승인 대기**: Mobility 담당이 정책 v0.9.3과 결정 58 구현을 승인해야 합니다. role-manager에 둘지 결정하고 PG 관문을 재실행해야 합니다 | 분모 모름 |
| 자전거 기본 런타임 golden 공백 | **수락·승인 대기**(담당자 기대값 결정) | 분모 모름 |
| PR110 | **HOLD**(draft 유지, reader fatal 근거 미확보) | 해당 없음 |
| BLOCKED | 없음 | 0 |

## 6. 보존·사본

- **증거(공개용)**: [evidence 폴더](../evidence/2026-11-02_hold3-eks-precision-remaining18/). 들어 있는 것:
  - 행렬 요약, 전체층·기본층·행렬 XML
  - 재계산 코드·결과
  - 탐침, Codex 질의·답, 관문 요약, 원격 상태
  - `SHA256SUMS`
- **원시 로그·실행 스크립트(비공개)**: guguroute `backups/hold3-eks-precision-r18-1102/`. 관문 5 shard × 2 날짜 원 로그·XML, base·재실행 로그를 포함하고 `SHA256SUMS`가 있습니다. 더미 설정값이 든 실행 스크립트라 비공개 쪽에 두었습니다.
- **격리 사본** `C:/_proj/final_workspace/.tmp/clones/hold3-eks-precision-r18`
  - 2,620,037,830 B: `.git` 719,345,414 B, 입력 자료 289,950,471 B 포함
  - HEAD `1ab3f0d88`, tracked diff 0
  - `disk_guard release`로 반환해 유휴 사본으로 남겼습니다. HOLD 3(513ab4cc·1ab3f0d88 통합)이 같은 bundle 사슬을 재사용할 수 있습니다.
  - 삭제는 루트 규칙상 대상별 승인이 필요해 하지 않았습니다.
- **scratch** `hold3-eks-precision-r18-1102/`(397 MB). 이 중 Hermes git 복사본 389 MB는 재생성할 수 있어 정리했습니다. WSL `/tmp/hold3-eks-r18-1102`는 WSL 재기동으로 이미 없었습니다.
