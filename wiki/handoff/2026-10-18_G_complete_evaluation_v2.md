# G 전체 평가 v2 인계

2026-10-18 03:45 KST 실제 연결·독립 재확인 완료. 현재 Winnow 학습과 E4B Optuna 선행 학습 정의는 그대로다. 기존 대기 평가 두 건만 새 평가 진입점으로 바꿨고 다른 52개·순서를 보존했다. 예약·heartbeat·cron·새 실행기를 만들거나 다시 활성화하지 않는다.

한 일: E3 646·A 단일 835·B/C 복수 835 동결, D/D3 원래 전체 분모 유지, E2 요청 P/R/F1·개수/가족별 성공, E3 위험 오류·분류 F1·형식/누락 포함 지표 구현. 모델당 총 16,859회이며 중복 관계를 독립 합산하지 않는다. CPU14/14, 참조 재생과 빈 응답 각각 16,859/16,859, A4000 CPU 토큰33,718/33,718, 원본 출처17/17 지문 유지. 현재 학습 PID 유지·평가 진입점2/2·보호52/52 재확인.

남은 일: 기존 작업 흐름에서 두 학습 성공 후 실제 평가. 새 모델 성적0/2, 현재 표의 최신 완료판 E2 F1은 G 이전 판이다. E2 467개 전체는 AI 교차 검토이며 사람 검수로 쓰지 않는다. Claude/Codex의 C66 성적과 E2 설계 검토를 응시 성적으로 혼동하지 않는다.

완료 파일: 두 기존 평가 작업 폴더의 scores_complete_v2_G.json·result_summary_complete_v2_G.json, 두 번째 평가 폴더의 comparison_complete_v2_G.json/md. 기존 collect_results_G.py 대신 v2 수동 회수 도구를 쓴다. 새 예약을 만들지 않는다. 실패/부분 출력·기존 데이터·모델·준비본을 지우거나 덮어쓰지 않는다.

[전체 결과와 범위](C:/Users/playdata2/Documents/final_workspace/wiki/records/reports/2026-10-18_G_complete_evaluation_and_historical_metrics.md) · [실제 연결된 준비본](C:/Users/playdata2/Documents/final_workspace/datasets/core/travel_tasks/20261017_audited_G/evaluation_after_both_v2_G/README_G.md)
