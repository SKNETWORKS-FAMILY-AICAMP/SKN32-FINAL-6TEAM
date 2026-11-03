---
type: report
title: 고객 웹 trip-home 기존 타입 차단 최소 수정
status: draft
domain: travel
---

# 고객 웹 기존 타입 차단 수정 — 2026-10-25

## 수정 전 계약·범위

이 문서는 구현보다 먼저 작성합니다. 대상은 기존 untracked `frontend/apps/web/src/features/trip/trip-home.tsx`의 두 타입 오류뿐입니다. 신규 응대 UI·gateway·response 정책은 수정하지 않습니다. 기존 dirty 작업을 보존하고 프로필 scratch에 원본 바이트를 백업한 뒤 좁은 hunk만 수정합니다.

- `src/lib/settings.ts`의 Settings에는 language/theme/skipAnimation만 있습니다. 2026-10-07 사용자 결정으로 navigation 설정과 저장값 읽기는 제거됐습니다. `DEVELOPMENT.md`·`README.md`와 실제 라우트의 `TripScreen`이 같은 계약입니다. 없어진 설정을 되살리거나 상수로 기능을 끄지 않습니다. 미사용 구화면 파일은 삭제하지 않고, 그 안의 일정·지도·채팅 전환은 모두 유지하며 폐기된 설정 분기만 정리합니다.
- `TripAttention`은 제어형 탭(`CenterTab`, `onTab`), 실제 일정 이동(`onGoto`), 재난 해제 결과(`onResumed`)를 필수로 받습니다. 구 호출부도 로컬 탭 상태, 실제 날짜·선택·펼침·일정 pane 이동, 해당 여행/언어의 recovery 캐시 전달로 계약을 충족해야 합니다. 빈 callback·가짜 결과는 사용하지 않습니다. 활성 `trip-screen.tsx` 호출 계약을 기준으로 삼습니다.
- 실제 URL은 `TripScreen`을 사용하며 `TripHome` 호출은 검사한 src 범위에서 없습니다. 이번 변경은 구화면 재도입이나 URL 연결이 아닙니다.
- `.next-live/types/routes.d.ts`는 현재 0바이트입니다. 원본 생성물·tsconfig를 삭제/변경/완화하지 않습니다. 원본 tsc 실패와 깨끗한 격리 소스/동일 설정의 typecheck·Next webpack production build 결과를 분리 기록합니다.

## 검증 계획·경계

기존 Node 24.10.0 x64(`cache/scratch/cs-web-response-status/node.exe`)와 설치된 의존성을 재사용합니다. 원본 tsc의 정확한 두 오류를 RED로 보존한 후 수정하고 전체 Vitest·원본 tsc·깨끗한 격리 tsc·실제 Next webpack production build를 실행합니다. 컴파일만 통과한 결과는 빌드 성공으로 쓰지 않습니다.

서비스/브라우저·실 HTTP·DB·모델·배포·커밋/푸시는 실행하지 않습니다. 실제 화면은 미확인입니다. 루트 wiki·인계 통합은 부모 소유입니다.

## 실제 결과

