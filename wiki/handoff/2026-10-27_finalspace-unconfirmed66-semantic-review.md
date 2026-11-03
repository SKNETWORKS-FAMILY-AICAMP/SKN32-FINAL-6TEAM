# 이관 백업 미확인 66개 의미별 재분류 — 인계

## 현재 결론

앞 감사의 미확인 66개를 의미별로 다시 나눴다: 보존 44/66 = 66.7% · 실사용 2/66 = 3.0% · 기록 17/66 = 25.8% · 미확인 3/66 = 4.5%. final_project_cs 런타임 코드를 바꿀 것은 0개다. 정적 대조만 했고 시험 실행은 0건, 커밋·push 0건이다. [보고서](../records/reports/2026-10-27_finalspace-unconfirmed66-semantic-review.md)

## 한 일 목록

- 상태 끝: 앞 감사 근거(scratch `unmerged-audit-20261027`, pin `93c7ba8e`)로 고유 줄 의미 검토, 이름 정규화 재계산, 원본 작업트리 `_backup` 사전 사본 대조, 링크 대상·추적 상태 확인을 했다.
- 새 파일 3개: 보고서, `wiki/records/evidence/2026-10-27_finalspace-unconfirmed66-semantic/classification66.json`, 이 인계. 원본 코드·인덱스·백업·목차는 변경하지 않았다.

## 다음(통합 대상, 모두 문서·평가 기록)

1. I-2 실사용 문서 연결(#60 · #62): 관리자 사용자 목록 계약 색인 + 미추적 `admin-users.md`, UTIC 20초 설명 + 미추적 `2026-10-18_oracle-rain-traffic-diagnosis.md`. 반영하기 전에 문서를 pin 코드와 대조한다.
2. I-1 codex_percall 정정 기록(#64 · #77 · #85~#88): [격리 uuid 패치](2026-10-27_codex-percall-uuid-isolated-apply.md) 뒤에 이어서 넣는다. 원본 작업트리의 현재 결과 2파일은 `results/_backup/2026-10-16_codex_du_before_rerun/` 사본과 같은 정정 전 판이다.
3. I-3 합성 자료 표현 정정(#76 · #117 · #118).
4. I-4 기록 보충(#61 · #70 · #71 · #78 · #119~#122). 이 묶음이 pin 의 끊긴 참조 2개(2026-10-16 일정짚기 보고서, agent-prompt-passing-idea.md)도 해소한다.
5. 결정 대기: `.codex/hooks.json`(사용자), `setup_oracle_model_gpu.sh`(운영), EKS 정적 manifest(EKS 담당).
