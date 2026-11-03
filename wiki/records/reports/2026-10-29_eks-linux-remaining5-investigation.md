---
type: report
title: EKS Linux 잔여5 원본 재현·경로와 golden 개별 진단
status: draft
domain: travel
---

# EKS Linux 잔여5 조사

**새 Linux 재현은 통과0/5 = 0%·실패5/5 = 100%·오류0·skip0입니다. 추가 해소0/5 = 0%, PR110 draft/HOLD 유지입니다.** 이전 전체층218/223 = 97.76%는 이전 실행의 결과이며 이번에223개 전체를 재실행한 수치가 아닙니다. 운영 reader fatal의 원인은 미확정입니다. 제품·시험·golden 수정, 운영 쓰기·모델 실호출·push·merge·배포는 모두0건입니다.

## 재현과 보존

루트와 cs AGENTS/RULE, wiki 색인·개발 역할, Mobility 현행 계약 및10/11 엄격 golden 계약, 이전 인계·보고·coord EKS 관련 알림을 읽었습니다. 변경·자체 검토 담당은 Codex이며 별도 독립 검토자의 승인을 주장하지 않습니다. 원격 읽기에서 main57f3d2f004d0, PR110 open/draft3fda4eee/HOLD를 확인했습니다. 기존 운영3회 중 성공2/3 = 66.67%·fatal1/3 = 33.33%는 그대로입니다. 운영 전체 검증 분모는 모릅니다.

이전 최종 tip ee8ca88070ac0b999750098b70ff7e3a825fd0f9(제품/시험 소스7484a180)을 새 no-hardlinks 사본 `/root/eksremaining5_1029/candidate`로 복제했습니다. 기존 모든 사본·자료·시험DB·임시 폴더를 보존했습니다. 원래113개 자료289950471바이트를 새 사본에 복사·SHA256 검증113/113 = 100%, 이전 기본 Linux 사본과 시험5·golden3·입력/픽스처2의 바이트 일치10/10 = 100%를 확인했습니다. 새 사본의 tracked diff는 없습니다. Linux ARM64/Python3.12.16에서 이전 mock·외부 연결 차단 환경을 유지했고 DB를 시작하지 않았습니다. EKS AMD64 실서버 검증은 아닙니다.

[재현 XML](../evidence/2026-10-29_eks-linux-remaining5-investigation/reproduce.xml)·[실제 명령/종료1](../evidence/2026-10-29_eks-linux-remaining5-investigation/reproduce-exit.json)·[로그](../evidence/2026-10-29_eks-linux-remaining5-investigation/reproduce.log)·[해시/런타임/후보 요약](../evidence/2026-10-29_eks-linux-remaining5-investigation/summary.json).

## 실제 실패와 판단

| 원래 실패 | 이번 관측 | 판단·남은 조건 |
|---|---|---|
| `test_full_earliest_waits_for_first_train[after_last_holiday]` | 기대05:23 지하철, 실제03:49→05:16·목표05:36, 버스710→301 | 옛 지하철 첫차 기대만으로 버스를 오답이라고 확정하지 않음. 기점 첫차와 중간 정류장 통과의 제품 한계는 아래처럼 별도 보존 |
| `test_full_earliest_uses_mixed_when_stations_blocked` | earliest는303→2412 버스+버스, 목표12:05. rail+bus라는 단언 실패 | rail+bus 도달성 자체는 있음. 같은 목표의 별도 rail+bus도 성립하므로 후보 탐색/선택과 경로 부재를 구별. prefix·허용 수단 확대0 |
| `test_full_only_blocked_stations_is_no_service` | 실제320→2412 버스+버스, 원래11:30 목표 출발10:08. `subway_bus` prefix 단언 실패 | 생성된 rail+bus7개도 원래 목표에는 성립하나 선택되지 않음. 제한 탐색이 전역 최적 후보를 보장하지 않는 한계. 출발이 더 늦은 B후보10:09도 별도 확인했으며 이를 최적성 결함 해소로 표시하지 않음 |
| `test_golden_bike` | 옛7 items/2 routes→6 items/1 route. 저녁→롯데마트의194m/4분 직접도보가 사라지고 `arrive_late` skipped·탈락 근거/출발 문맥 추가 | router 픽스처에 검증된 도보 경로가 없는데 직접도보를 복구하면10/12 무폴백 계약 위반. golden 자동 생성/삭제/부분 비교0 |
| `test_bike_not_called_by_default` | 자전거 호출0 단언은 통과한 뒤 전체 v1 golden equality 실패. items10·left_out22·routes10개 비교항목 차이 | 시각·도보·제외 사유·출발 문맥이 섞임. `test_plan_v1`의 별도 v2는 `local_router=True` 조건이라 이 시험의 기본False에 바로 대입하지 않음. 전체 equality 유지 |

### 새벽: 환경 실패로 닫을 수 없는 제품 경계

원본710은 기점 상암차고지 첫차03:50, 경복궁은 seq20·기점부터12,048m입니다. 실제 trace는 장소03:49 출발+접근11분으로04:00 정류장 판정을 하고,710→301을 계산합니다.301은 기점04:00·승차 seq53까지25,514m입니다. 현 `verify_time.py`는 기점 첫차와 요청 시각을 비교하지만 첫차의 중간 정류장 도달을 별도로 보장하지 않습니다. 이는 운영체제 차이나 원자료 누락으로만 설명할 문제가 아닙니다.

