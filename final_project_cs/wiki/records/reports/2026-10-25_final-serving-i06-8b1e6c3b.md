# I06 최종 동결 실검증 — 양성 통과, booked-only 잔여로 서빙 보류

정본 증거: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/final-serving-i06-20261025-203428-8b1e6c3b/REPORT_KO.md` 및 `FINAL_ACCEPTANCE.json`.

| 실제 수락 | 결과 |
|---|---|
| 정상 API E4B→claim→assemble→review→GET 명시고정 | 두 비교DB 새 고유 tenant 2/2=100% |
| 고정하지마 정상 control | 1/1=100% |
| 예약만 control | **0/1=0%**, `예약 완료`가 잘못된 locked_quote로 저장됨 |
| 유효 terminal 4사례 | 3/4=75%; 최초 cold timeout 1별도 |
| 최종 exact union | 2174/2184=99.54%, 기존 baseline동일8fail/2skip |
| F02 / hours / Opus I06 / 추가 계약 / date_generation | 1389/1389 · 180/180 · 9/9 · 9/9 · 12/12 |
| full serving assembly preflight | RC0, metadata 실제/추론0/listen0 |

일반 등록은 고객승인이 별도이므로 실행하지 않았습니다. 장소좌표 없음/unknown risk도 보존합니다. review 성공을 등록·여행 생성 성공으로 부르지 않습니다.

실JUnit: `union-final.xml`, `final-baseline-nine.xml`, `contract-red.xml`, `real-I06-junit.xml`. 실제 저장원문 증거: `real-runs/*/private/I06-stored-source-proof.json`에 DB 원문·llm_agent lock claim·stored review·정상 GET을 함께 보존했습니다. 각 run complete/source-posthash와 모델 safe ledger도 존재합니다. 예시 로그만으로 수락하지 않았습니다.

SYSTEM 예시에 locked/locked_quote null을 정합시키고 inline reader `intake.agent_read.v2-explicit-lock`/template SHA/렌더된 prompt SHA가 reading.agent로 저장되는 것을 실검증했습니다. 파일기반 tool prompt DB allowlist를 임의로 늘리거나 미등록 fallback을 넣지 않았습니다. donor reader date preimage7cb1e402… 보존.

최종 app closure `3cca7a179bc773f61eaebdbd05026c3abf4393cb2b951eb96a0729686f2b42a6`; 전체source5197파일 동결 후 제품/시험/source문서 편집0. evidence-only runner는 날짜 nullable fixture 및 app/eval source 결속을 바로잡았고 원 실패를 보존했습니다. live-v7 source4894파일 SHA 불변. `PARENT_SWAP.json`은 **HOLD_DO_NOT_SWAP**. allpast4f67652c 작업트리/commit에 병합0, 고객DB변경0, 고객27107a20 rev2 revalidate0, push/runtime교체/restart/kill0.

추가 hunk 없이 반환합니다. booked-only 의미보호는 부모가 긴급 Git 배포 후 새 후보/새 budget에서 해결·재검증해야 합니다.
