# B/C/D/E 현재 결과와 사용자 E 명칭 연결 — 2026-10-08

사용자의E 설명(평문 자유질의 속 실제 여행 관련 요청)은MX 설계 원문과 일치한다. 파일명을 바꾸거나 새로운 시험을 중복 실행하지 않고 같은 결과를 연결했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| B/C 기본·집합 출력 재계수 | 완료 | 16/16 = 100% |
| D/E 완료 원본 재계수 | 완료 | 9/9 = 100% |

[전체 현재 결과표](../../../../program/scripts/plan_qa_bench/results/bcde_results_2026-10-08_115323.md) · [실행 원본 경로·해시·구조화 계수](../../../../program/scripts/plan_qa_bench/results/bcde_results_2026-10-08_115323.json).

B와C는 동일835문항의 채점 방식으로 각각 하나라도 맞힘과 정답 집합 전체 일치를 센다. 한 번호만 출력한 판은 두 요청 C에서0/66이다. D 단일 선택은 복합66개를 제외한2669개이며 실패를 남긴다. E 입력4014개는 혼합2007개·대조2007개로, 자연 혼합239개와 코드 이어 붙임1768개를 분리해 해석한다. 자연 혼합만 잘 나온 결과를 전체 개선으로 채택하지 않는다. 모델이 생성한 자연 문장이지 실제 사용자 자유 대화 검증은 아니다.

우리 학습판 B/C 기본HF 평가와 D/E 서비스 기반GGUF 평가는 실행 경로가 다르므로 같은 경로 지연·엔진 속도 비교가 아니다. 출제자 계열·출력 계약·시드와 추가 학습 여부를 구분했다. 별도 원본 Gemma12B E는 관측2459/4014개 저장·진행 중이므로 최종 점수에 넣지 않았다. MAI 지정D3 결과를 D전체나E로 옮기지 않았다. 현재 표는 모든 과거 모델·역할 완료 행렬이 아니며 기존 개발·회귀 자료와 새 독립 보류 자료를 구분한다.

입력 ID·정답·유형·전체 분모·실패를 원본에서 직접 대조했고 모델별835/2735/4014 입력 크기를 확인했다. 자료와 답안 해시를 구조화 결과에 저장했다. 새 모델 호출은0회, 기존 완료 결과 덮어쓰기는0회다. 관련 wiki와일일 기록의 수정 직전 판:

- [final_project_cs/wiki/quality/_backup/2026-10-08_115421_bcde_result_reference/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_115421_bcde_result_reference/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_115421_bcde_result_reference/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_115421_bcde_result_reference/log.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_115421_bcde_result_reference/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_115421_bcde_result_reference/2026-10-08.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_115421_bcde_result_reference/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_115421_bcde_result_reference/2026-10-08.json)
