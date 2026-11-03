---
type: report
title: ST4F-718 저장 정책 후보 독립 검토
status: draft
domain: travel
---

# ST4F-718 저장 정책 후보 독립 검토

2026-10-29 독립 검토 결과는 **통합 HOLD 유지**입니다. 신규 구현은 하지 않았습니다. 정상 새 버전 간 원자성은 확인했으나 구버전 공존 시 중복 재생·raw ID 재생성과 저장 대기 중 무응답 경로를 재현했습니다. 기존 필수 관문 2/3 = 66.7% HOLD는 선행 실행 결과이며 이번에 재실행한 수치가 아닙니다. 개인정보 보존 정책 승인·최신 통합 tip·운영 수락은 미완료이며 운영 완료 분모 모름입니다.

## 발견 사항 — 중요도 순

1. **P1 · 구버전 공존은 여행별 한 번 계약을 깨고 로그아웃 뒤 raw ID를 다시 만듭니다.** `credits-history.ts:74–88`의 이관은 IDB commit 후 v1 키를 제거합니다. 이미 열린 구버전 탭은 v2를 모르므로 제거된 v1을 빈 배열로 읽고 이관된 여행도 다시 허용합니다. 실제 Edge 두 탭에서 새 탭은 `played`, 옛 v1 알고리즘 탭은 `true`이며 raw 여행 ID 배열을 다시 썼습니다. 후보 계약도 구버전 수락 필요를 적었으나 배포 시 갱신을 강제하는 경로는 없습니다. IDB transaction은 localStorage와 옛 코드를 함께 원자화하지 못합니다. **해결/수락 조건:** 새 코드가 활성화되기 전에 구버전 쓰기를 멈추는 검증 가능한 배포 절차 또는 호환 프로토콜, old→new·new→old·동시 이관·이관 중 옛 쓰기·logout 뒤 옛 쓰기 시험이 필요합니다. 단순 재이관은 이미 허용된 재생을 취소하지 못합니다. 재현의 옛 탭은 기존 v1 알고리즘을 실행한 합성 탭이며 옛 전체 앱 mount는 아닙니다.

2. **P2 · open 요청 대기에는 실패 안내 경로가 없습니다.** `credits-history.ts:21–36`은 해당 요청의 `onblocked`만 처리합니다. 다른 탭이 DB v1 연결을 유지하고 v2 업그레이드가 막힌 상태에서 claim의 `open(...,1)`이 뒤에 줄서면 이 요청 자체에 `onblocked`가 오지 않습니다. 실제 Edge에서 1,200ms 관측 동안 Promise가 미완료였고 차단 탭을 닫자 `VersionError`로 끝났습니다. 고정 시간 초과를 재현한 것은 아니며, 소스상 완료 기한·대기 UI가 없어서 차단 연결을 유지하는 동안 결과 안내가 없습니다. `trip-screen.tsx`는 `.then` 뒤에만 Toast를 내고 SignOut은 migration을 기다린 뒤에만 경고/`finally`에 도달하므로 같은 큐 정체가 logout 화면도 묶을 수 있습니다(후자는 전체 UI 재현 전 코드 경로 판단). **수락 조건:** 진행/지연을 표시하고 안전한 제한·재시도 정책을 정하며 늦게 열린 DB를 닫고 늦은 성공이 자동 재생을 열지 않게 실제 컴포넌트에서 검증하십시오. 저장 성공으로 간주하는 timeout 폴백은 금지합니다.

