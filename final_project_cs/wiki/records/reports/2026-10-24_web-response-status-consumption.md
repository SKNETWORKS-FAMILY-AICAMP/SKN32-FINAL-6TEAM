---
type: report
title: 고객 웹 신규 응대 상태 소비 — 로컬 구현·검증
status: draft
domain: travel
---

# 고객 웹 신규 응대 상태 소비

2026-10-24 작업 시작, 10-25 KST 후속 검증. 담당: frontend 응대 소비 child. 부모 매니저의 독립 검토 대기.

## 결론

고객 웹의 문의 JSON/SSE·duplicate·대화 재조회/탭 보관, 알림 목록/현재 알림, 계획 검토·confirm/plan 결과에 선택 응대 필드를 연결했습니다. **전체 Vitest 770/770 = 100%, 91/91 파일 통과**입니다. 수정 소스 ESLint exit 0입니다. **전체 타입 검사와 최종 빌드는 기존 별도 파일 오류 때문에 실패**했으며 서비스/브라우저는 기동하지 않았습니다. 제품 전체·실화면·운영 완료가 아닙니다.

요청의 `cs/frontend`는 디스크에 없었고 실제 루트 규칙과 코드 경로의 `final_project_cs/frontend/apps/web`를 사용했습니다. backend는 수정하지 않았습니다. 루트 wiki/index/handoff 통합은 부모 소유로 남깁니다.

## 계약·최소 UI

코드보다 먼저 [웹 응대 상태 소비 계약](../../external/web-response-status.md)을 작성했습니다. 기존 [공통 응대 계약](../../external/travel-response.md), API 생산자, 루트/cs AGENTS·CLAUDE·RULE, 현재 상태·역할·코드 경로·화면 API를 확인했습니다. 새 디자인 토큰이나 전면 UX 개편 없이 기존 보조 문장과 알림 위치를 재사용했습니다.

- response_status는 complete/partial, question_status는 answered/needs_input/unsupported/failed만 허용합니다. 필드 없는 구서버는 그대로 두고 완료를 추정하지 않습니다. 명시된 잘못된 값은 고정 계약 오류로 거부하며 원값을 오류에 넣지 않습니다.
- partial: ‘일부 확인이 필요해요’. needs_input·unsupported·failed 한계를 짧게 추가합니다. complete는 등록/실행 완료 배지를 만들지 않습니다.
- 접수 response는 answer/completion/question_status/execution_status만 투영합니다. 계획 검토 안내의 실제 response.answer 앞에 ‘계획 검토 · 등록 전’을 표시합니다. registered/confirmation_recorded가 review 화면으로 오면 완료 문장을 표시하지 않고 상태 불일치를 안내합니다.
- confirm/plan 결과의 고객용 응대만 현재 세션에 묶인 **메모리 1건**으로 여행 화면에 전달하여 기존 자동 이동을 유지합니다. 여행 일정 맨 위 등록 결과 위치에서 answer를 표시합니다. 새 URL 인자나 브라우저 영속 저장은 추가하지 않습니다. 세션이 달라지거나 다른 여행이면 사용하지 않습니다. 새로고침 후 이 일시적 응대가 사라져도 실제 여행 조회는 기존대로입니다.
- 원문 scope/request/evidence/workflow/token 등은 신규 상태 객체나 UI로 복사·직렬화하지 않습니다. 기존 개발 전용 basis 표시와 기존 answer 자체의 개인정보 정책은 이번에 전면 변경하지 않았습니다.
- 알림 클릭 자동 focus·기존 선택 질문/승인·등록 가능성·업무 재실행 경계는 변경하지 않았습니다.

## 실제 호출 경로

| 경로 | 연결 |
|---|---|
| 문의 | live/gateway.sendMessage → streamApi(JSON fallback 또는 SSE result) → 응대 allowlist → TripMessage → trip-chat 보조 문장 |
| 중복/재조회 | 같은 request_id 재전송의 duplicate → 같은 result 투영; conversation의 chat.reply 및 탭 저장 상태를 재검증. 구서버 reply에 새 필드가 없으면 같은 Case에 한해 탭 상태 보존 |
| 알림 | live/extras.getNotices → 최소 상태 투영 → trip-attention 본문 아래 + trip-screen의 기존 noticeToast 문장. 이벤트 bell은 기존대로 GET 재조회 |
| 검토 | getIntake/edits/restore/revalidate 및 autofix.view → response 4필드 투영 → intake-review의 기존 계획 확인 안내 |
| 등록 | confirmIntake/planIntake JSON·SSE → 같은 투영 → 세션 한정 메모리 전달 → live gateway 여행 조회 → trip-screen 등록 결과 |

## 실행 결과·RED→GREEN

