# SNS 맛집 링크 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 승인된 SNS 맛집 링크 접수·후보 확인을 여행 전 일괄 배치와 여행 중 식사 변경에 연결한다.

**Architecture:** 링크 정규화·안전한 메타데이터 조회·근거 검증 추출을 독립 부품으로 둔다. 고객 소유 접수에 희망 식당을 보관하고, 기존 장소 검색과 전체 일정 검증을 사용한 변경안을 명시적으로 적용한다. 등록 여행은 기존 reopen/edit/confirm 경로를 사용한다.

**Tech Stack:** Python/FastAPI/PostgreSQL, 기존 chat.json, React/Next.js/TypeScript, pytest/vitest.

**Spec:** [승인된 첫 범위](2026-10-14_social-dining-links-design.md) — 2026-10-15 사용자 「그래」로 구현 승인.

## Global Constraints

- 서울, 공개 Instagram/TikTok/YouTube 링크, 텍스트 우선과 고객 보완. 영상 다운로드·자막 전사·사진 해석 제외.
- 링크만 전송하면 후보 저장만 한다. 일정 변경은 검증된 변경안의 명시적 적용과 기존 여행 등록/확정 경로를 따른다.
- 완료·고정 항목과 식사 외 활동은 이 기능으로 재배치하지 않는다. 자료 부족은 해당 후보만 보류한다.
- 고객·tenant 격리, 기준 revision, 멱등성, 출처·확인 시각을 유지한다.
- 현재 미커밋 변경은 보존한다. native worktree는 Windows 긴 경로로 실패했으므로 현재 폴더에서 파일별 백업과 소유 경계를 사용한다.
- 이 계획·승인 범위를 기준으로 계속 구현한다. 추가 실행 방식 확인을 반복하지 않는다. 코디네이터가 통합하고 독립 파일 구현을 병렬 위임한다.

## Review Focus

- 단축 URL·userinfo·비표준 포트·리디렉션이 내부 주소 조회로 이어지지 않음: Task 1 안전 조회 시험.
- 모델이 만든 식당·지점이 실제 읽은 문구에 없으면 확정하지 않음: Task 1 인용 검증 시험.
- 다른 고객 접수·낡은 변경안·중복 적용은 저장되지 않음: Task 2/3 소유·revision 시험.
- 배치 일부만 가능할 때 미반영과 꼭 가기 미충족을 숨기지 않음: Task 2 배치 시험.
- 링크와 기존 글/파일/계획 입력이 서로 사라지지 않고 실패 후 다시 보완 가능: Task 4 화면 시험.

## Task 1: 링크 읽기·추출 부품

**Files:** Create `app/domains/travel_ops/components/intake/social_links.py`, `tests/unit/travel/test_social_links.py`; coordinator owns shared guardrails.

**Interfaces:** `resolve_links(entries: list[dict], *, chat=None, fetch=None, limits: dict, progress=None) -> list[dict]`. 입력 `{url,note?,priority?}`. 결과별 `{key,source_urls,platform,status,reason,restaurants:[{name,area,branch,menu,evidence}],priority,checked_at}`. `fetch_metadata(url, *, limits)`는 텍스트와 canonical URL을 반환하며 테스트에서 교체한다. 모든 링크 결과를 남기고 중복은 source_urls에 합친다.

- [ ] 실패 시험: 플랫폼 ID 정규화·중복·지원 밖 URL·리디렉션·응답 상한·없는 근거·다수 식당·고객 보완·부분 실패.
- [ ] 지정 시험을 실행해 미구현 실패를 확인한다.
- [ ] allowlist·설정 상한을 지키는 조회와 인용 검증 추출을 구현한다. LLM 실패와 접근 실패를 구별한다.
- [ ] `python -m pytest tests/unit/travel/test_social_links.py -q`가 통과한다.

## Task 2: 후보 보관·배치·명시적 적용

**Files:** Create `components/intake/social_dining.py`, migration `904_social_dining_links.sql`, `tests/unit/travel/test_social_dining.py`.

