# 여행 취향 전송 · 백엔드 전달 계약

작성일: 2026-09-28 · 상태: 프론트가 보내는 형식과 백엔드 합의 제안. 받는 API는 아직 없다(TeamFlow `ST4F-155`).

온보딩의 여행 취향 9문항 답변을 추천에 쓰도록 서버로 보내는 형식이다. 정본은 코드의 Zod 스키마 [`src/features/onboarding/payload.ts`](src/features/onboarding/payload.ts)의 `preferencesPayloadSchema`이며, 이 문서는 그 설명이다. 둘이 다르면 코드를 기준으로 이 문서를 고친다.

## 1. 언제 보내나

취향 완료 요약의 `여행 계획 등록하기`(여행이 이미 있으면 `내 여행 이어보기`)를 누르면 `TripGateway.submitPreferences(payload, language)`를 부른다. 성공해야 다음 화면으로 넘어가고, 실패하면 요약에 남아 오류를 보이고 다시 누를 수 있다. 실패를 데모 성공으로 바꾸지 않는다.

| 데이터 모드 | 동작 |
|---|---|
| `demo` | 스키마로 형식만 검사하고 성공한다. 저장하지 않고 어디로도 보내지 않는다 |
| 그 외 | 실제 API가 없으므로 `DATA_MODE_UNAVAILABLE` 오류. 2026-09-28 `live` 빌드에서 요약에 머무르고 오류가 뜨는 것을 확인했다 |

## 2. 형식

값은 화면 문구가 아니라 선택지 코드다(`model.ts`의 `options` 첫 칸). 표시 언어가 바뀌어도 같은 값이 간다.

```json
{
  "version": 1,
  "language": "ko",
  "answers": {
    "themes": ["food", "nature"],
    "companions": { "types": ["family"], "adults": 2, "children": 1, "infants": 0 },
    "food": { "none": false, "allergies": ["nuts"], "diet": [], "religious": [] },
    "transport": ["public", "walk"],
    "budget": { "range": "custom", "amountKrw": 800000 },
    "nationality": "foreign",
    "priority": "activity",
    "detailPriority": { "food": "taste", "activity": "healing", "transport": "walk" },
    "religion": "unselected"
  },
  "skipped": ["religion"]
}
```

| 키 | 질문 | 답했을 때 값 |
|---|---|---|
| `themes` | 1 여행 테마 | 코드 배열(1개 이상): `food` `nature` `culture` `activity` `shopping` `local` |
| `companions` | 2 여행자 구성 | `types`: `alone` `partner` `friends` `family` `other` 배열, `adults`(1~20) `children` `infants`(0~20) |
| `food` | 3 기피 음식 | `none`(해당 없음), `allergies`, `diet`, `religious` 코드 배열 |
| `transport` | 4 이동수단 | 코드 배열(1개 이상): `public` `walk` `car` `taxi` |
| `budget` | 5 예산(1인 전체) | `range`: `low` `mid` `high` `premium` `custom`, `amountKrw`: `custom`일 때만 숫자, 아니면 `null` |
| `nationality` | 6 내국인 여부 | `domestic` `foreign` |
| `priority` | 7 우선순위 | `food` `activity` `transport` |
| `detailPriority` | 8 세부 우선순위 | `food`·`activity`·`transport` 각 하나 |
| `religion` | 9 종교 | `none` `christian` `catholic` `buddhist` `muslim` `hindu` `other` `skip` |

`religion`의 `skip`은 사용자가 고른 **`응답하지 않음`(Prefer not to say) 선택지**다. 질문을 건너뛴 것과 다르며 `skipped`에 들어가지 않는다.

## 3. 건너뛴 질문

사용자가 `응답하지 않고 넘어가기`로 넘긴 질문은 화면에 `미선택`으로 보인다. 전송값은 질문별 기본값 표 `skipDefaults`에서 가져오고, 그 질문 키를 `skipped`에 넣는다. 서버는 `skipped`로 사용자가 고른 값과 기본값을 구분할 수 있다.

**현재 모든 질문의 기본값은 `"unselected"`다.** 질문별 일반 기본값은 추후 정한다(사용자 결정, 2026-09-28). 정하면 `skipDefaults`의 해당 칸만 답했을 때와 같은 형태의 값으로 바꾸면 되고, 스키마는 `"unselected"`와 답 형태를 모두 받는다.

## 4. 백엔드와 합의할 것 (미정)

- 엔드포인트·메서드·인증. 백엔드 scope API 키는 브라우저에 넣지 않는다.
- 이 답변을 누구에게 묶을지(사용자·여행)와 여행 등록 요청과의 순서.
- 응답 형식과 재시도·멱등성(같은 답변을 두 번 보낼 때).
- 질문별 건너뜀 기본값.
- 약관·동의: 목업 약관은 온보딩 답변을 "현재 페이지 상태로 유지"한다고 적고 있다. 실제로 서버에 보내려면 수집 항목·목적·보관을 약관에 반영해야 한다. 종교·알레르기·식단 정보는 목업 약관에도 "필요성과 별도 동의 여부를 검토"해야 한다고 적혀 있다.
