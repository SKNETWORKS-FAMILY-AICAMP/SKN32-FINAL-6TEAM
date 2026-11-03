---
type: report
title: 공급자 안전 수정 부모 재실행과 안정성 한계
status: draft
domain: travel
---

# 공급자 안전 수정 체크포인트

[부모 실제재실행] 현재프로필scratch/reader-safety/final_verify.py를실행했습니다. 고유402선택중398통과/4실패 = 99.005%, exit1입니다. 4실패는금지된실제HTTP서버bind시험입니다. 실행중trip_api.py가다른절작업으로변경돼tree_unchanged_during_run=false이며최종안정검증으로인정하지않습니다. run: cache/scratch/reader-safety/final-runs/20261024T145954_816996Z/summary.json 및pytest.log.

child는취소·늦은response정리/다음read차단,stream공유deadline,매유료시도reader전용failclosed예산,정확backend/model출처,reader원문외부전송기본차단,905schema준비점검을구현했습니다. 직접API주입과legacy줄reader우회도차단하며기존일반업무API정책은유지합니다. 부모는보고서와핵심코드를읽었고원결함범위만독립확인할새readonly child에넘겼습니다. 외부전달기본설정은false이며사용자승인없이켜지않았습니다.

실transport가이미blocking이면강제취소할수없고daemon/자원이남을수있습니다. 동기DB예산reserve·비스트림줄읽기는driver timeout에의존합니다. 대역에서늦은반환cleanup과논리deadline을검증한것이지엄격한서버생성취소/실wallclock보장이아닙니다. schema준비검사도실DB를조회/적용한증거가아닙니다.

다음단계는원안전결함독립확인·남은/plan/UI완료뒤단일전체회귀입니다. 5DBfixture오류와4HTTP시험은별도실환경승인검증대상입니다. DB/모델/HTTP·앱서비스·운영배포·커밋푸시는하지않았습니다.

## 독립 확인 추가 기록 — 하위 비스트림 우회 미해결

독립 child가 기존 안전25/25를 재실행했으나, stream 생략 read_source(agent=FailoverChat, agent_mode=on) → agent_read 일반 structured 경로의 원결함 우회를 대역으로 재현했습니다. local 실패/유료 global gate True/strict reader gate False에서 유료 대역1회·global reserve1회·strict reserve0회·이름sentinel 원문 전달입니다. 실제 외부 호출은 없습니다. 정상 process API는 stream 정책을 검증·주입하므로 정상 API에서의 직접 누수 재현과는 구분합니다.

앞서 적은 외부 기본 차단/예산 보완을 모든 허용 하위 호출에서 완결됐다고 읽으면 안 됩니다. 결함을 다시 열고 새 child에 정확반례 TDD 및 정상입구 회귀를 넘겼습니다. 일반 업무 API structured 정책·외부 기본 false·운영 활성화 보류는 유지합니다. 이 독립 보고는 자가 보고이며 부모의 정확반례 재실행과 수정 검증이 남습니다.

## 추가 수정·부모 직접 재실행

[stream 생략 4줄 수정·TDD 증거](../../../final_project_cs/wiki/records/reports/2026-10-25_reader-stream-policy-omission-tdd.md)를읽고실제guard와7개회귀를대조했습니다. 부모가동일full-manifest를원본증거와다른출력폴더reader-stream-omission-parent/20261024T151656_523123Z에서직접실행했습니다. 고유409개중405통과/4HTTPbind차단=99.022%,exit1,collection/deselect0,실행전후1297hash동일입니다. 원반례는정책wrapper에stream없으면어떤모델호출전명시거부하며일반업무structured정책은보존합니다. 전체제품GREEN/실환경활성화가아닙니다.

새child에완료된모든백엔드후속을모은단일통합회귀와관문가능범위확인을넘겼습니다. UI는별도작업중이며이백엔드선택증거의화면수용범위가아닙니다.

## 관계

- [cs 안전수정·TDD·정확한계](../../../final_project_cs/wiki/records/reports/2026-10-24_reader-provider-safety.md)
- [현재상태](../../delivery/travel-response-current.md)
- [계획API인계](../../handoff/2026-10-24_plan-reading-api-next.md)
