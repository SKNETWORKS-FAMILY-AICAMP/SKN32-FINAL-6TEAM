# 모델 비교 결과 내보내기

자동 생성 파일이다(`eval_final_all.py --sets ... --matrix <md> --export <폴더>`). 손으로 고치지 않는다.

- 이 파일은 eval_final_all.py --export 가 만든다(손으로 고치지 않는다).
- 생성 2026-10-04T20:38:49 · 세트 heavy, mix4, mix5, mix6, mix7, mix8, mix9, mix10, mix11, mix12
- ※ fair_comparison=False 인 행(Claude Opus 5.5 · Fable 5.1 · Codex 루나)은 세트 묶음 풀이 + 생각 설정 통제 불가라 로컬과 공정한 비교가 아니다. 천장 참고용이다.
- 로컬 모델·조합: 문제 하나씩 · 생각 끔 · 온도 0 · 번호만 JSON.
- 개발 5세트(heavy·mix4~7)의 조합 값은 문턱·τ 를 고른 세트라 낙관적이다. 판정은 시험 세트(mix8 이후)로 한다.
- set_author: mix8~mix11 은 Codex(gpt-6-sol), mix12 는 Claude 가 썼다(§61). mix4·5·heavy 는 [미확인].
- per_question: pick 은 고른 일정 번호(없으면 빈 칸=null), gold 는 정답 번호(없으면 빈 칸=정답 없음), wrong_non_null=엉뚱한 번호를 댄 경우.

| 파일 | 내용 |
|---|---|
| per_question.csv | 모델·구성 × 세트 × 문제 한 줄(정답·고른 번호·맞음 여부·공정 비교 여부) |
| summary_model_set.csv | 모델 × 세트 정답 수·정확도 |
| models.csv | 모델 정보(크기·서버·질문당 시간·공정 비교 여부·주의) |
| results_all.json | 위 전부를 한 파일로 |
| results_all.xlsx | 엑셀(요약·긴 형식·모델 정보·문제별 결과 시트) |
