# F3 미해결 / 새 설계 검토 인계

- 새 격리 `remaining_non_db_f3_fix/repo`, 입력 tree `e94caecf05c9af750b45bef4bdc4e64395caaf8b`.
- 요청별 publication/dispatch claim 동기화 최소 수정은 있으나 원문 probe3개가 여전히 실패하여 **NOT_ACCEPTED**입니다.
- 단일955개 실행948통과, 원문3실패, 기존4bind정책차단. 원문15개는12통과/3실패입니다. 실패/차단은 분모에 유지했습니다.
- 실제 trace: local 정식 enqueue 완료 → settled=True인 API claim=False → cancelled enqueue → 시험 Thread.start override의 paid_called.wait3초 실패. API 대역 진입0건. 원문81행 대기와90행0회 기대의 동시 충족 문제는 새 독립 검토가 필요합니다. 시험 완화·삭제·예외 삼키기 우회는 하지 않았습니다.
- 초기 보조8/8 및 손상XML은 수락으로 채택하지 않습니다. 재시도 정상XML 경계2/2, ruff 통과, code/test hash stable.
- [상세 원인·한계·runner 실패](../records/reports/2026-10-25_remaining-non-db-f3-unresolved.md). scratch FINAL.json/REPRODUCE.md와 diagnostic-not-accepted.patch가 현재 증거입니다.
- 원본/기존 후보/DB/서비스/실모델/외부API/push/배포는 변경하지 않았습니다. DB는 라이팅 에이전트 세션 소유입니다. 부모가 다음 새 독립 설계 검토를 진행합니다.
