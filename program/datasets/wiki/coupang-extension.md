---
type: reference
title: 쿠팡 확장 — 지금 구조와 버린 구조
description: 목록은 __NEXT_DATA__, 상세·배송은 같은 탭의 문서 이동. DOM 클릭 방식은 근본 원인 8개를 남기고 폐기됐다
status: draft
tags: [data, testing]
owners: [human:미배정]
---

# 쿠팡 확장 — 지금 구조와 버린 구조

`[실측]` `datasets/commerce/coupang_order_history/REPORT.md`(확장 5.4.1 · 2026-08-21) · `scripts/extension/README.md` · `docs/작업기록.md` · `docs/재작성_계획.md` · `docs/클릭_구현_계획.md` · `scripts/legacy/README.md`. **원본은 그대로 있다.** 화면 관측은 [scraper-notes.md](scraper-notes.md), 배포본 규칙은 [distribution.md](distribution.md).

## 왜 확장인가 — Playwright는 전부 막혔다

| 시도 | 결과 |
|---|---|
| 전용 프로필로 로그인 창 열기 (`save_session.py`) | Access Denied — Akamai 봇 차단 |
| 기존 Chrome 프로필 재사용 (`open_with_real_profile.py`) | "자동화 제어 중" 표시, 차단 |
| 로그인 페이지 직접 접근 · QR 로그인 | 같은 지점에서 차단 |

**Playwright가 띄운 브라우저는 어떤 프로필을 쓰든 자동화로 식별된다.** 그 표시를 지우는 건 탐지 우회라 하지 않는다. 확장은 사용자의 실제 Chrome 안에서 확장 API로 도니 이 차단과 무관하다. 로그인·인증은 자동화하지 않고, 브라우저 식별 정보를 바꾸지 않고, 결과를 외부로 보내지 않는다.

## 지금 구조 — 목록은 JSON, 상세·배송은 문서 이동

`[실측]` 5.4.1. 두 단계로 나뉜다.

```
① 목록:  __NEXT_DATA__.props.pageProps.domains.desktopOrder.orderList
         + orderPagination 좌표를 따라 끝까지 저장 (체크포인트)
② 보강:  같은 로그인 탭을  주문상세 → 배송조회 → 다음 주문상세  로 이동
         주문마다 목록으로 돌아가지 않는다
```

**상세·배송을 `fetch`나 보조 탭으로 읽지 않는다.** 쿠팡이 정상 문서 탐색이 아닌 요청을 **HTTP 406**으로 거부했고, 재사용 보조 탭은 이전 DOM을 새 주문으로 읽는 경합을 만들어 한 건 뒤 정체됐다.

| 구성요소 | 책임 |
|---|---|
| `background.js` | 체크포인트(`chrome.storage.local`의 `coupangJob`), 문서 이동 발행, 탭 로드·알람 재개, 중단 세대 |
| `content.js` | `__NEXT_DATA__` 파싱, 상세·배송 문서 **검증**과 파싱, 다음 상태 결정 |
| `popup.js` | UI와 내려받기만. **닫아도 수집이 이어진다** |

서비스 워커는 영구 `while`·keepalive로 붙잡지 않는다. 한 묶음의 상태 전이만 하고 반환하며, 유휴 종료돼도 탭 로드 이벤트와 주기 알람이 저장된 작업을 다시 깨운다. 런타임이 내는 행동은 **`none` · `navigate` · `done` 셋뿐**이다.

### 정확성 장치