증거 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/cs-web-response-status/`.

| 시험 | 실제 결과 |
|---|---|
| gateway JSON/SSE/duplicate 신규 상태 | RED 3 실패/40 통과 → GREEN 43/43 |
| 알림·탭 저장 검증 | RED 2 실패/52 통과 → GREEN 54/54 |
| 표시 component | 최초 미구현 import 실패와 별도로 빈 component를 통한 의미 있는 RED 1 실패/2 통과 → GREEN 3/3 |
| 계획 응대 투영/등록 전달 | RED 4/4 실패 → GREEN 4/4 |
| 검토/등록 문장 | RED 3 실패/11 통과 → 전체 회귀에 포함하여 GREEN |
| edits/restore/revalidate/autofix 투영 | RED 4 실패/4 통과 → 기존 autofix 빈 응답 fixture 회귀 1건도 보존하여 최종 GREEN |
| 구서버 chat reply가 새 상태를 지우는 결함 | RED 1 실패/44 통과 → 최종 GREEN |
| 최종 단일 전체 실행 | `node node_modules/vitest/vitest.mjs run`: **770/770 = 100%, 91/91 파일**, 실패/skip 0, exit 0 (`all-unit-final.log`) |
| 수정 소스 ESLint | `lint-final.log`, exit 0 |
| 전체 원본 tsc | `tsc --noEmit --incremental false`, exit 2; 아래 기존 오류 3건 (`typecheck-final.log`) |
| 최종 격리 Next webpack build | 컴파일 성공(6.7초), TypeScript에서 기존 오류 2건으로 exit 1 (`build-webpack-final.log`) |

### 도구·빌드 차단 사항

- 실제 lock은 앱의 package-lock.json, package.json 엔진은 Node >=22 <25입니다. 기본 Node 26.7.0 arm64로 첫 Vitest가 기존 x64 네이티브 바인딩을 읽지 못했습니다. lock/node_modules를 지우거나 바꾸지 않고 공식 Node 24.10.0 x64 실행 파일을 프로필 scratch에 받아 기존 x64 의존성을 사용했습니다. pnpm은 없었습니다. npm 12.0.2, 프로젝트 Vitest 5.0.1/Next 16.3.5입니다.
- 원본 tsc: `.next-live/types/validator.ts:5`의 routes.d.ts 비모듈 오류 1건, **작업 전부터 untracked인** `src/features/trip/trip-home.tsx:68`의 Settings.navigation 부재와 `:225` TripAttention 필수 props 누락 2건입니다. 이 파일과 기존 생성물을 삭제/수정/제외하지 않았습니다.
- 이번 소유 hunk를 되돌린 **scratch baseline** tsc에서도 trip-home.tsx의 동일 2건을 재현했습니다(`typecheck-baseline.log`). 기존 상태의 타입 결함이며 이번 범위 밖입니다. 원본의 생성 폴더 오류는 격리 사본에 생성물을 복사하지 않아 나타나지 않습니다.
- 빌드는 원본 .next/tsconfig/next-env를 보호하려고 소스/설정 사본에서 실행했습니다. 기본 Turbopack은 외부 node_modules junction을 허용하지 않아 실패(`build.log`). 공식 --webpack 대안에서는 최종 소스 컴파일이 통과했으나 위 기존 trip-home 2건 때문에 **전체 빌드는 실패**입니다. TypeScript 검사 완화나 오류 파일 제외로 성공을 만들지 않았습니다. 격리 사본의 설정 변경은 원본에 반영하지 않았습니다.

## 변경·보존

신규: `src/lib/response-state.ts`, 동명 test, `src/components/response-status.tsx`, 동명 test, `src/lib/live/response-consumption.test.ts`.

작은 hunk 수정: `src/lib/live/{gateway.ts,gateway.test.ts,extras.ts,extras.test.ts,intake.ts,intake-review.ts}`, `src/features/trip/{model.ts,trip-chat.tsx,trip-attention.tsx,trip-screen.tsx}`, `src/features/intake-review/intake-review.tsx`.

문서: 소비 계약·이 보고서·cs wiki index/log. 원래 dirty 변경은 유지했습니다. 원본 백업·baseline.diff·이번 hunk만의 own.diff·변경 manifest는 위 scratch 폴더입니다. 대부분 파일은 수정 전에 백업했습니다. **extras.test.ts는 최초 clean 상태의 HEAD에서, intake-review.ts는 기록한 자기 hunk만 역적용하여 원본 백업을 사후 복원했습니다.** 모든 파일을 수정 전 백업했다고 과장하지 않습니다.

## 미확인·부모 인계

- 부모가 전체 타입/빌드의 기존 trip-home 및 .next-live 오류를 별도 처리할지 결정해야 합니다. 이번 child가 무관한 untracked 파일을 고치지 않았습니다.
- 실제 브라우저·실화면·실서버·DB·모델·외부 고객 API·배포 확인 없음. 앱/서비스 기동 승인 경계를 유지했습니다. 실제 화면의 줄바꿈·밀도·읽기 쉬움은 미확인입니다.
- response.answer는 서버가 제공하는 고객용 문장으로 React 텍스트 렌더링합니다. answer 자체의 문장 품질·개인정보 안전 전체 인증은 frontend enum 검사로 대신할 수 없습니다.
- 현재 검사한 고객 웹 응대 API에서 필수 계약 변경 요청은 발견하지 못했습니다. 별도 `/v1/trips/plan`의 plan_generated는 이 웹 intake/confirm 소비 경로가 아니며 이번 범위에 추가하지 않았습니다.
- 커밋/푸시·루트 wiki/index/handoff 변경 없음. 부모는 이 보고서와 소비 계약을 현재 상태 및 루트 인계에 연결하고 독립 검토 후 통합 판정해 주세요.
