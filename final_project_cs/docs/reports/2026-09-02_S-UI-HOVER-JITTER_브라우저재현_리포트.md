# S-UI-HOVER-JITTER — 브라우저로 실제 재현 시도 (2026-09-02)

선행 리포트: [`2026-08-20_S-UI-HOVER-JITTER_리포트.md`](2026-08-20_S-UI-HOVER-JITTER_리포트.md)
— 그때는 **브라우저 제어가 없어 재현 자체를 못 했고**, 추측으로 고치지 않고 남겼다.
이번 세션은 브라우저 제어가 있어서 그 조건이 풀렸다.

## 판정

**현재 코드에서 hover 로 인한 레이아웃 이동은 없다.** 두 방향으로 확인했다 —
CSS 규칙 전수 조사(구조적 증명)와 실제 마우스 hover 후 좌표 측정(실측). 둘 다
"이동 0"으로 일치한다.

★**"재현 못 했다"와 "없다"는 다르다.** 아래는 *레이아웃이 튀는* 현상에 대한
판정이다. 원 증상 서술("마우스 오버 하이라이트가 튄다")이 레이아웃이 아니라
색·깜빡임을 뜻했다면 이 측정이 그것까지 배제하지는 않는다. 다만 그 경우에도
아래 §3 의 CSS 전수 목록이 후보를 6개로 좁힌다.

## 1. CSS 전수 조사 — hover 규칙은 정확히 6개다

페이지에 실린 `<style>` 전체(12,455자)를 파싱해 `:hover` 를 포함하는 규칙을
전부 뽑았다.

```
nav a:hover{background:var(--surface);color:var(--text)}
.card__head--fold:hover h2{color:var(--accent)}
tbody tr:hover{background:var(--surface-2)}
button:hover:not(:disabled){background:var(--accent-strong)}
button.ghost:hover:not(:disabled){background:var(--critical-bg)}
.stage__head:hover .stage__title{color:var(--accent)}
```

여섯 규칙이 바꾸는 속성은 **`background` 와 `color` 뿐이다.** 둘 다 레이아웃에
영향을 주지 않는 순수 페인트 속성이다. `padding`·`border`·`width`·`height`·
`transform`·`filter`·`font-*` 를 바꾸는 hover 규칙은 **하나도 없다.**

## 2. 실측 — 진짜 마우스를 올리고 좌표를 쟀다

`getBoundingClientRect()` 로 hover 전후를 비교했다. `:hover` 는 스크립트로
만들 수 없으므로 실제 포인터를 움직였고, `element.matches(':hover')` 로 hover
가 실제로 걸렸는지 함께 확인했다(측정이 헛돌지 않았다는 증거).

| 화면 | 대상 | hover 확인 | 좌표 변화 |
|---|---|---|---|
| `/ui/cases` | 표 행 1 (`tbody tr`) | `hovered: -1 → 0` | 행 2개·표·문서 크기 **전부 동일** |
| `/ui/approvals` | nav "Cases" | `hoveredNav: 0` | 추적 12개 요소 **변화 0건** |
| `/ui/approvals` | nav "VOC" | `hoveredNav: 2` | 추적 12개 요소 **변화 0건** |

`/ui/cases` 표 행의 실제 값(hover 전 = 후):

```
rows  [[91, 364.2, 1236.14, 64.84], [91, 429.05, 1236.14, 64.34]]
table [91, 326.41, 1236.14, 166.98]
docW 1280 · docH 720 · scrollY 0
```

## 3. 원인으로 보이는 것 — 이미 고쳐져 있었다

`app/presentation/ui/theme.py` 의 hover 규칙 옆에 이런 주석이 있다.

> ★`filter` 대신 색을 직접 바꾼다. `filter` 는 hover 동안만 containing block 을
> 만들어 자식의 배치 기준을 바꾼다 — 지금은 자식이 없어 안전하지만 같은 부류의
> 원인이다.

**이것이 정확히 jitter 의 메커니즘이다.** `filter` 가 걸린 요소는 그 순간
자손 `position:absolute/fixed` 의 기준 상자가 되므로, hover 가 켜지고 꺼질 때
자손이 튄다. 즉 원인으로 지목될 만한 코드는 **이미 색 변경으로 대체돼 있었고**,
체크리스트만 갱신되지 않은 채 남아 있었다.

★단 이 주석이 언제 들어왔는지는 **확인할 수 없었다.** 이 저장소의 git 이력이
초기 단일 커밋(`0062211`)으로 스쿼시돼 있어 `git log -S` 가 그 커밋 하나만
가리킨다. "언제 고쳤는지"는 근거가 없으므로 적지 않는다.

## 4. 오진했다가 바로잡은 것 (다음 사람이 되풀이하지 않도록)

처음에 `getComputedStyle(tr).transition` 이 `"all"` 로 나와 **"`transition: all`
이 걸려 있다 = jitter 의 전형적 원인"** 이라고 판단했다. 틀렸다.

`transition` 의 축약 계산값은 `transition-property` 의 **초기값이 `all`** 이라
아무 transition 을 선언하지 않아도 `"all"` 로 보인다. `transition-duration` 이
`0s` 라 실제로는 아무것도 애니메이션되지 않는다. CSS 원문을 뒤져 `transition`
선언이 **0건**임을 확인하고 철회했다.

## 5. 못 한 것

- **스크린샷 없음.** 이 세션의 브라우저 pane 이 화면에 표시되지 않아
  (`Screenshot timed out: the Browser pane is not displayed`) 캡처가 불가능했다.
  텍스트 실측(좌표·CSS 원문)으로 대체했다 — jitter 판정에는 좌표 비교가 눈으로
  보는 것보다 오히려 정밀하지만, "화면이 이렇게 보인다"는 증거는 여전히 없다.
- `.card__head--fold` 와 `.stage__head` 는 현재 데이터로 렌더되는 화면이 없어
  실측하지 못했다(두 규칙 다 자손의 `color` 만 바꾸므로 레이아웃 영향은 구조적으로
  불가능하다 — §1 로 갈음한다).

## 6. 조치

`docs/release_checklist.md` §5-3 의 hover 항목을 **미해결에서 해소로 옮긴다.**
근거는 이 리포트다. 코드는 바꾸지 않았다 — 바꿀 것이 없었다.