3. **P2 · 로그아웃 뒤 표식 보존은 개인정보 정책 미승인 상태입니다.** HMAC 비추출 키가 같은 origin에 함께 남으므로 ID를 아는 스크립트는 `sign()`으로 이력을 조회할 수 있습니다. 실제 Edge에서 `extractable=false`인 키로 후보 여행 ID의 표식 일치를 확인했습니다. 비추출은 키 export를 막지만 같은 origin 사용을 막지 않습니다. 새 표식에 raw ID·제목·계정·토큰은 없으나 재식별 가능한 기기 이력입니다. 모듈 첫 줄의 “never customer data”는 과도한 설명입니다. 공유 브라우저의 계정 변경, XSS/동일 origin 제3자 코드, 로컬 프로필 접근의 위험이 남습니다. `SessionCard`의 사후 logout 문구만으로 저장 전 안내·보존 종료·동의 철회·여행/계정 삭제와의 관계가 확정되지는 않습니다. 게스트는 member용 SignOut을 사용할 수 없어 이 안내에 의존할 수도 없습니다. **수락 조건:** 매니저·웹/인증·개인정보 책임자의 명시적 결정과 회원/게스트 모두의 고객 안내, 철회/삭제 동작 및 다음 사용자 화면 검증이 필요합니다. 익명화 승인이나 법적 적합성 판정은 하지 않습니다.

4. **P2 · 손상 보장의 범위를 좁혀야 합니다.** 비문자/깨진 v1, 키 유실+남은 표식은 차단됩니다. 반대로 키는 남기고 `played` 내용만 지우는 논리적 부분 유실을 주입하면 같은 여행을 `claimed`로 다시 허용했습니다. 브라우저가 이 방식으로 자연 손상된다고 주장하지 않습니다. 동일 origin 악성 코드는 원래 저장소를 바꿀 수 있어 이 시험은 보안 경계 우회 발견도 아닙니다. 다만 “손상은 항상 차단”이라는 포괄적 수락은 성립하지 않습니다. 임의 레코드 삭제·키 교체·전체 origin 축출을 구분하고 탐지 가능한 손상과 불가능한 유실을 계약에 명시해야 합니다.

## 검증한 것과 제품 계약

루트/CS AGENTS·RULE, 두 wiki 입구, 역할·코드 경로·문서 표준, 후보 보고/patch/계약 및 실제 coord NOTICE 61개를 읽었습니다. coord의 디스크 정리 요청보다 원본 보존 사용자 지시를 우선하며 삭제는 하지 않았습니다. coord에는 쓰지 않았습니다. 검토 담당은 이번 Codex 세션이며 작성 세션의 자체 검증을 독립 승인으로 승격하지 않았습니다.

새 `scratch/st4f718-storage-review-20261029/r`에 후보 src·시험·설정의 일반 파일 사본을 만들었습니다. Git 작업·원본 코드 변경 없이 의존성만 기존 node_modules junction으로 읽었습니다. 후보 7/7 = 100% 파일 SHA256이 선행 후보와 일치합니다. snapshot은 최신 원격 통합본이 아닙니다. 스냅샷 생성 직전 공간 측정을 놓쳤고 직후 여유 227,778,916,352바이트를 확인했습니다. 자료 삭제·이전 사본 수정은 0건입니다.

| 이번 직접 실행 | 결과·의미 |
|---|---|
| Vitest 전체 | 1,241/1,241 = 100%, 실패/skip 0 |
| tsc | 1/1 = 100%, exit 0 |
| 기존 Edge runner 새 프로필 재실행 | 22/22 = 100%; 이전 runner를 그대로 복제하되 경로만 새 snapshot으로 지정 |
| 추가 동시 claim | 32/32 = 100%, 각 두 탭 중 허용 하나 |
| 추가 Edge 관측 | 9/9 = 100% assertion 관측; 결함 재현도 포함하므로 제품 수락률이 아님 |
| 원본 XML·scanner 보존 | 2/2 = 100% SHA256 일치 |

