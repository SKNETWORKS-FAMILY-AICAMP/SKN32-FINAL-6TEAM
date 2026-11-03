<!-- 후보 폴더: C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/web-allpast-refusal-20261026-011450-9110/ (patch · evidence · REPORT_KO.md) — 작성 2026-10-26 KST -->

# 웹 — 전부 과거 거절(itinerary_infeasible / all_dates_in_past) 영어 문구 · 계획 확인 화면 표시 보완 (2026-10-26)

## 결론

- 영어 화면에서 일반 문장 「The request could not be completed … (itinerary_infeasible)」로 나오던 등록 거절을 전용 영어 문장으로 바꿨습니다. 한국어 화면은 서버 문장(「모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요」)을 그대로 씁니다.
- 계획 확인 화면에서 서버 review의 `date` 줄(✕)은 항목 이름이 비어 「✕ (빈칸)」으로 보이고, 영어 화면에서도 한국어 문장이 그대로 나왔습니다. 이제 「날짜 / Date」 이름이 붙고, 영어 화면에서는 영어 문장으로 보입니다(카드 줄 · 「확인 필요」 칩 · 멈춘 카드 질문 · 지도 핀 안내).
- 검사 결과: develop 기준 lint · typecheck · Vitest 1189/1189 = 100% · build 모두 exit 0이고, `npm run check`도 exit 0입니다. role-manager 기준은 Vitest 1129/1129 = 100%이고 나머지 단계와 `npm run check`도 exit 0입니다. 새 시험 14/14 = 100%는 수정 전 role-manager 원본에서 11/14 실패(RED)했습니다.
- 배포 · push · 서빙 교체는 하지 않았습니다. 원격 0/2, x600 미반영, 로컬 서빙(3100) 미반영 상태입니다.

## 산출물

| 대상 | patch | SHA256 | 적용 기준 |
|---|---|---|---|
| develop | `web-allpast-refusal-develop.patch` | `2e371709013c4c945a5204521cd46affead23c118f5e1a73538d6bca5a2e594d` | `d2ab93a65e127e03154af535654bada0d9383d90` |
| role-manager | `web-allpast-refusal-role-manager.patch` | `3a30b30b588b25693ad3d12122670a24668839eb4374758355d4594f845af9e9` | `08b99597633a9d1e8e858bc03705314b927a6775` |

- 두 patch는 각자 기준 커밋 트리에 `git -c core.autocrlf=false apply --cached`로 적용했습니다(임시 index 사용). 적용 뒤 바뀐 파일 8/8 = 100%의 blob 해시가 시험한 작업트리 파일과 같습니다.
- 서로 다른 브랜치에는 적용되지 않습니다(`intake-review.ts`·`model.ts` 등의 문맥 차이). 그래서 브랜치마다 patch를 따로 만들었습니다.
- 검사가 끝난 뒤 다시 만든 diff의 SHA도 위 값과 같습니다. 검사 중 소스는 바뀌지 않았습니다.

## 변경 (두 브랜치 공통 내용, 6개 소스 + 새 시험 2개)

| 파일 | 변경 |
|---|---|
| `src/lib/live/error-text.ts` | `ALL_PAST_TEXT`(ko = 서버 문장 원문, en = "Every stop is before today. Please check the trip dates.")를 추가했습니다. `REFUSAL_TEXT.itinerary_infeasible`는 `violations[].code === "all_dates_in_past"`이면 이 문장을, 아니면 이 코드의 일반 문장을 씁니다. `checkLineText(line, t)`도 추가했습니다 — `date` 줄이 서버 문장과 같을 때만(공백과 끝 마침표는 무시) 영어로 바꾸고, 그 밖의 줄은 서버가 쓴 그대로 둡니다 |
| `src/lib/live/client.ts` | **변경하지 않았습니다.** `refusal()`은 이미 `refusalSentence(code, message, detail, language)`에 detail(violations 포함)을 넘깁니다. 그래서 표에 코드를 추가하는 것만으로 고쳐집니다. 실제 `Response`로 `refusal()`을 부르는 시험을 추가했습니다 |
| `src/lib/live/intake-review.ts` | `ItemRow`에 `"date"`를 추가했습니다(타입만) |
| `src/features/plan-check/model.ts` | `CheckKind`에 `"date"`를 추가했습니다(타입만) |
| `src/features/plan-check/parts.tsx` | `kindLabel`에 `date: 날짜 / Date`를 추가했습니다. `Checks`의 줄 문장은 `checkLineText`를 거칩니다 |
| `src/features/plan-check/stop-questions.ts` | 멈춘 카드 질문의 이유(`why`)가 `checkLineText`를 거칩니다 |
| `src/features/plan-check/map-description.ts` | 지도 핀·경로 안내(`firstIssue`)가 `checkLineText`를 거칩니다 |
| 새 시험 `src/lib/live/all-past-refusal.test.ts` (7건) | `refusal()`의 ko/en 결과, detail 보존, 일반 itinerary_infeasible과 구분, 문장표의 존댓말, `checkLineText`가 모르는 줄을 그대로 두는지 |
| 새 시험 `src/features/plan-check/all-past-dates.test.ts` (7건) | 서버 `admission_dates` 모양의 review로 `reviewResultOf`를 만들고 확인합니다: 각 카드의 `date`/`bad` 줄, ko·en 렌더(SSR), NeedsLine 칩, `placeQuestion` 질문, `stopToast` 안내, 다른 줄을 지어내지 않는지 |

