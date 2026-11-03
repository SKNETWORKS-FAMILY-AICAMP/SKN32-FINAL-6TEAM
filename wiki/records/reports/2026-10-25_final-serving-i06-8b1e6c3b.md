# 독립 서빙 후보 I06 통합 — 교체 보류

명시 고정 I06 실모델 2/2=100%(두 비교DB 새 tenant), 고정하지마 1/1=100%. **booked-only 0/1=0%**: 모델이 `예약 완료` 인용으로 locked=true를 내고 실제 claim/review/GET에도 true가 저장됐습니다. 성공으로 덮지 않았으며 `PARENT_SWAP.json`은 HOLD_DO_NOT_SWAP입니다. 최초 cold first-token timeout 1건도 별도 보존했습니다. 총 실제 dispatch 5/8, lease 반환.

최종 exact 합집합 단일실행 2174/2184=99.54%, 8fail/2skip. F02 1389/1389, Comment9 180/180, Opus I06 9/9, 추가 계약 9/9, date_generation 12/12. 기존9-node의 정본 baseline 재현은 8fail/1pass이며 최종 8fail nodeid와 동일합니다. 중간 donor eval namespace 오염 성공은 버렸고 최종은 모든 app/eval 파일을 동결 candidate에 결속했습니다. 날짜 fixture는 새 nullable lock 슬롯만 외부 runner에서 보충; 제품 schema/원 assertion/guards 불변.

baseline f02-origin-20261025-201456-5daacb에 donor 5파일 pre/fullpostimage SHA 대조 통합. source5197파일 동결, 실모델 후 source편집0. 최종 app closure `3cca7a179bc773f61eaebdbd05026c3abf4393cb2b951eb96a0729686f2b42a6`. full serving --shadow --preflight RC0(metadata 실제, inference0/listen0/shared DB readonly). live-v7 source4894파일 SHA 불변, 8042 listener PID27184 유지. push/restart/kill/runtime교체/실고객변경0. 별도 allpast 4f67652c 작업트리/commit 병합0.

실제 전체 증거·보고서: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/final-serving-i06-20261025-203428-8b1e6c3b/`
- `REPORT_KO.md`, `FINAL_ACCEPTANCE.json`, `UNION_ACCOUNTING.json`
- **실JUnit** `union-final.xml`, `final-baseline-nine.xml`, `real-I06-junit.xml`
- **실API 저장원문/claim/review/GET** `real-runs/*/private/I06-stored-source-proof.json` (private 원자료를 공개 문서에 복사하지 않음)
- `FINAL_POST_ACCEPTANCE_SOURCE_PROOF.json`, `SERVING_PREFLIGHT_ACCEPTANCE.json`, `PARENT_SWAP.json`, `product-exact.patch`, `PATCH_ROUNDTRIP.json`

부모는 긴급 allpast Git 배포와 섞지 말고 booked-only 의미보호를 새 unique candidate/새 lease에서 수락한 뒤 서빙 delta를 조율해야 합니다. 이 frozen 후보를 수정하거나 교체하지 않습니다. Comment9 고객27107a20 rev2 revalidate 미실행·별도 승인 유지.