새 버전끼리 동일 played store의 readwrite getKey+add가 직렬화되고 claim은 `tx.oncomplete` 뒤에만 허용됩니다. historyKey 생성도 meta+played 트랜잭션 안에서 한 키를 선택합니다. request success만으로 재생하지 않습니다. 이는 [IndexedDB transaction scheduling·commit 규정](https://www.w3.org/TR/IndexedDB/)과 일치합니다. 브라우저 complete를 OS crash 이후 영구 보장으로 확대하지 않습니다.

기존 runner를 독립 사본에서 재실행해 256개 이력·reload/프로세스 재시작·동일/다른 여행 경합·v1 128/10,000개 이관·actual logout 함수 및 추출 SignOut 본문·raw 제거 실패·키 부분 유실·stale callback 차단을 확인했습니다. 실제 localStorage 포화와 **주입 IDB commit QuotaExceededError** rollback을 구분했습니다. native IDB quota·디스크 포화는 이번에도 재현하지 않았습니다. 주입 abort는 실제 IDB rollback을 실행하지만 브라우저 자체 quota 발생 증거를 대신하지 않습니다.

새 시험에서 IndexedDB 자체 비지원은 HistoryUnsupported, localStorage 접근 거절은 SecurityError, 비문자 v1은 HistoryCorrupt로 차단되고 메모리/서버 폴백은 없었습니다. IDB가 사용 가능해도 legacy 조회 권한이 없으면 막는 것은 보수적인 현재 정책입니다. 배열 전체 비용은 v1 최초 이관에 남고 정상 claim은 한 키만 읽습니다. HMAC 키 후보 생성은 정상 claim마다 수행되므로 원장 O(1) 주장과 전체 crypto 비용을 혼동하면 안 됩니다.

D3은 같은 origin 기기의 자동 시작 한 번이지 방문/완주 기록이나 계정별 이력이 아닙니다. 50 cap/임의 TTL/로그아웃마다 삭제는 기존 계약을 바꿉니다. 반대로 저장 불가 때 자동 시작 보류도 사용자 체감 동작 변경이므로 draft 정책에 대한 공동 수락이 필요합니다. commit 뒤 화면 이탈로 영상을 못 봐도 재시작하지 않는 후보는 시작 권리 예약이라는 추가 해석을 명시했으나 승인된 전체 화면 수락은 아닙니다.

기존 390px Toast 캡처를 직접 열어 코드·수동 보기 안내·닫기 버튼이 보임을 확인했습니다. 이번 22개 runner도 실제 컴포넌트 전체가 아니라 추출 callback/SignOut 본문을 사용합니다. 전체 TripScreen mount, 실제 종료 카드 수동 열기, focus/스크린리더, 언어·휴대폰, 서버 연동은 검증하지 않았습니다. 초기 번들 경고(React external 및 use-client directive)는 로그 출력으로 남았고 실행은 22개 모두 완료했습니다. 첫 웹 준비 PowerShell 명령은 파싱 오류로 실행 전 실패했고 별도 check.py로 바꾸어 성공했습니다. 숨기거나 성공 수에 합치지 않았습니다.

## 남은 수락과 보안 HOLD

필수 후속은 구버전 공존 방지, pending 저장 UI/종료 처리, 보존/삭제 공동 승인, 최신 통합 tip에서 전체 TripScreen·회원/게스트 logout·계정 전환 수락입니다. native IDB quota, 지원 브라우저(Firefox/WebKit/Safari·private/disabled), quota 회복·origin 축출/사이트 삭제도 별도 환경 검증이 필요합니다. 이번 Edge 한 종류의 통과를 지원 브라우저 전체로 확대하지 않습니다.

원본 scanner와 clone baseline의 허용 목록 차이는 선행 보고대로 남습니다. 이번은 원본 scanner `find_leaks`를 변경 없이 새 공개 evidence/문서에 실행하는 제한 검사만 하며, 기존 XML 실패를 제거·예외 처리하거나 보안 전체 관문을 통과했다고 하지 않습니다. 기존 보안 124/125 = 99.2%·필수 2/3 = 66.7% HOLD를 유지합니다. 계약/DoD/보안 PG 관문은 이번에 재실행하지 않았습니다. 원본 제품/운영/트래커 쓰기·commit·push·배포·종결은 각각 0건입니다.

[실행 집계·해시](../evidence/2026-10-29_st4f718-storage-policy-review/summary.json) · [추가 재현 코드](../evidence/2026-10-29_st4f718-storage-policy-review/adversarial.cjs) · [관측](../evidence/2026-10-29_st4f718-storage-policy-review/adversarial.json) · [인계](../../../../wiki/handoff/2026-10-29_st4f718-storage-policy-review.md).