## 검증 (Node `cache/scratch/cs-web-response-status/node.exe` v24.10.0)

- node_modules: 공유 서빙 폴더의 node_modules는 symlink 사슬로 다른 작업 폴더를 가리킵니다. 그래서 쓰지 않았습니다. 대신 lockfile(`640c2db5…`, 두 브랜치 같음)로 각 작업트리에 `npm ci`를 했습니다. npm은 `date_risk_node24_official`의 npm-cli.js, cache는 내 폴더를 썼고 전역 설정은 바꾸지 않았습니다. `unrs-resolver` postinstall은 npm allowScripts 경고로 실행되지 않았지만 lint는 통과했습니다.
- 실행 root는 매 실행 첫 줄(`evidence/check-*/meta.txt`의 `WALLPAST_RUN_ROOT`)에 남겼습니다. HEAD도 기록했습니다.

| 단계 | develop (d2ab93a65) | role-manager (08b995976) |
|---|---|---|
| lint (`eslint .`) | exit 0 | exit 0 |
| typecheck (`tsc --noEmit`) | exit 0 | exit 0 |
| Vitest | 1189/1189 = 100% (132 파일, skip 0) | 1129/1129 = 100% (128 파일, skip 0) |
| build (`next build`) | exit 0 | exit 0 |
| `npm run check` 전체 | exit 0 | exit 0 |
| 새 시험 | 14/14 = 100% | 14/14 = 100% |

- RED: 수정 전 role-manager 원본에 새 시험 2개만 넣고 돌렸을 때 11/14 실패했습니다(`evidence/red-rm-pristine.log`). 실제 렌더에서 `<b class="_checkKind_…"></b>`(빈 이름)와 영어 화면의 한국어 문장을 확인했습니다.
- 실패한 시도 보존: `evidence/check-*-attempt1-npmpath`는 npm-cli 경로를 MSYS 경로로 넘긴 runner 오류입니다. `evidence/check-rm-attempt2-junction-turbopack`은 rm의 node_modules를 dev로 junction해서 Turbopack이 root 밖의 next를 거부한 것입니다. 둘 다 환경 오류이고 제품 결함이 아닙니다. 고친 뒤 처음부터 다시 실행했습니다.
- 모델 · E4B · DB · live API(8042) · 프런트(3100)는 호출하지 않았고 건드리지도 않았습니다. 그래서 lease 획득은 0회입니다.

## 남은 한계 (되돌릴 수 있는 기본값으로 두었습니다)

1. **멈춘 카드의 선택지**: 전부 과거인 계획은 모든 카드가 `review`입니다. 그래서 C안 흐름은 첫 카드에서 멈추고 「확인이 필요해요 — 모든 일정이 오늘 이전이에요… 어떻게 할까요?」라고 묻습니다. 그런데 선택지는 기존대로 **다른 장소 후보(A·B·C)**입니다. 장소를 바꿔도 날짜 문제는 풀리지 않으므로 날짜 수정이나 여행 날짜 바꾸기로 안내하는 것이 맞아 보입니다. 다만 화면 흐름을 바꾸는 설계 결정이라 이번에는 현재 동작을 유지했습니다(문구만 맞춤). 결정이 필요합니다.
2. **실제 화면 미확인**: SSR 렌더 단위 시험과 production build까지만 확인했습니다. 실제 브라우저 화면과 실서버 응답은 확인하지 않았습니다.
3. 영어 변환은 서버 문장과 정확히 맞을 때만 일어납니다. 서버가 문장을 바꾸면 영어 화면에 한국어 원문이 다시 나옵니다(시험이 그 경우를 「지어내지 않음」으로 고정). 서버가 줄에 코드(`code: all_dates_in_past`)를 함께 보내면 문장 일치에 기대지 않아도 됩니다. 서버와 협의할 항목입니다.
4. 일반 `itinerary_infeasible`(휴무 등)의 영어 문장도 새로 생겼습니다. 한국어 화면은 기존 규칙을 따릅니다: 서버 문장이 존댓말이면 그대로, 아니면 표 문장입니다. 예전에는 둘 다 「요청을 처리하지 못했어요 (itinerary_infeasible)」였습니다.
5. 원본 wiki/index에 한 줄을 남기는 일은 하지 않았습니다(이번 작업은 새 보고서 추가만 허용). 부모 몫입니다.
