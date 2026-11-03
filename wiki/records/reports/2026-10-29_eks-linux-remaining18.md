---
type: report
title: EKS Linux 잔여18 진단·13건 계약 정정·5건 보존
status: draft
domain: travel
---

# EKS Linux 잔여18 후속

**기존 실패 13/18 = 72.22% 추가 해소, 같은216개에서 211/216 = 97.69% 통과·5실패·새 실패0. 새 구성금액7개를 합치면 218/223 = 97.76% 통과입니다. PR110 draft/배포 HOLD를 유지합니다.** 실제 EKS fatal 원인과 운영 수락은 해결되지 않았습니다. 기존 운영 기준선 성공2/3=66.67%·fatal1/3=33.33%를 바꾸지 않았으며 전체 운영 검증 분모는 모릅니다. 운영 요청·모델 실호출·push·merge·배포0입니다.

## 확인과 변경 경계

지정 인계, 루트/cs AGENTS·RULE·wiki 색인·개발 역할·Mobility 현행 계약, coord의 precision/Linux/fatal/release 알림을 읽었습니다. main57f3d2f004d0와 PR110 draft3fda4eee/HOLD를 읽기 전용으로 확인했습니다. 이전 후보346a57d4dca74dc18dd2bbee0da1873c30506cd5에서 **새 no-hardlinks 격리 사본** `C:/_proj/eksremaining1029/candidate`, 브랜치 `fix/linux-remaining18-20261029`를 만들었습니다. 담당·자체 검토는 Codex이며 아래 별도 산술은 같은 작업자의 독립 구현입니다. 독립 검토자·Mobility 담당·매니저 승인이나 통합 예약을 받은 것으로 표시하지 않습니다. [최종 원격 상태](../evidence/2026-10-29_eks-linux-remaining18/remote-final.json).

후보의 시험5파일만 바꿨습니다(원래18건 관련4파일+아래 별도 날짜 준비1파일). 제품 코드·공유 계약·정밀 시간표·guardrail·golden·마커·제외 조건·workflow 변경0입니다. 원본 제품/Git 설정·색인·refs를 대상으로 쓰기 명령을 실행하지 않았고, 원본 자료113/113=100%(289950471바이트)와 사본을 재해시했습니다. 과거 그래프·백업·원문 입력을 보존했습니다. [의미/AST 보존](../evidence/2026-10-29_eks-linux-remaining18/semantic-verification.json)·[입력 해시](../evidence/2026-10-29_eks-linux-remaining18/inputs.json)·[검토할 diff](../evidence/2026-10-29_eks-linux-remaining18/source.patch).

## 원인별 판단