증거: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/type-repair-20261025/`.
실행기: 상위 폴더의 `node.exe`(실측 v24.10.0 x64), `type-repair-run.py`. 설치하지 않았습니다. 기존 로그·build-web 배치를 확인했으며 과거 증거를 덮지 않고 새 고유 폴더에 실행했습니다.

| 관문 | 결과·로그 |
|---|---|
| RED 원본 `node node_modules/typescript/bin/tsc --noEmit --incremental false` | exit 2. TS2339(Settings.navigation), TS2739(TripAttention의 tab/onTab/onGoto/onResumed 누락), TS2306(기존 generated)의 정확한 3건 재현. `red-original-tsc.log` |
| GREEN 원본 동일 tsc | **exit 2 유지**. trip-home 두 오류는 없어지고 `.next-live/types/validator.ts(5,56)` TS2306만 남음. `green-original-tsc.log` |
| 전체 `node node_modules/vitest/vitest.mjs run` | **770/770 = 100%, 91/91 파일**, 실패/skip 0, exit 0. `all-vitest.log` |
| 수정 파일 ESLint | exit 0. `scoped-eslint.log` |
| 격리 `node node_modules/next/dist/bin/next typegen` | exit 0. `clean-typegen.log` |
| 격리 동일 tsc(빌드 전) | exit 0. `clean-tsc-before-build.log` |
| 격리 `node node_modules/next/dist/bin/next build --webpack` | **exit 0**. webpack 컴파일 23.4초 → TypeScript 16.4초 → page data → **static pages 11/11 = 100%** → 최종 page optimization → build traces → 전체 route 표 완료. `clean-next-webpack-production-build.log` |
| 격리 동일 tsc(빌드 후) | exit 0. `clean-tsc-after-build.log` |

이번 RED/GREEN 회귀는 사용자가 지정한 실제 TypeScript 검사이며 별도 가짜 assertion이나 오류 허용 주석을 추가하지 않았습니다. 전체 Vitest는 기존 suite 회귀이며 구화면 callback의 실제 브라우저 조작을 검증한 것으로 주장하지 않습니다.

### 격리 조건과 generated 분류

- 원본 src/public과 설정·lock을 새 `clean-web`에 복사했습니다. `_backup`은 기존 tsconfig/Vitest에서도 제외되는 보존 사본이라 복사하지 않았습니다. 원본 generated 디렉터리·개인 `.env*`는 복사하지 않았고 기존 node_modules를 junction으로 연결했습니다.
- 실행 환경은 `NEXT_DIST_DIR=.next-live-hours`, `NEXT_PUBLIC_DATA_MODE=live`, `NEXT_PUBLIC_MAP_PROVIDER=osm`, `NEXT_TELEMETRY_DISABLED=1`입니다. 원본 next-env가 가리키는 dist 경로와 맞춰 Next가 새 타입을 정상 생성하도록 했습니다. API 요청·서버 기동은 하지 않았습니다.
- **격리 tsconfig는 원본과 바이트 일치**합니다. include/exclude·strict·skipLibCheck 등 검사 강도는 한 줄도 완화하지 않았습니다. 원본 tsconfig와 next-env도 수정 전 백업과 SHA256 일치합니다.
- 원본 `.next-live/types/routes.d.ts`는 계속 **0바이트**이며 validator가 이를 module로 import하여 실패합니다. 깨끗한 Next가 생성한 routes.d.ts는 **1,965바이트**, validator도 생성돼 같은 설정으로 통과했습니다. 따라서 이번 증거에서 남은 원본 TS2306은 소스 계약 결함과 구분되는 기존 불완전 generated 산출물 문제입니다. 원본 생성 폴더를 지우거나 고쳐 성공으로 만들지 않았으며 원본 tsc 실패는 여전히 열려 있습니다.
- `candidate-input-hashes.json`의 **380/380 = 100%** 입력 파일이 빌드 후에도 원본과 SHA256 일치했습니다. 전체 게이트 실행 후 소스 변경 없음. 빌드 ID `tX0WALqn1NNJeFlOJBJj7`.

## 변경·보존·인계

- 제품 코드 변경은 `frontend/apps/web/src/features/trip/trip-home.tsx` **1개 파일**입니다. 폐기된 navigation 설정을 타입 확장·고정 false로 우회하지 않고 해당 분기/전용 effect만 제거했습니다. 일정·지도·채팅 버튼과 각 pane은 유지하고 inline nav로 연결했습니다. TripAttention의 탭·일정 이동·recovery 캐시 callback을 현재 필수 계약에 맞췄습니다. 활성 TripScreen·gateway·응대 UI/정책·CSS·tsconfig는 수정하지 않았습니다.
- 문서 변경은 이 보고서와 cs `wiki/index.md` 현재 상태 한 문장입니다. 기존 10-24 보고서는 동결 보존했습니다. 루트 wiki·인계는 부모가 통합합니다.
- 수정 전 백업: 증거 폴더 `backup/src/features/trip/trip-home.tsx`, `backup/tsconfig.json`, `backup/next-env.d.ts`, `backup/wiki-index.md`. trip-home 시작 SHA256 `21b6d5e802a1131a6e09db5c6044deabbef2aad56c9d72697fa8fea4392eb65c`, 수정 SHA256 `c6037be0be292455ad55f1730f39dae66668bf9408a74df3a9bdbf143b0786ba`. `own.diff`와 `verification-manifest.json`으로 이번 hunk와 입력 보존을 구분합니다. 파일은 여전히 기존 untracked이며 삭제·복구·stash·기존 dirty 덮어쓰기는 하지 않았습니다.
- **소스 타입 결함 2/2 = 100% 해결, 깨끗한 전체 production build 통과**입니다. **원본 tsc generated 오류는 미해결**, 서비스·UI 실화면·실 HTTP·DB·모델·배포는 미확인입니다. 커밋/푸시 없음. 추가 사용자 결정은 필요하지 않으며 원본 generated 재생성/정리는 별도 범위로 남깁니다.