제품 함수를 쓰지 않고 원본19/52구간 프로파일을 누적했습니다.710 holiday p90의 기점03:50→경복궁 통과 모델은04:26.44지만 p10/p50은 도중 필요한 유효 셀이 없어 완전한 사슬을 만들지 못합니다.301 holiday p50/p90은05:21.71/05:38.56입니다. **분위수 누적은 실제 첫차 관측이나 최소 도달시각이 아닙니다.** 이를 새 정답이나 첫차 강제 상한으로 채택하지 않았습니다. 첫차의 정류장별 근거 및 근거 부재 시 처리 계약을 확인해야 안전한 수정이 됩니다. 옛05:23으로 돌려놓기 위해 버스 수단·프로파일을 끄지 않았습니다. [원본 기반 독립 산술](../evidence/2026-10-29_eks-linux-remaining5-investigation/independent-first-pass.json)·[실제 trace](../evidence/2026-10-29_eks-linux-remaining5-investigation/dawn.json). 원문 노선/정류장/프로파일 행은 로컬 `independent-first-bus-facts.json`에 보존했습니다.

### 혼합: rail+bus 없음과 다른 경로 선택은 다름

원래 사고·좌표·시각·버퍼·precision을 유지하고 별도 harness에서 A/B를 직접 열거했습니다. A0/B13, materialize13/13 = 100%, 원래11:30 목표에7/13 = 53.85% 성립·6/13 = 46.15% 심야 첫차 전입니다. 성립7개의 장소 출발은09:14~10:09이며 모두 앞 일정 끝10:45 이전입니다. 이는 제품 생성기가 내는13개에 대한 조사이지 현실의 모든 경로 분모가 아닙니다.

잠실8호선→천호5호선→왕십리→2016은10:45 장소 출발(접근 후10:49 판정), 최악 도착11:52+버퍼10+이탈3분으로12:05 목표에 성립합니다. 직접 지정 재검증에서도 slack0으로 확인했습니다. 이 경로는 earliest 소스3개에도 포함되지만 최종 `leg()`는 버스+버스를 골랐습니다. 따라서 앞 인계의 「2412 중단 진단에서 rail+bus 성립 미입증」은 그 진단의 한계였으며, 이번에는 **원래 사고 조건에서 성립을 입증**했습니다. 최종 선택은 제한된 후보 탐색·순서·동률 처리와 별도이며, rail+bus 강제 선택을 현행 제품 요구로 임의 신설하지 않았습니다. [전체13개 진단](../evidence/2026-10-29_eks-linux-remaining5-investigation/rail-bus.json)·[명시 경로 재검증/원래 선택 trace](../evidence/2026-10-29_eks-linux-remaining5-investigation/explicit-recheck.json).

### golden: 환경과 계약 차이를 보존

자전거 픽스처는 직접도보의 근거를 제공하지 않습니다. 원래 자전거 경로는 남고 근거 없는 직접도보만 사라집니다. 기본 golden은 정밀 시각·현재 source 조건·v1의 옛 경로/문맥을 섞고 있습니다.10/14 v2 보고의 도보/GTX-A 설명은 후보 사본에서 읽었으며 원본 작업폴더에는 그 보고 파일이 없었습니다. 이를 원본에 복원하거나 v2 결과를 이번 조건의 정답으로 복사하지 않았습니다. [항목별 원값/실제값 비교](../evidence/2026-10-29_eks-linux-remaining5-investigation/golden-diff-audit.json). 배열 길이가 바뀐 차이는 배열 한 항목으로 기록했으므로4/42는 전체 leaf 개수나 성능 분모가 아닙니다.

## 인코딩과 준비 오류

지정 handoff/report는 strict UTF-8 읽기2/2 = 100% 성공, U+FFFD 및 `???` 연속0개입니다. 첫 PowerShell 기본 디코딩 출력만 깨졌고 UTF-8 명시 시 원문이 정상입니다. 원문 바이트·해시를 보존했으며 고친 문서0개입니다. 다른 wiki 색인에서 보인 과거 물음표 행은 이번 두 파일과 별개이며 권위 원문 없이 추정 복원하지 않았습니다. [두 원문 해시](../evidence/2026-10-29_eks-linux-remaining5-investigation/encoding.json).

첫 보존 검사에서 Windows CRLF 사본과 Linux LF를 바이트 비교해 assertion이 실패했습니다. 파일을 변환하지 않고 이전 기본 Linux 사본과 재대조해10/10 일치를 확인했습니다. PowerShell jq 인자 오류는 구조화된 Python API 읽기로 다시 확인했습니다. 없는 root10/14 보고 경로 읽기도 실패로 남기고 후보 사본의 실제 보고만 읽었습니다. 이 준비 오류를 제품 실패5개에 합산하지 않습니다. 모든 helper·JSON·실패 캡처·로그는 `C:/_proj/eksremaining5_1029`, Linux 사본은 `/root/eksremaining5_1029`에 보존합니다. 전용DB·리스너 생성0, 삭제0입니다.

## 다음 작업 경계

새벽은 정류장별 첫차 근거/미확인 처리, 혼합은 제한 탐색과 선택 요구의 명확화, golden은 기존 입력·환경별 권위 기대의 개별 검토가 남았습니다. 증거가 부족한 기대 교체나 계약 변경을 이번 수정으로 만들지 않았습니다.5개는 모두 열린 실패이며 새 수락·독립 담당 승인·통합 예약은 없습니다. RAG16 미준비는 이전 별도 결과이고 이번에DB를 실행하지 않았으므로 갱신하지 않습니다. reader 운영 fatal은 이5건으로 원인을 추정하지 않으며, 기존 허용된 reader 이유 로그 확보와 운영 수락 전까지 PR110 HOLD를 유지합니다.