**Interfaces:** `list_links`, `resolve`, `update`, `preview`, `apply`는 `conn`과 keyword `tenant_id,customer_id,intake_id`를 받는다. `resolve`는 Task 1과 chat·fetch·progress를 사용한다. `update`는 저장 후보의 `key`와 보완/우선순위/restaurant_index/selected_ref를 받는다. `preview(revision,target_item_id=None,chat=None,kakao=None,now=None)`는 `{revision,proposal_id,changes,unplaced,links}`를 반환한다. `apply(revision,proposal_id,kakao=None,dining=None)`는 저장한 제안만 사용하고 전체 검증 후 기존 intake view를 반환한다.

**Storage:** 접수당 후보 JSON과 제안 JSON을 `intake_dining_links`에 보관한다. 소유 검사는 trip_intakes와 customer/tenant를 함께 사용한다. 후보 상태는 접수 revision과 구분하며, 변경 후 옛 제안을 무효화한다. SNS는 장소 제공자 타입에 섞지 않는다.

- [ ] 실패 시험: 소유 격리·동명이점·다수 식당·고정/완료 식사 제외·부분 배치·미충족·낡은 제안·중복 적용.
- [ ] 실패를 확인한 뒤 저장/조회와 기존 `candidates.search`·`pipeline.edit`·`pipeline.view` 연결을 구현한다.
- [ ] preview는 저장점을 되돌려 일정 revision을 바꾸지 않고, 실제 적용 시 전체 검증 결과를 다시 확인한다. 식사 외 활동 변경은 거부한다.
- [ ] `python -m pytest tests/unit/travel/test_social_dining.py -q`가 통과한다.

## Task 3: 인증된 API·설정·계약

**Files:** Create `entry/social_dining_api.py`, `tests/unit/travel/test_social_dining_api.py`, `wiki/external/social-dining-links.md`; Modify `entry/trip_api.py`, `config/guardrails.yaml`.

**Interfaces:** `register_routes(router, *, web_customer, count, lazy, chat_factory, kakao_factory, dining_factory, error)`로 기존 라우터에 결합한다. `/v1/web/trip-intakes/{intake_id}/dining-links` GET/POST, `/{key}` PATCH, `/preview` POST, `/apply` POST. POST 접수는 `{links:[{url,note?,priority?}]}`, PATCH는 보완과 선택, preview는 `{revision,target_item_id?}`, apply는 `{revision,proposal_id}`. `Accept: text/event-stream`은 기존 op_stream의 단계·생존 신호·result/error를 사용한다.

- [ ] 계약 문서를 구현 전에 추가한다. 추출·후보 상태와 일정 반영 상태를 구분한다.
- [ ] API 실패 시험: 인증·소유·잘못된 몸통·충돌 매핑·SSE/JSON 일치.
- [ ] 인증·사용량 제한·설정 기반 호출 상한·예외 코드와 기존 라우터 연결을 구현한다.
- [ ] Task 1/2/3 단위 시험과 기존 접수 회귀를 실행한다.

## Task 4: 공통 고객 화면과 통합 검증

**Files:** Create `features/social-dining/*`, `lib/live/social-dining.ts`와 대응 시험. Modify `features/plan-check/*`·`features/trip/trip-edit.tsx`의 최소 진입점. 기존 초기 일정 생성·수정 화면을 공통 연결점으로 사용한다.

**Interfaces:** Task 3의 JSON/SSE 응답을 사용한다. 후보에는 `key,status,reason,restaurants,choices?,selected_ref?,priority,source_urls,checked_at`을 표시한다. preview의 changes/unplaced를 보여주고 사용자가 apply하면 부모 intake를 새 view로 갱신한다. 원래 여행 저장은 기존 confirm이 담당한다.

