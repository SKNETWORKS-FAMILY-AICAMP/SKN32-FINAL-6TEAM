# 옮김 (2026-10-16)

769 세트(mix8~12.json)와 A~C 채점 정답(gold_sets.json)은 저장소 루트 기준 `datasets/core/pointing/testset/itinerary_questions_v1/` 로 옮겼다 — [새 자리](../../../../datasets/core/pointing/).
일정 항목 짚기 시험 · 학습 세트를 `datasets/core/pointing/{testset,trainset}/` 한곳에서 관리한다. 위치 목록: `program/scripts/plan_qa_bench/TESTSETS.md`.

스크립트는 `testsets.py` 의 `fixture(이름)` 으로 읽는다. 이 폴더의 나머지 파일은 그대로다.
