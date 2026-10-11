# DoD-17 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
git log --oneline
```

## 실제 출력
```
4c1e04a feat(dod): verify_dod 검증도구 인수 - evidence 6/18 정직 보고. DoD-06 낡은 판정줄 정정
85c373d docs: M2 게이트 도달 - DoD 02/03/12 증거 기록, 상태표 갱신
cbb75e6 fix(controller): resuming 에서 RESUMED 선행 발행 - 107 passed, 전이표/테스트 무단변경 0
331cd8b test(controller): 통합테스트 8종 추가 - 7통과/1실패(resuming->completed 진짜 결함 발견). 전체 106 passed
c7426e6 feat(controller): S-CTRL 코드 인수(정적검사 통과) - 테스트 0건이라 테스트만 재발주
57f921f feat(ui,eval): S-UI+S-EVAL 인수 - 운영화면 4개 마운트, golden60/holdout20, bootstrap/McNemar. 테스트 99+3건
5455d01 feat(teams,voc): S-TEAM+S-VOC 인수 - 두 TeamModule, 인라인분류, 일일배치. 테스트 96건, Core격리 위반 0
c986ad6 fix(rag): 검색 SQL 에 ::vector 캐스트 - 테스트 78건 전부 통과(skip 0), 시나리오 질의가 정답 문서를 1-2위로 검색
ced4cc6 fix(rag): 적재 실행(25문서/300청크/1536d) + 검색 100% 실패 결함 발견, 수정 발주
4d0fc27 feat(rag): 코퍼스 v5 인수 - 25문서/300청크, 청크 평균 241자, 중앙 유사도 0.002 (5회차)
6c620d6 feat(api): S-API 인수 - REST5+MCP3 동작 검증(테스트 74건), 설정우회/오류응답 500 버그 수정. 코퍼스 게이트에 길이검사 추가
091dde6 fix(gate): check_corpus 에 지표 우회 탐지 추가 - v3 무작위토큰 주입 거부, v2 복원 후 v4 발주
f6e217c feat(context,rag): Context Broker 구현 + S-DB seed 인수 + check_corpus 게이트 구멍 수정(전역 유사도 검사)
b0a03c0 feat(db,rag): S-DB 스키마 인수 + S-RAG 1차 인수거부(보일러플레이트) - check_corpus 게이트 신설, 재작업 발주
1e73241 feat(core): P0 부트스트랩 + P1 계약/전이표/리듀서 - contracts.py, events.py, case.py, transition.py, 테스트 53건
8b13fff docs: A-COP 저장소 골격 - RULE/CLAUDE 룰파일, DOCS 구조, 실행계획서, handoff 계약 6종
```

## 관측 사실
- `git log --oneline` 출력은 17개 커밋 행이다.
- 최신 커밋 해시는 `4c1e04a`이다.
- 로그 메시지에 `feat(ui,eval)`, `feat(teams,voc)`, `feat(api)`, `feat(context,rag)`, `feat(db,rag)`, `feat(core)`가 포함되어 있다.

## 확인하지 못한 것
- 각 커밋과 별도 Phase 문서의 자동 매핑 결과는 확인하지 못했다.