- [ ] 실패 화면 시험: 여러 링크·보완·다수 식당·실패 사유·미반영·명시적 적용·오래된 revision·기존 입력 보존.
- [ ] 공통 패널에 링크 입력·후보 선택·우선순위·변경안·적용을 연결한다. 빈 접수에서도 후보를 보관하고 생성 후 재사용한다.
- [ ] typecheck·vitest·관련 lint와 기존 회귀를 실행한다. 브라우저에서 실제 화면을 확인한다.
- [ ] 독립 코드 검토 후 지적을 보완한다. 계약/보안/DoD 관문을 실행하고 성공·실패·건너뜀을 모두 기록한다. 실플랫폼 조회와 모델 검증은 mock 결과와 구분한다.

## 작업 기록

- 2026-10-15: 사용자 승인 후 현 코드·미커밋 상태 확인. native worktree 생성은 tracked 브라우저 임시 디렉터리의 Windows 경로 길이로 실패. 기존 폴더에서 새 부품 중심 구현으로 진행한다.
- 커밋/푸시·운영 배포는 별도 반영 상태로 기록하며, 사용자 기존 변경을 묶어 커밋하지 않는다.
- 2026-10-15 (Claude 이어받음): Task 1~3 코드·시험은 있었고 Task 4 는 화면 시험이 실패하는 단계(근거 객체·메뉴 문자열 미대응)에서 멈춰 있었다. 아래를 고쳤다 — 각 항목은 먼저 실패하는 시험을 넣고 고쳤다.
  - 화면: 근거를 서버 모양(`{source, quote, source_url, checked_at}`)으로 받고 인용문을 보인다. 메뉴는 글 하나 · 목록 둘 다 받는다(`cards.tsx` · `lib/live/social-dining.ts`). [실측] 실제 모델이 메뉴를 `"냉면"` 글 하나로 돌려줬다.
  - 조회: HTML 은 `</head>` 에서 읽기를 멈추고 상한을 1MB 로 올렸다(`guardrails.yaml`). [실측] YouTube 영상 페이지는 1.4MB, `og:title` 은 약 770KB 지점이라 256KB 상한에서 모든 YouTube 링크가 `response_too_large` 였다.
  - 저장: 실패했다 회복한 링크가 앞 시도의 `source_failure` 를 남기던 것을 통째 교체로 고쳤다(`social_dining.resolve`).
  - API: CORS 허용 메서드에 PATCH 가 없어 화면의 우선순위 · 식당 · 지점 선택 · 보완이 모두 사전 확인 400 이었다(`app/presentation/api/app.py`).
  - 모델 호출 실패를 예외 종류와 함께 로그로 남긴다(`social_links._extract`).
- 2026-10-15 실행 결과: SNS 백엔드 시험 117/117, 화면 vitest 25/25, typecheck 0 오류. travel 단위 전체는 5,337 통과 · 15 실패 · 39 건너뜀 — 실패 15건은 모두 `tests/unit/travel/mobility/`(도착 1분 차이 · 공개 노선 행 수)이며 이번 변경 파일과 겹치지 않는다. 변경 전부터 실패했는지는 깨끗한 사본으로 확인하지 않았다.
- 2026-10-15 브라우저(로컬, `dining_rebuild`): 빈 접수 → 링크 2개(같은 영상) 한 후보로 합침 → 메모로 「우래옥 · 냉면」 추출 확인. 모델은 사용자 승인으로 이번 로컬 시험에만 개인 OpenAI 키를 서버 넘김 키로 넘겼다(파일에 쓰지 않는 scratchpad 실행 스크립트). 이 PC 의 Ollama(gemma4:e4b, CPU)는 같은 추출에 7~15초, gpt-4.1 은 약 1초였다(각 3회).
- 2026-10-15 (2차, 브라우저에서 찾은 것): 각 항목은 실패하는 시험을 먼저 넣고 고쳤다.
  - 적용(apply)이 일반 요청이라 1분 넘는 전체 검증 중 화면이 먼저 포기하고 「서버가 응답하지 않아요」를 보였다(서버는 저장 완료). 미리보기처럼 진행 상태(SSE)로 받는다(`social_dining_api.py` · `lib/live/social-dining.ts` · `model.ts`). [실측] 적용 87초 · 44초 모두 정상 완료 표시.
  - 같은 가게 합치기: 이름 · 좌표가 정확히 같아야만 합쳐 장소 목록 「우래옥」과 카카오 「우래옥 본점」(2.4m)이 지점 둘로 보였다. 지점 표시를 뗀 이름이 같고 150m 안이며 지점 표시가 서로 다르지 않으면, 또는 도로명 주소(도로 · 건물번호)가 같고 한 이름이 다른 이름을 품으면 같은 가게로 본다(「명동교자 명동역점 신관 본점」 = 「명동교자 본점」, 퇴계로 129). 「본점」 · 「별관」, 「서울역점」 · 「종로점」은 가까워도 따로 둔다. 합칠 때는 검사를 통과했거나 우리 장소 목록에서 온 쪽을 남긴다(운영시간 없는 카카오 쪽이 남아 전체 검증을 못 넘던 것).
  - 자동 배치가 이미 들어간 「꼭 가기」 희망 식당의 식사를 다른 희망 식당으로 바꾸려 했다(점심 우래옥 → 명동교자). 고객이 고른 희망 식당이 든 식사는 자동 배치 대상에서 뺀다. 고객이 그 식사를 직접 고르면(`target_item_id`) 바꿀 수 있다.
  - 이미 일정에 든 희망 식당이 다시 찾기에서 고른 지점을 잃고 「골라 주세요」로 돌아가던 것 — 고른 지점이 일정에 있으면 다시 찾지 않고 `already_scheduled` 로 둔다. 화면은 이 사유에 「꼭 가기 미충족」을 붙이지 않는다.
  - 카드에 같은 사유 문장이 두 번 나오던 것(링크 사유 = 배치 사유)을 한 번만 보인다.
