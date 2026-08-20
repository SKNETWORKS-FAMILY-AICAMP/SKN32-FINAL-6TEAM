# DoD-17 — 마일스톤 gate 와 기능 동결·통합 규칙

- v5 §20 항목 17 / 검증 방법: release checklist
- 실행: 2026-08-12 23:20 · 실측 원문 `docs/evidence/_raw/DoD-17.md`
- 판정: 부분 통과

## ★v5 원문과 이 프로젝트의 차이 (실행계획서에 기록한 재해석)

v5 §17-3 은 **"목요일 기능 동결 / 금요일 통합·회귀"** 라는 팀 캘린더 규칙이다.
1인 + 에이전트 체제에는 요일이 의미가 없으므로 실행계획서 §1 에서 이렇게 바꿔 실행했다:

> **마일스톤 gate 통과 후에는 그 Phase 에 새 기능을 넣지 않고 P0/P1 결함 수정만 한다.**

## 재현 명령

```powershell
python -m scripts.check_release_gate
```

## 실제 출력 (커밋 이력, 최신순 발췌)

```
fix(publish)     한글 경로 quotepath 처리 + 자기 자신 제외
feat(publish)    공개 배포 검사 스크립트
feat(wire,...)   분류기 API 연결(109 passed) + DoD 증거 5건 판정
fix(controller)  resuming 에서 RESUMED 선행 발행 - 107 passed, 전이표/테스트 무단변경 0
test(controller) 통합테스트 8종 추가 - 7통과/1실패(진짜 결함 발견)
feat(controller) S-CTRL 코드 인수(정적검사 통과) - 테스트 0건이라 테스트만 재발주
feat(ui,eval)    운영화면 4개 마운트, golden60/holdout20, bootstrap/McNemar
feat(teams,voc)  두 TeamModule, 인라인분류, 일일배치. Core격리 위반 0
fix(rag)         검색 SQL ::vector 캐스트 - 78건 통과, 정답문서 1-2위
feat(rag)        코퍼스 v5 인수 - 25문서/300청크 (5회차)
feat(api)        REST5+MCP3 동작 검증(74건), 설정우회/오류응답 500 버그 수정
feat(core)       P0 부트스트랩 + P1 계약/전이표/리듀서, 테스트 53건
docs             저장소 골격 - 룰파일, DOCS 구조, 실행계획서, handoff 계약 6종
```

## 통과한 것 — 마일스톤 게이트

| 게이트 | v5 조건 | 상태 |
|---|---|---|
| **M1** | Case 생성→classifying→routing→Team, event/replay 통과 | **도달** |
| **M2** | 두 시나리오 end-to-end, 승인·outbox·MCP·RAG·UI smoke | **도달** — 시나리오1 `classifying(1)→routing(2)→running(3)→waiting_approval(4)→resuming(5)→running(6)→resolved(7)`, 시나리오2 `→resolved(4)` |
| **M3** | 60건×3회 harness, 통계 report, MCP 3 tool, RC | **도달** — 아래 |

### M3 재판정 (2026-08-14)

| v5 조건 | 결과 |
|---|---|
| 60건×3회 harness | **통과** — 3군 × 180행 = **540 관측** (DoD-15) |
| 통계 report | **통과** — paired bootstrap 10,000 + McNemar(discordant<25 시 정확검정 분기) (DoD-16) |
| ★ablation | **통과** — 5종 실행. RAG·Context Broker 제거 시 grounding 3.98→0.00 |
| MCP 3 tool | **통과** — 전부 `mcp:read`, payments/subscriptions 미접근 (DoD-13) |
| RC | **부분** — 아래 |

★**M3 는 도달했으나 "RC(릴리스 후보)" 는 아직이다.** 남은 것을 정직하게 적는다:
- ★**judge agreement (사람 라벨 20건) 미측정** — DoD-15. **이것이 유일한 차단 항목이다**
- ~~릴리스 체크리스트 문서 미작성~~ → **작성함** (`docs/release_checklist.md`, 2026-08-16)
- ~~커밋 ↔ Phase 자동 매핑 미수행~~ → **부분 자동화**(2026-08-20) —
  `scripts/check_release_gate.py` 가 pytest·`verify_dod`·기능동결(git diff)
  3단계를 한 명령으로 실행해 pass/fail exit code 를 낸다("사람이 손으로
  재현"에서 "한 명령"으로 바뀜). 다만 이건 게이트 자체의 자동화이지 커밋
  메시지↔Phase 매핑 자동화는 아니다 — 그건 여전히 사람이 읽어 대조한다.
  근거: `docs/reports/2026-08-20_S-DOD17-AUTOMATED-GATE_리포트.md`

## 통과한 것 — 통합 규칙

- 각 커밋이 **검증 결과를 메시지에 담는다**(테스트 건수·무엇이 통과/거부됐는지)
- ★**결함을 숨기지 않았다.** `test(controller) ... 7통과/1실패(진짜 결함 발견)` 처럼
  실패한 채로 커밋하고 다음 커밋에서 고쳤다
- ★**우회하지 않았다.** controller 수정 시 전이표·테스트 단언 변경 0건을
  `git diff` 로 확인하고 커밋 메시지에 적었다
- 매 merge 지점에서 `pytest tests -q` 를 돌렸고 **skipped 0** 을 유지했다

## ★미통과 — 왜 "부분"인가

| 항목 | 상태 |
|---|---|
| M1 · M2 · **M3** 게이트 | **도달** |
| 커밋 이력에 검증 근거 기록 | **통과** |
| 릴리스 체크리스트 | **통과** — `docs/release_checklist.md` (2026-08-16) |
| ★**RC(릴리스 후보) 선언** | **미도달** — judge agreement 미측정 **한 건**이 남았다 |
| 각 커밋 ↔ Phase 자동 매핑 | 미수행 — 사람이 읽어 대조해야 한다 |

★**세 게이트가 모두 도달했지만 이 항목은 여전히 부분 통과다.**
v5 가 M3 에 "RC" 를 함께 적어 두었고, RC 는 **"돌아가는 것"이 아니라 "내보낼 수 있는 것"** 을 뜻한다.
judge 가 사람과 얼마나 맞는지 모르는 상태에서 평가 수치를 근거로 내보낼 수 없다
(`CLAUDE.md` §0.1 — 근거를 못 대면 확정 답변을 만들지 않는다).

**게이트 도달 = 완료가 아니다.** 남은 두 줄을 채우면 통과로 바꾼다.
