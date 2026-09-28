# 구현 지시 — 운영 UI 품질 (Codex)

## 0. 왜 다시 하나

기존 `/ui/*` 4화면은 **기능은 맞는데 품질 요구가 발주 조건에 없었다.**
지시서에 "evidence 를 함께 표시할 것 / 승인은 API 경유 / HTTP 200" 만 적었고
디자인 요구를 한 줄도 안 적었다. 그래서 `_page()` 안에 인라인 CSS 한 덩어리가 전부고,
guardrails·case status·outbox 를 **JSON 그대로 `<pre>` 에 쏟아붓는다.**

Claude 가 `app/presentation/ui/theme.py`(디자인 토큰 + 컴포넌트)를 만들고
`routes.py` 를 그 위로 옮겼다. **네 일은 그 결과를 검증하고 빈 곳을 채우는 것이다.**

현재 기준선: **158 passed, 0 failed, skipped 0**.

## 1. 소유 범위

```
app/presentation/ui/**        ← theme.py / routes.py / composer
tests/e2e/**  tests/integration/api/**
wiki/records/reports/
```
★금지: `app/core/**`, `app/domain/**`, `app/application/**`, `app/infrastructure/**`,
`app/presentation/api/**`, `app/composition.py`, `config/**`, `eval/**`, `knowledge/**`,
`scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`.

## 2. 이 화면이 지켜야 하는 것 (장식이 아니라 안전 요구다)

이건 **틀린 정보가 고객 돈을 건드리는 시스템**의 운영 콘솔이다.

1. ★**사람이 손대야 하는 상태가 눈에 띈다** — `waiting_approval` 은 경고색,
   `escalated`·`unknown`·`dead_letter` 는 위험색. **`unknown` 이 가장 세다**
   (돈이 나갔는지 모르는 상태다)
2. ★**근거 없음이 조용하지 않다** — 근거 없는 제안은 승인 버튼이 잠기고
   **왜 잠겼는지 화면이 말한다.** 이유를 안 적으면 운영자가 UI 결함으로 오해한다
   (2026-08-14 에 실제로 그렇게 오해했다)
3. ★**degraded 를 숨기지 않는다** — ContextPack 이 축소됐으면 Case 상세 상단에 뜬다
4. ★**빈 값을 0 으로 지어내지 않는다** — 분류 실패는 빈칸이 아니라 "미분류"

## 3. 할 일

### 3-1. 검증 (먼저)
`python -m pytest tests -q` 가 **158건 이상 통과**하는지 확인하라.
깨지면 고쳐라. ★`pytest.skip` 금지.

### 3-2. 실제로 띄워서 4화면 + composer 를 본다
```powershell
python -m uvicorn app.presentation.api.app:app --port 8055
```
`/ui/cases` `/ui/cases/{id}` `/ui/cases/{id}/trace` `/ui/approvals` `/ui/voc` `/ui/admin`
★HTTP 200 만 보지 마라. **본문에 무엇이 렌더링됐는지** 확인하고 리포트에 원문을 붙여라.
(이 프로젝트에서 "4화면 200" 을 통과시키고도 화면이 비어 있던 적이 있다)

### 3-3. 빠진 것을 채운다
- ★**VOC 화면이 아직 JSON 덤프다.** `intent/issue count` 를 표로,
  급증 alert 을 **눈에 띄는 카드**로 바꿔라. alert 이 없으면 "없음"을 정직하게 적어라
- ★**Composer 화면**이 새 디자인을 안 쓴다. `theme.page()` 로 옮겨라
- 반응형 확인 — 폭 375px 에서 표가 페이지를 가로로 밀지 않아야 한다
  (`.scroll-x` 안에서만 스크롤)
- 다크 모드 확인 — `prefers-color-scheme: dark` 에서 대비가 죽지 않아야 한다

### 3-4. 회귀 방지 테스트
`tests/e2e/` 에 추가하라. **화면이 무너지면 실패해야 한다:**
- `waiting_approval` Case 가 목록에서 경고 상태로 렌더링된다
- 근거 없는 제안은 승인 버튼이 `disabled` 이고 **잠긴 이유 문구가 함께 뜬다**
- `degraded` Case 상세에 경고 배너가 뜬다
- admin 이 실제 API key 를 노출하지 않는다 (기존 검사 유지)

## 4. 깨면 안 되는 문자열 (기존 테스트가 건다)

```
/ui/cases        "post_cancel_charge"
/ui/cases/{id}   "masked answer" 포함 · ★"policy" 는 들어가면 안 된다
/ui/.../trace    "append-only" · "v1" · "approval_required"
                 ★index("v1") < index("approval_required")
/ui/approvals    "rationale evidence" · "근거 없음" · "policy claim"
                 "name='decision' value='approved' disabled"
/ui/voc          "리포트 없음"
/ui/admin        "12000" · "sk-****" · team_id 들
승인 실패 화면    "승인이 처리되지 않았습니다"
```

## 5. 완료 조건

```powershell
python -m pytest tests -q
```
**158건 이상, 0 failed, skipped 0.**

## 6. 리포트

`wiki/records/reports/2026-08-14_S-UI-QUALITY_리포트.md`
— §3-2 렌더링 원문, 채운 것, 추가한 테스트, 발견한 결함.

## 7. 하지 말 것
- ❌ HTTP 200 만 보고 "확인함"
- ❌ 잠긴 버튼의 이유를 안 적기
- ❌ degraded·근거 없음을 조용히 넘기기
- ❌ 빈 값을 0 이나 "정상" 으로 지어내기
- ❌ 소유 범위 밖 수정
- ❌ 기존 테스트 단언을 고쳐서 통과시키기 (화면을 고쳐라)