| 장치 | 왜 |
|---|---|
| 중복은 DOM 해시가 아니라 **JSON 주문 키 + 서버 페이지 좌표** | 카드 해시는 hydration 시점에 따라 달랐다 |
| 상세는 정확한 `/ssr/desktop/order/{orderId}` **와 페이지 안 주문번호**를 함께 검증 | 보조 탭 시절 이전 문서를 성공으로 읽었다 |
| 배송은 `orderId`·`shipmentBoxId`가 맞는 shiptrack URL만, 같은 박스의 모든 `vendorItemIds`를 URL에 | |
| 16자리 이상 식별자는 JSON 파싱 전에 문자열로 보존 | 큰 정수 손실 |
| 상세·배송 실패는 **항목별 3회** 뒤 경고와 함께 건너뜀 | 한 건이 전체를 막지 않게 |
| 송장번호 없는 건은 배송 JSON에서 제외, `(orderId, shipmentBoxId)`로 분리 배송 구분 | → scraper-notes "5건 중 4건" |
| `다음으로 끝까지` 모드는 URL에 `requestYear`를 안 붙인다 | 붙이면 수집 범위가 바뀐다 |

수집 범위 셋 — `목록만`(주문·상품·금액·송장 요약) / `+ 상세`(할인·배송비·복합 결제·배송 요청) / `+ 배송조회`(단계·이력). 대기는 0.3~1.1초, 여섯 번에 한 번 1.1~2초 — **간격이 일정하면 사람으로 안 보인다.** 0.3초 아래로는 못 줄인다.

`[실측]` 테스트 45개 — `node scripts/extension/tests/index.js`. 실측 상세·배송 fixture, NextData fixture(큰 정수·무연도/연도별), 연속 흐름(이전 DOM 거부), 워커(재주입·재기동·저장 경쟁·알람 재개).

## 폴더가 넷이다

| 폴더 | 무엇 |
|---|---|
| `scripts/extension/` | **현행 5.4.1** |
| `scripts/extension_nextdata_ref/` | 목록만 읽던 참고판. 상세에 안 가고 `DeliveryRegion`은 항상 `null`, **팝업을 닫으면 멈춘다**, 3~7초 대기. README가 "`scripts/extension/` 폴더를 선택한다"고 적혀 있어 자기 폴더를 가리키지 않는다 |
| `scripts/extension_backup_20260821_5_4_pre_cleanup/` | 레거시 삭제 직전 백업 — 배포 zip에서 뺀다 |
| `scripts/legacy/` | Playwright 시도 둘 |

**README 둘의 제목이 같다**(`쿠팡 주문내역 추출 확장 프로그램`). 설치법을 따라 하려면 `extension/` 것만 본다.

## 버린 구조가 남긴 것 — 근본 원인 8개

`[실측]` `docs/작업기록.md` 2026-08-21. 처음 요청은 "배송 정보를 못 읽는 문제 하나"였다. 커밋 안 된 `content.js` 1005행·`popup.js` 511행을 `git checkout --`으로 잃고 테스트 976행을 명세 삼아 다시 만들면서 아래가 차례로 드러났다.

| # | 원인 | 증상 | 해결 |
|---|---|---|---|
| 1 | 수집 루프가 `executeScript` 주입 함수 안에서 페이지를 이동 → **주입 컨텍스트 파괴** | 로그 소실, `result: undefined`, 이동 없는 진단만 동작 | 제어를 service worker로. content는 DOM 읽고 다음 행동만 반환 |
| 2 | `orderCardOf`가 조상을 타다 목록 컨테이너·`body`까지 카드로 봄 | 주문 6건에 상품 행 66개 | 카드엔 `주문 상세보기` 리프가 정확히 하나 |
| 3 | 카드 헤더를 클릭 — **React 핸들러는 `span`에 있고 이벤트는 위로만 전파**, `element.onclick`은 항상 `null` | 상세로 못 감 | 가장 안쪽 리프 클릭, 안 먹히면 조상으로 한 칸씩(최대 4). `pointerdown→mousedown→mouseup→click` |
| 4 | **URL이 먼저 바뀌고 DOM은 나중** — 서명(URL+내용)이 바뀌면 성공으로 봄 | 상세 클릭 무한 반복, 목록은 1페이지 6건에서 종료 | `wait` 행동 최대 6회 |
| 5 | **`args: [method, undefined]`** — Chrome이 직렬화 못 해 호출 자체 거절 | 페이지 상태 읽는 호출이 **한 번도 성공한 적 없음**. 인자 있는 팝업 버튼만 됐다 | `undefined`→`null`, JSON 왕복으로 중첩까지 |
| 6 | `document.textContent`는 `null` | 상세가 계속 목록으로 판정 | Document면 `body`로 내려감 |
| 7 | `body.textContent`엔 `<script>` 안 JSON 문자열까지 들어옴 | 목록이 상세로 판정 | 요소 단위로, `script`·`style`·`noscript`·`template` 건너뜀 |
| 8 | START로 깨어난 워커의 최상단 `resume()`과 `start()`의 `resume()`이 경합 | 아무도 안 돎, `지금 상태`를 누르면 돎 | 도는 중 들어온 요청을 기억했다 재시작 |

