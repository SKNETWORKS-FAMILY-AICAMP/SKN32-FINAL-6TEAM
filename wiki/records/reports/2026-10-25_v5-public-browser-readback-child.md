# v5 교체 직후 공개 브라우저 제한 readback

## 결과·부모 handoff
- 부모 기록 `2026-10-25_v5-frontend-parent-live.md` 및 profile scratch `web-v5-release-20261025-170512-b1431a/PARENT_FRONTEND_LIVE.json`을 읽었습니다. root/cs AGENTS·CLAUDE·cs RULE 및 양쪽 wiki index, integration/dogfood skill을 확인했습니다. 기존 공유 index와 과거 보고서는 수정하지 않았습니다.
- 새 named browser session `v5-public-readback-20261025-new`을 사용했습니다. 도구가 기존 Edge 프로필 잠금으로 **fresh browser without user's logins**를 사용했다고 명시했습니다. 기존 고객 storage를 별도로 읽지 않았습니다.
- 실제 localhost:3100 홈과 /start를 렌더링하고 스크린샷을 직접 시각 확인했습니다. 구구루트 로고·헤더·도움말/언어/메뉴가 보이며 깨진 화면이나 예외 오버레이는 관찰하지 않았습니다. 홈의 최근 여행은 초기 ‘불러오고 있어요’에서 ‘아직 등록한 여행이 없어요’로 바뀌었습니다. /start는 필수 동의 전 정상 잠금 화면입니다.
- favicon 선언은 `/images/guguroute-mark.svg`, apple-touch icon 선언은 `/images/guguroute-apple-touch-icon.png`입니다. 브라우저 performance에서 mark.svg HTTP 200을 확인했습니다. apple-touch 실다운로드는 확인하지 않았습니다.
- 브라우저가 실제 로드한 홈 JS는 `app/page-41e253eae9df2ea2.js`, `app/layout-615c076ec1404b4f.js`, `8892-09f1c3004c008952.js` 등이며 parent localhost artifact 목록과 일치합니다. 해당 홈 script/css resource 상태는 관찰 목록에서 모두 200이었습니다. BUILD_ID manifest의 별도 재검산은 이번 절에서 완료하지 못했습니다. 부모 BUILD_ID `ZojSXmTH7hmXO9eyo677J` 및 22/22 바이트 검산은 **부모 증거**입니다. LAN 화면은 이번 절에서 열지 않았습니다.
- fresh browser 홈 API `/v1/web/auth/me` 401은 비로그인 응답이며, `/v1/web/support/notices` 200이 관찰됐습니다. 공개 GET `http://127.0.0.1:8042/v1/web/features`는 HTTP 200, `{"guardian":false,"risk_panel":false,"plan_test_mode":true}`였습니다.

## 제한·미완료
- 호텔 조식 예시와 동적 날짜는 **이번 실제 브라우저에서 미확인**입니다. /start에서 동의가 필요하므로 동의 저장·guest 생성·제출 금지 경계를 유지하고 진행하지 않았습니다. /trips/new 탐색 시도는 browser exec 60초 timeout이었고 이후 현재 화면은 /start였습니다. 이를 예시 성공으로 계산하지 않습니다.
- 뒤이은 HTTP 정적 문자열 재수집도 30초 timeout으로 결과 파일을 얻지 못했습니다. 실제 served JS의 새 reading 분기/문자 확인을 이번 절 완료로 주장하지 않습니다. 부모 바이트 검산 및 이전 child fixture 4/4와 실화면 검증은 별개입니다.
- Runtime/Log CDP enable만 수행했고 console event 수집이 완결되지 않았습니다. ‘JS console 오류 0’은 주장하지 않습니다. 정상 렌더링과 resource 200 관찰만 확인했습니다.
- 고객 접수 POST 재생·동의 저장·guest 생성 버튼·폼 제출·등록·기존 고객 storage 조회를 하지 않았습니다. 서비스 kill/restart·소스/DB 변경·schema906 재적용·모델 호출도 하지 않았습니다. 실제 고객 처리시간 개선이나 E4B 품질 개선 주장은 없습니다.

## 증거 파일
프로필 `cache/scratch/v5-public-readback-20261025-child/`:
- `home.png`: 홈 로딩 완료 후 화면
- `start.png`: 동의 전 공개 화면
- `features.json`: 실제 공개 features GET 응답

브라우저 screenshot 최종 원본 경로: `C:/Users/kcxsz/.config/browser-harness/tmp/p-bab3e632fff3/shot.png` (덮어쓰일 수 있으므로 위 scratch 사본을 우선합니다).

## 다음 소유자에게
현 상태/서비스는 그대로 유지했습니다. 동의·고객 쓰기 0 경계에서 예시를 열 수 있는 승인된 공개 경로가 없다면 동적 날짜를 미확인으로 남겨 주세요. 이 결과만으로 소스를 패치하거나 부모 API 전환 계획을 바꾸지 마세요.
