# 2026-10-26 Comment9 고객 화면 갱신 — revalidate 리허설·적용 절차

- 작성: 2026-10-26 02:25 KST, 하위 작업자(Opus). 후보 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/comment9-revalidate-rehearsal-20261026-011446-25219` (원문 `REPORT_KO.md`, 증거 `evidence/`).
- 대상: 실고객 접수 27107a20…(rev2, 북촌 2026-11-02 10:00–11:30) — 읽기 전용 구조 조회만, 변경 0. 관련 수정: [Comment9 방문제한](2026-10-25_comment9-visit-time-restriction.md).
- 문서 수정: 이 보고서 신규만. wiki 계약·index 수정 0. 코드 원본 수정 0. live 8042·3100 kill/재시작 0, push 0.

결론: **정상 경로(POST …/revalidate)로 0-6 경고가 사라지는 것을 비교 DB에서 재현했습니다(closed warn → ok, 판 2 유지).**
다만 ① 현재 live(v7a)에는 Comment9 수정이 없어 지금 갱신해도 경고는 그대로이고, ② 고객 화면을 다시 여는 것만으로는 갱신되지 않으며,
③ 운영자가 대신 갱신할 정상 경로가 없고 D-024 기준으로도 하면 안 됩니다. ④ 갱신해도 이 접수는 **ready=false 그대로**입니다(0-8 창덕궁이 2026-11-02 월요일 휴무 bad — Comment9와 무관한 정상 판정).
실고객 행 변경 0(전후 읽기 전용 대조 동일), live/프런트 kill·재시작 0, push 0, 실모델 추론 0.

## 1. 코드로 확정한 revalidate 동작 (v7a = live, v7a+Comment9 동일)
| 항목 | 사실 | 근거 |
|---|---|---|
| 경로 | `POST /v1/web/trip-intakes/{id}/revalidate`, 본문 `{"revision": n}`만(`extra="forbid"`, 다른 칸 422) | trip_api.py 1937(v7a)·`IntakeRevisionIn` 273 |
| 권한 | `_web_customer` = 고객 본인 자격만: 쿠키 세션(쓰기는 허용 Origin + 세션 HMAC `X-CSRF-Token` 둘 다), 사용자 키, 에이전트 키, 개인 AI 위임. 관리자 경로·운영자 대리 경로 없음(호출처 1곳) | web_cookie.py 210–290 |
| 소유 | `trip_intakes WHERE tenant AND intake AND customer` — 남의 접수 404, 상태≠review 409, 판 불일치 409 `stale_revision` | pipeline.current_review 1023 |
| 바뀌는 것 | `intake_reviews`(그 판 1행) payload 재계산 UPSERT·`built_at=now()`; 배경 작업: 식사 재판정(`rejudge`, E4B), 대안 미리 준비(`prepared.prepare`, `intake_alternatives`), 위험 점검 fresh(외부 날씨 — live 정책상 차단) | review.ensure 1176, trip_api 1946–1949 |
| 안 바뀌는 것 | `trip_intakes`(status·revision·updated_at 포함), `intake_claims`(원문 해석·고객 선택·경로 선택), `intake_sources`(원문), 다른 판 검사, 설문 답 | FOR UPDATE 잠금만, UPDATE 없음 |
| 재열람(GET) | `ensure(force=False)` → 같은 판 저장본 반환. 운영시간/휴무 재계산 없음. 식사 판정 기한 초과 시 실패 표시만 저장할 수 있음 | review.ensure·dining_review.refresh |
| 고객 버튼 | 「다시 제출」(하단): 고객이 고친 것이 있을 때만 동작, 아니면 `확인이 필요한 항목 n건` 이유만 표시. 「다시 확인」(위험 점검 칸): `risk_panel` 켜졌을 때만 — live `GET /v1/web/features` = `risk_panel:false` | result-parts.tsx 150–158, plan-check.tsx 1978(live 3100 소스 동일) |

## 2. 비교 DB 리허설 (gugu_replay_improved_20261025, 새 tenant `c9reval_8fbdade933c8`)
- 합성 접수: 실고객과 같은 구조(9항목, 11-01~02, 0-6 북촌 126537 10:00–11:30, rev1 50행형 claim + rev2 고객 선택 5행; 원문은 합성). 관광공사 사실값은 비교 DB demo에서 새 tenant로 복사.
- v7a(live 코드)로 정상 GET → 저장 rev2 검사: 9항목 줄 결과가 실고객 rev2와 일치(0-6 `closed=warn`, 0-8 `closed=bad`, needs 1, ready false). 차이: 실고객의 식사 `dining_check` 줄 2개는 합성에 없음.
- 같은 v7a 코드로 revalidate(대조): 200, 0-6 **여전히 warn** → 스왑 전 갱신은 무의미.
- v7a+Comment9(3파일 LF 적용, 정규화 후 v8 postimage와 3/3 동일):

| 단계 | HTTP | DB(접수) |
|---|---|---|
| 1 고객 재열람 GET | 200, 0-6 warn 유지(payload built_at 불변) | 검사 payload 재계산 없음(식사 판정 기한 초과 기록만 저장) |
| 2a 다른 고객 쿠키 | 404 not_found | 불변 |
| 2b CSRF 없음 / 2c 잘못된 Origin | 403 csrf_failed / 403 | 불변 |
| 2d 낡은 판(1) | 409 stale_revision(current 2) | 불변 |
| 2e 자격 없음 | 401 | 불변 |
| 2f 추가 칸 `force` | 422 | 불변 |
| 3 본인 쿠키+CSRF+Origin, revision 2 | 200, **0-6 hours ok·closed ok**(문구 「쉬는 요일이 없어요 · ※ 방문 제한시간…」), 0-8 bad 유지, ready false, needs 1 | intake_reviews rev2만 갱신, intake_alternatives +6, trip_intakes·claims·sources 해시 동일 |
| 4 다시 GET | 200, ok 유지 | 불변 |

- 차단·호출: revalidate 1회당 식사 재판정 E4B 호출 시도 2회(배경, 리허설에서는 차단), 외부 날씨 6회 차단(live도 차단 정책). 메타데이터 GET만 허용, lease 보유 중 실행 후 반환.
- 실행 오류 보존: 첫 revalidate 실행은 프로세스마다 합성 비밀키가 달라 CSRF HMAC 불일치로 전부 403 → `<후보>/evidence/revalidate-result-run1-csrf-secret-mismatch.json`. 기존 쿠키로 `POST /v1/web/auth/session`(웹 로드와 같은 경로, 새 세션 아님)에서 토큰을 다시 받아 재실행.

## 3. 적용 선택지
| 선택지 | 가능 여부 | 근거 |
|---|---|---|
| A 고객 재열람 시 자동 | **현재 코드로 불가.** 하려면 제품 변경(저장 검사에 운영시간/휴무 규칙 버전 서명 → 다르면 재열람 때 같은 판 재계산) + 시험 + 배포 | 리허설 단계 1. 읽기 경로를 잠그지 않는 ST4F-731 결정과 충돌 여부 검토 필요 |
| B 고객 버튼/조작 | **가능(권장).** 이 고객은 0-8을 고치면(수정·전체 자동 추천 → 새 판, 새 코드로 전체 재계산 — 코드 근거, 새 판 경로는 리허설 미실행) 0-6도 함께 갱신. 고친 것이 있으면 「다시 제출」이 revalidate. 고친 것 없이 누를 버튼은 `risk_panel` 켤 때 「다시 확인」뿐 | 코드·live features |
| C 운영자 대신 갱신 | **불가.** 운영자 자격 경로가 없어 고객 세션·키를 가장하거나 DB에 직접 써야 함. D-024 「운영자는 답변·상태·담당 기록만, 고객 일정은 대신 고치지 않는다」, cs AGENTS 「고객 대신 문제를 직접 고치는 운영 관리자 역할을 만들지 않는다」 위반. revalidate는 판·원문은 안 바꿔도 고객 화면 검사·대안·식사 판정과 모델 호출을 바꾼다 | D-024(team/develop d2ab93a6), trip_api·web_cookie |

## 4. 실제 적용 절차 (부모 전용, 승인 후)
1. live v7a에 Comment9 3파일 통합: `tr -d '\r'`로 정규화한 patch를 `git -c core.autocrlf=false apply`(preimage 3/3 = v7a). v8 후보 postimage는 CRLF라 바이트 SHA가 다름(내용 동일) — 줄끝 정책을 정해 동결.
2. 동결·lease 확보 후 정식 `--preflight` RC0 → 부모만 스왑. rollback = 현재 v7a launcher.
3. 읽기 전용 확인: 실고객 `intake_reviews` rev2 `built_at=2026-10-25 19:27:01.66` 그대로(정상 — 자동 갱신 없음).
4. 고객 안내(문의 답변 경로, D-024): 「0-8 창덕궁이 11/2 월요일 휴무입니다. 수정하시면 북촌 경고도 새 기준으로 다시 확인됩니다」. 고객이 고치고 「다시 제출」 → 고객 브라우저가 revalidate 호출. 운영자는 대신 호출하지 않음.
5. 그 시점 E4B 식사 재판정 2회가 배경으로 돎 — live 정책은 모델이 사용 중이면 거절(`local_model_busy`)하고 판정 unknown으로 남김(지금과 같음).
6. 읽기 전용 수락: 새 판(또는 같은 판) 검사에서 0-6 `closed=ok`, claims·sources 해시 불변(revalidate만 한 경우 revision 2·updated_at 불변), 같은 화면을 읽기 전용으로 확인.

## 5. 사용자 결정 필요
1. 적용 방식: B(고객 조작, 기본안) / A(재열람 자동 갱신 제품 변경) / 운영 스위치 `risk_panel` 켜서 고객에게 「다시 확인」 버튼 노출(전체 고객 화면 영향).
2. C를 원하시면 D-024를 바꾸는 새 결정(「판·원문 불변 유지보수 재검사」 허용 범위와 고객 고지)이 먼저 필요합니다. 현재는 불가로 판단했습니다.
3. Comment9 통합본 줄끝(LF/CRLF) 기준.

## 산출물
- `phase_seed.py`·`phase_revalidate.py`·`c9common.py`·`run_with_lease.sh` — 정상 API 리허설(자체 root 변수 `C9R_SOURCE_ROOT`, 실행 root 출력)
- `<후보>/evidence/seed-result.json`·`revalidate-result.json`(+run1 실패본)·`seed-1.log`·`revalidate-1/2.log`
- `<후보>/evidence/customer-*-readonly*` — 실고객 구조 읽기 전용(값·원문 제외), 전후 동일
- `src-v7a`, `src-v7a-c9` — v7a 사본과 Comment9 적용본(제품 원본 수정 없음)
- 비교 DB 잔여: tenant `c9reval_8fbdade933c8`(합성 접수 2, 게스트 2, places 8, 카탈로그 복사 6). 다른 tenant/demo 쓰기 0.