- 2026-10-15 최종 실행: 관련 백엔드(아키텍처 · 프로필 e2e · SNS · 접수 장소) 391/391, 화면 vitest 27/27, typecheck 0 오류, ruff · eslint 지적 없음. 브라우저 최종 일정: 진미옥설농탕 → 경복궁 → 점심 명동교자 분점 → 저녁 우래옥(두 SNS 희망 모두 배치).
- 남은 것: 여행 중(등록된 여행 다시 열기) 경로 브라우저 확인 · 실제 Instagram/TikTok 링크 시험 · 미리보기가 검색 결과에 없는 고른 지점을 지우는 동작(위 가드가 일정에 든 경우만 막는다) · 인계 · 보고서 · 커밋.
- 2026-10-15 (3차): 고른 지점이 이번 검색에 없으면 선택을 지우고 남은 한 곳(고르지 않은 지점)을 자동으로 넣던 것을 고쳤다 — 선택을 유지하고 그 후보만 `selected_place_unavailable` 로 보류한다. stash 와 무관한 SNS 시험 112/112, 화면 social-dining 23/23. 보고서: [브라우저 검증](../reports/2026-10-15_SNS_맛집링크_브라우저검증.md).
- 2026-10-15 12:06: 다른 세션이 develop 병합 전 커밋 안 된 변경을 `stash@{0}` 에 넣었다 — SNS 연결 13개 파일이 그 안에 있다. 되돌리기 뒤 연결 · 오늘 수정을 다시 확인해야 한다. 이 세션은 git 을 건드리지 않았다.
- 2026-10-15 (4차, 실제 Instagram 2건): 계정 이름이 든 게시물 주소를 거절하던 것을 고쳤다(링크 시험 48/48). 캡션에 식당명 · 주소가 있는 게시물은 `identified`, 식당명 없는 목록 게시물은 `needs_info` 로 정상 처리. 모델이 `area` · `branch` 를 비워 두는 점은 프롬프트 판올림 결정으로 남겼다. TikTok 미시험.
- 2026-10-15 (5차): develop 병합 · stash 되돌림 뒤 관련 시험 394/394 · 화면 291/291. 여행 중 경로 브라우저 확인 — 등록 → 「일정 수정」에 패널 표시 · 여행 전 후보 이어짐 · 점심을 직접 골라 하동관으로 교체 → 적용 → 「완료」 → 새로고침 뒤 유지. 결정 D-025(공개 게시물 글 읽기 학업용 한정) 작성.