- **택시7건:** 9월 미터 하한 기대값이 남았습니다. 현재 계약은 신고 심야 기본금액, 실제 이동 조각 중점의 방향별 속도, 미터+중형37% 여유(최소1000원·100원 올림)+통행료입니다. 제품 함수를 쓰지 않고 원본 합성 경로·방향 대응 CSV·TOPIS 프로파일로 거리3988.4m, 저속0/225/391/229/0/924/0초를 다시 계산했습니다. 총액은 CAR-02 11100,03 10300,03b11100,04 14400,05 9200,07 13500,11 9200원입니다. 정확한 금액7필드만 정정하고 거리·저속·미터·여유·총액의 추가 단언7개를 넣었습니다. 기존 입력12/12=100%와 다른 기대값은 보존했습니다. 실제 택시 정확도 개선 주장이 아닙니다. [계산 코드](../evidence/2026-10-29_eks-linux-remaining18/taxi_oracle.py)·[원문 대응/구성값](../evidence/2026-10-29_eks-linux-remaining18/taxi-independent-facts.json)·[전후](../evidence/2026-10-29_eks-linux-remaining18/expectation-changes.json). 계약: [Mobility 택시 과소추정 기준](../../../final_project_cs/wiki/teams/mobility.md#택시-과소추정-원인-수정-기준-2026-10-12).
- **동시성2건:** 서로 다른 호출의 `captured_at`을 그대로 같다고 비교했습니다. 두 시험 안에서만 계획·문맥 시계를 고정하고 **전체 결과 equality를 유지**했습니다. 기록 시각을 없애지 않았고 고정값을 명시적으로 검사합니다. 기존 공유 싱글턴/복사 끔의 실패 유도 검사,80건·8스레드·빈 캐시·입력 구별·싱글턴 보존·경쟁 뒤 순차 재검사도 유지했습니다.
- **스키마1건:** 10/12의 arrive_late 탈락 근거 보존 계약 이후에도 정확한 키 집합을 `code/reason`으로 고정했습니다. `code/reason/left_out` 정확 집합과 비어 있지 않은 이유 목록·행 스키마를 검사합니다. `earliest`가 없는 기본 경로라는 검사는 유지합니다. [계약과 당시 수정 근거](../../../final_project_cs/wiki/records/reports/2026-10-12_mobility_no_fallback/CLAUDE-HANDOFF-20261013-from-45290d-v1.md).
- **남산타워3건:** 원본 정류장9→13의 유효 프로파일4행(각 n70), 접근 좌표와 현행 우회1.4/속도1.04, 배차9를 별도 계산했습니다. 접근6+대기5+승차8+이탈3=22분, p90모델과 버퍼10의 마진15분입니다. 원래12:13 입력은11:36→11:58 성립을 **그대로 검사**하고, 별도12:06 입력의 실패·11:30→11:52·최소 목표12:07·1분 전 실패·slack-1·skipped 봉투를 함께 잠급니다. 원래 입력을 실패하게 만들도록 고치지 않았습니다. 전체 계획 off/on equality에도 고정 시각을 써 문맥을 보존합니다. [원문4행과 계산](../evidence/2026-10-29_eks-linux-remaining18/bus-independent-facts.json)·[별도 구현](../evidence/2026-10-29_eks-linux-remaining18/bus_oracle.py).

**전체 검사에서 별도로 발견한 날짜 준비5건:** 이동 계산기 등록 흐름은 원래2026-10-05 입력을 오늘 등록하면서 정상적인 `all_dates_in_past` 거절을 받았습니다. 원래 날짜·모든 시험 본문을 유지하고 해당 fixture의 정책 시계만2026-10-01로 고정했습니다. 실제 날짜 판정 함수가9/30은 거절·10/5는 허용하는 두 방향을 함께 검사합니다. 흐름7/7=100%이며 원래18건 해소율에는 이5건을 더하지 않습니다. [흐름 재실행](../evidence/2026-10-29_eks-linux-remaining18/native-candidate-flow.xml).

정밀도·금액 허용오차·마진·버퍼를 넓히지 않았습니다. 별도 진단에서 예산 여유 제거7/7=100%, 기록 시각 제거1/1=100%, 버스 프로파일 제거3/3=100%가 각각 실패했습니다. 이 변이는 정식 실행에 섞지 않았습니다. [금액 음성 대조](../evidence/2026-10-29_eks-linux-remaining18/taxi-no-reserve.xml)·[시각 음성 대조](../evidence/2026-10-29_eks-linux-remaining18/capture-no-timestamp.xml)·[프로파일 음성 대조](../evidence/2026-10-29_eks-linux-remaining18/bus-profile-removed.xml).

## Linux 검증

Linux ARM64/Python3.12.16/NumPy1.26.4, mock provider, 외부 연결 차단 플러그인과 전용 루프백 시험 PG를 사용했습니다. 최종 전체 검사는 `/root/eksremaining1029-native`의 기본 Linux 파일시스템 Git 사본에서 수행했습니다. 원본113개를 양쪽에 동일 복사·검산했고, 후보는346a57d4+시험5파일 patch입니다. 실제 검증한 Git blob과 로컬 커밋을 대조했습니다. EKS AMD64 실서버 검증과 구별합니다. [스냅샷·blob 대조](../evidence/2026-10-29_eks-linux-remaining18/native-final-snapshots.json).

| 실행 | 새 기준선 | 최종 후보 |
|---|---:|---:|
| 공통 전체 Mobility216 | 198/216=91.67%·18실패·skip0 | 211/216=97.69%·5실패·skip0 |
| 추가 구성금액 포함 | 기존 노드216 | 218/223=97.76%·5실패·skip0 |
| 기본 Mobility | 1606/1607=99.94%·1skip | 1606/1607=99.94%·1skip |
| 계약 | 368/368=100% | 368/368=100% |
| 보안 | 125/125=100% | 125/125=100% |
| 아키텍처 | 170/170=100% | 170/170=100% |
| DoD | 26/26=100% | 26/26=100% |

기준선은 이전18실패를 정확히 재현했습니다. 공통216/216=100% 노드를 대조해 정확히13개만 통과로 바뀌고 새 실패0, 새7개는 모두 통과했습니다. 중간 후보215/223·8실패도 보존했습니다. 최종 후보의 기본 Linux 파일시스템 재실행도218/223·5실패로 같았습니다. 기본 관문의 skip1은 원본에 없는 건물 출입구 자료이며 통과로 세지 않았습니다. [노드별 비교/잔여](../evidence/2026-10-29_eks-linux-remaining18/comparison.json)·[전체층 최종 XML](../evidence/2026-10-29_eks-linux-remaining18/native-candidate-full.xml).

**전체 기본 testpaths(`tests`+`eval/tests`, non-live) 최종 실행: 13455/13805 = 97.46% · 실패2 · 오류14 · skip334. 전체는 녹색이 아닙니다.** 기준선은 13450/13805 = 97.43% · 실패7 · 오류14 · skip334입니다. 동일 노드 전체를 비교해 날짜 준비5개만 통과로 바뀌고 새 실패0입니다. 남은 실패2+준비 오류14=16개는 양쪽 동일한 RAG 코퍼스 미적재 조건입니다(필요 여행문서12·청크130·1024차원 벡터130, 시험 DB 실측0·0·0). 가짜 벡터나 옛 쇼핑몰 자료로 채우지 않았습니다. 이 시험 DB의 미준비 상태로 실제 EKS fatal 원인을 단정하지 않습니다.

전체층223은 별도 실행이고 기본 전체 시험 분모와 중복 합산하지 않습니다. eval 준비 확인38/38=100%입니다. 최종 전체 검사는 파일 단위2-worker로 기준선→후보를 차례로 돌렸습니다. 양쪽 각각 새 base+worker DB3/3=100%를 확인했고 기존 worker DB가 있으면 중단했습니다. 생성한 시험 DB 정리 요청도 실제 DROP 대신 보존했으며 업무 단언은 바꾸지 않았습니다. `--ignore`·새 마커 제외·skip 추가0, worker 재시작0입니다. 기존 CI가 제외하는 RAG도 이번 명령에는 새 제외를 넣지 않았습니다. [명령·종료값](../evidence/2026-10-29_eks-linux-remaining18/commands.json)·[메모리 표본](../evidence/2026-10-29_eks-linux-remaining18/native-serial-memory.json)·[DB 보존 기록](../evidence/2026-10-29_eks-linux-remaining18/native-db-preservation-events.json).

## 남긴5건과 준비 실패

남은5/18=27.78%는 **새벽 첫차1·rail+bus 도달성2·golden2**입니다. 원래 전체 입력·단언·golden 바이트를 유지했습니다. 새벽은710→301의03:49→05:16(목표05:36)과 옛 첫 열차05:23 기대의 차이이며 기점/중간정류장 첫차·운행일을 더 확인해야 합니다. 혼합2건은 새 버스+버스 후보가 고르게 된 상황입니다. 실제2412 운행중단을 추가해도 rail+bus의 성립이 입증되지 않아, 허용 prefix만 넓혀 닫지 않았습니다. [추가 사고/최소시각 진단](../evidence/2026-10-29_eks-linux-remaining18/route-followup.json).

자전거 golden은 router 없는 픽스처에서 옛194m/4분 직접 도보가 사라지고 근거를 가진 skip과 출발 문맥이 추가됐습니다. 기본 golden은 현재 `local_router=False`와 다른 조건의 옛 v1/v2 기대를 섞고 있습니다. 시각·문맥·제외 이유별 검토 없이 복사/재생성하지 않았습니다. 현행 [직접 도보 무폴백 계약](../../../final_project_cs/wiki/teams/mobility.md#직접-도보의-근거-없는-대체-계산-금지-2026-10-12-사용자-지시), [엄격 골든 재검토 기준](../../../final_project_cs/wiki/records/reports/2026-10-11_mobility.md#2026-10-11-계획-시험-기준-재검토-계약)을 유지합니다. [18개 각각의 계약/판단](../evidence/2026-10-29_eks-linux-remaining18/diagnoses-final.json).

초기 helper 경로·미설정 경로·BOM·셸 인자 오류는 도구 실행 기록과 요약에 남겼습니다. 고유 pytest 임시 폴더 부모 누락은 작업자의 준비 결함입니다. 처음 광범위 실행894통과/22동일 준비 오류/5skip과 eval35통과/3동일 오류의 XML·로그를 보존하고 고쳤습니다. 직렬688통과·0실패/오류 중간 실행도 정상 중단해 보존했습니다(각 중간 실행의 전체 분모는 모름). 이어 NTFS 임시 폴더의 나노초 수정 시각 보존 실패, 외부 차단기의 시험 소유 로컬 서버 차단, 하위 pytest의 전역 플러그인 간섭, 보존을 위한 DB 정리 차단을 확인했습니다. Linux 기본 파일시스템·소유한 로컬 서버만 허용하는 차단기·명시적 CLI 플러그인·DB 보존으로 재실행했습니다. 시험·시한·단언을 느슨하게 하지 않았습니다.

두 전체 검사를 동시에 돌린 첫 기본 Linux 실행에서는 메모리 할당 실패2건과 일시적인 골든 차이1건도 관측했습니다. 해당3개는 기준선·후보 분리 재실행에서 각각3/3=100% 통과했고, 최종은 두 worker·한 suite씩 전체 재실행해 대조했습니다. 앞선 raw 결과를 지우거나 최종 성공 분모에 섞지 않았습니다. 골든 차이를 입증 없이 특정 원인으로 확정하지 않습니다. 버스 별도 계산의 옛1.3 접근 가정도 실제1.4를 읽어 정정했고 옛 산출물은 남겼습니다(올림 결과6+3은 동일). [준비 이력](../evidence/2026-10-29_eks-linux-remaining18/preparation-attempts-final.json)·[양쪽 분리 재검사](../evidence/2026-10-29_eks-linux-remaining18/native-candidate-isolation.xml).

소스 커밋은 로컬 `7484a180eeb478092f9626b714c67f0fdc91c5f6`, push0입니다. 수정 전5파일·명시적으로 기록한 로그/XML·시행착오·자료 사본은 `C:/_proj/eksremaining1029`, 기본 Linux 사본·고유 시험 폴더는 `/root/eksremaining1029-native`에 남겼습니다. 보안/전체 원시 XML의 탐지기 양성 시험 id는 바이트를 그대로 로컬에 남기고 공개에는 집계·해시·위치를 기록합니다. 탐지기 예외나 원시 자료 삭제/수정0입니다. 전용 PG는 종료하고 클러스터와 검증한 별도 tar 사본을 유지했습니다. [원시 보존/해시](../evidence/2026-10-29_eks-linux-remaining18/raw-preservation.json)·[PG 보존](../evidence/2026-10-29_eks-linux-remaining18/pg-preservation.json).

5개 전체층 실패와 실제 reader fatal은 서로 다른 미해결 항목입니다. 허용된 기존 reader 운영 근거와 수락 전까지 PR110 draft/HOLD이며, 새 자격증명·권한·workflow로 우회하지 않습니다.
