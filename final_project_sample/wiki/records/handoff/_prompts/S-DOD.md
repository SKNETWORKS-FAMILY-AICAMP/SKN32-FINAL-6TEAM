# Codex — `scripts/verify_dod.py` (DoD 전수 검사 도구)

## 0. 목적

v5 §20 의 **DoD 18항목**이 (a) `wiki/records/evidence/` 근거 파일과 (b) 관련 테스트 통과를
**함께** 만족하는지 한 번에 검사한다.

★`RULE.md` §4.0 — **evidence 없는 DoD 체크는 미통과로 센다.**
"테스트가 초록이니 통과"가 아니라 "재현 명령과 실제 출력이 남아 있어야 통과"다.

## 1. 소유 범위

```
scripts/verify_dod.py
wiki/records/reports/ , wiki/records/history/
```

★그 밖 **전부 금지**. 특히 `wiki/records/evidence/` 의 기존 파일을 **만들거나 고치지 마라** —
증거는 Claude 가 판정해서 쓴다. 당신은 **있는지 검사만** 한다.

## 2. DoD 18항목 (v5 §20 등장 순서)

| # | 항목 | evidence 파일 접두사 |
|---:|---|---|
| 1 | 원본 v4 파일 hash 불변 | `DoD-01` |
| 2 | Case 상태가 상태표+transition 규약으로만 변경 | `DoD-02` |
| 3 | optimistic concurrency · append-only · replay | `DoD-03` |
| 4 | LangGraph checkpoint 와 업무 projection 분리 | `DoD-04` |
| 5 | ContextPack ≤ 12,000 token + omissions | `DoD-05` |
| 6 | 정책/FAQ 25건, 300~400 chunk 적재 | `DoD-06` |
| 7 | tenant/customer scope + PII redaction | `DoD-07` |
| 8 | Billing/Technical 이 TeamModule·manifest 호환 | `DoD-08` |
| 9 | 인라인 분류가 모든 Case 생성에서 실행 | `DoD-09` |
| 10 | 일일 배치가 count·ratio·급증 report 생성 | `DoD-10` |
| 11 | action proposal·approval·idempotency·unknown | `DoD-11` |
| 12 | outbox 원자성 + worker replay | `DoD-12` |
| 13 | REST 5 + MCP 3 이 문서·contract 와 일치 | `DoD-13` |
| 14 | API key scope 가 read/write/MCP 구분 | `DoD-14` |
| 15 | A/B/Proposed 60건×3회 + holdout 20 보존 | `DoD-15` |
| 16 | bootstrap CI · McNemar · **한계 서술** | `DoD-16` |
| 17 | 마일스톤 gate · 기능 동결 규칙 준수 | `DoD-17` |
| 18 | Case UI·trace·approval·VOC 가 시나리오를 끝까지 | `DoD-18` |

## 3. 검사 내용

각 항목마다:

1. **evidence 존재** — `wiki/records/evidence/DoD-NN_*.md` 파일이 있는가
2. **evidence 품질** — 파일 안에 다음이 **전부** 있는가 (없으면 미통과):
   - 재현 명령 (코드 블록)
   - "실제 출력" 또는 그에 준하는 실측 결과 블록
   - **판정** 줄 (`판정: 통과` / `부분 통과` / `미통과`)
   ★`판정: 통과` 가 아니면 그 항목은 **통과로 세지 않는다**
3. **테스트** — 아래를 실행하고 결과를 함께 보고
   ```
   python -m pytest tests -q
   ```
   ★**skipped 가 1건이라도 있으면 경고**로 표시하라 (skip 은 통과가 아니다 —
   실제로 `74 passed, 4 skipped` 가 결함을 감춘 적이 있다)

## 4. 출력 형식

```
================================================================
A-COP DoD 검증  (v5 §20 · 18항목)
================================================================
 #  항목                                    evidence   판정      결과
 1  원본 v4 hash 불변                        있음       통과      OK
 2  상태전이 규약                             있음       통과      OK
 4  checkpoint 분리                          없음       -         MISSING
...
----------------------------------------------------------------
 evidence 있음 12/18 · 통과 10 · 부분통과 2 · 미작성 6
 테스트: 107 passed, 0 skipped, 0 failed
----------------------------------------------------------------
 ★미작성 6항목: DoD-04, DoD-05, DoD-07, ...
```

- exit code: 전 항목 `판정: 통과` 이고 테스트 실패 0 이면 **0**, 아니면 **1**
- ★**진행 상황을 부풀리지 마라.** evidence 가 없으면 `MISSING` 이지 `OK` 가 아니다

## 5. 완료 조건

```powershell
python -m scripts.verify_dod
python -m pytest tests -q
```

★`verify_dod` 를 **실제로 돌려 출력 전문을 리포트에 붙여라.**
지금 evidence 는 일부만 있으므로 **미통과가 나오는 것이 정상**이다.
전부 OK 로 나오면 그게 오히려 버그다.

## 6. 리포트

`wiki/records/reports/2026-08-12_S-DOD_검증도구_리포트.md` — §5 **실제 출력 원문**,
현재 몇 항목이 evidence 를 갖고 있는지, 어떤 항목이 비어 있는지.
`wiki/records/history/2026-08-12_S-DOD.md` 이력 추가.

## 7. 하지 말 것

- ❌ `wiki/records/evidence/` 파일 생성·수정 (검사만 한다)
- ❌ 없는 evidence 를 있는 것처럼 세기
- ❌ 테스트 skip 을 통과로 세기
- ❌ 소유 범위 밖 수정
- ❌ 돌려보지 않고 "동작함"