**5번이 처음부터의 진짜 원인이었다.** 앞의 진단들은 대부분 그 그림자였다 — 페이지 상태 확인이 전부 실패한 위에서 내린 판단이 어긋난 것이다. 이걸 못 잡은 이유는 **가짜 `chrome`이 아무 값이나 받아줬기 때문**이고, 6번은 `parseFragment`가 요소를 돌려줘서(요소의 `textContent`는 정상), 7번은 픽스처에 `<script>`가 없어서였다. 셋 다 **테스트 대역이 실물보다 관대했다.**

### 재작성 원칙 — "바뀌었나"가 아니라 "원한 상태가 됐나"

`docs/재작성_계획.md`. 행동 뒤 "무언가 바뀌었나"를 보던 걸 버리고 **원하는 결과가 실제로 나올 때까지 확인**한다. 확인 안 되면 기다리기만 하지 않고 클릭 방법을 바꾼다.

| 행동 | 원하는 결과 |
|---|---|
| 다음 | 목록이면서 주문 구성이 직전과 다르다 |
| 상세보기 | 목록이 아니다 |
| 배송 조회 | 목록이 아니고 송장 표가 있다 |
| 목록 복귀 | 목록이면서 구성이 떠나기 전과 같다 |

클릭·복귀는 5.4.1에서 통째로 사라졌지만 **이 원칙은 "목표 URL·주문번호·배송박스·화면 표지를 확인한 뒤에만 성공"으로 살아남았다.**

### Codex가 테스트를 약하게 만들었다

통합 테스트의 `forceWrongReturnOnce`를 꺼서 복귀 실패 시나리오를 무력화했다. 되돌리니 즉시 실패했고 **실제로 주문 2건이 유실되고 있었다.** Codex가 테스트를 고쳤으면 그 diff를 반드시 본다 — [parallel-work.md](../../wiki/governance/parallel-work.md)의 "받은 뒤 검사"와 같은 말이다.

## 5.4.1이 지운 것

DOM 카드 수집기·카드 해시 / 상세·배송·다음·연도 클릭기와 4단계 재시도 / 복귀·위치 복원 / 직접 fetch·helper 탭·popup driver / `performAction`·`pageFacts`·`collectOrders` / 팝업의 "다음 누르기 시험"·"상세 열기 시험" / **`activeTab`·`tabs`·`www.coupang.com` 권한** / 레거시 통합 테스트와 DOM fixture. 위 근본 원인 2·3·4·6·7·8이 붙어 있던 코드다.

## Scrapling은 안 넣었다

Python·Playwright 계층이라 MV3 확장에 못 들어가고, 별도 프로세스면 로그인 세션을 넘겨야 해 차단 문제가 되살아난다. 설계 원칙만 가져왔다 — 목록과 보강 단계 분리, 항목별 안정 키와 체크포인트, 표지 없으면 제한 재시도 뒤 다음 항목.

## 관계

- [scraper-notes.md](scraper-notes.md) — 화면 관측·PII
- [distribution.md](distribution.md) — 합본에서 가리는 것
- [catalog.md](catalog.md) — 데이터셋 목록
- [../../wiki/governance/parallel-work.md](../../wiki/governance/parallel-work.md) — Codex 산출물은 받은 뒤 검사
