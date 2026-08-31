# A-COP 남은 작업 인수인계

작성 2026-08-24. 데이터셋과 문서 정리를 마친 시점의 기록이다.

## 이 문서를 왜 쓰나

작업이 여러 세션에 나뉘어 진행된다. 다음 세션이 무엇을 이어받아야 하는지, 앞선
세션에서 무엇이 확인됐고 무엇이 미확인인지 적어둔다.

세션이 바뀌면 앞의 맥락이 사라진다. 그래서 "무엇을 해야 한다"만 적지 않고 "왜
그래야 하는지"와 "어디까지 확인됐는지"를 함께 적는다.

## 완료된 것

| 항목 | 결과 | 커밋 |
|---|---|---|
| 쿠팡 주문 수집 확장 | 외부에서 5.4.6 완성. 테스트 45개 통과 | `ba92831` |
| 개인정보 파일 정리 | 세션 파일·스크린샷·조사 산출물 삭제 | (git 미추적 파일이라 커밋 없음) |
| 데이터셋 문서 연결 | 루트 `CLAUDE.md`에 `datasets/` 절 추가 | `5601c7d` |
| 택배조회 REPORT | `datasets/commerce/courier_tracking/REPORT.md` | `5601c7d` |
| 네이버 주문 REPORT | `datasets/commerce/naver_order_history/REPORT.md` | `5601c7d` |
| Composer 범위 재검토 | 토글 전용으로는 요구 미충족. 카탈로그 기반 CRUD와 선언형 Team 권고 | `f2b2049` |
| Composer 소유권 정정 | sample이 만들고 UI가 가져다 쓴다 | `f2b2049` |
| 비전 항목 3건 등록 | VISION-10 3층, VISION-11, VISION-12 | `f250d07` |
| 확장 추천 등록 | VISION-13. 자기 관측 기반은 이미 신호가 있다 | `fe7fdad` |
| v3 문서·UI 원칙 정정 | 정정 안내 삽입, "대상"의 뜻 명시 | (이번 커밋) |

## 남은 작업

### 1. 원격 저장소 연결 (사람이 해야 함)

`workspace` 브랜치에 원격 추적이 설정돼 있지 않다.

```bash
git push -u origin workspace
```

AI 세션은 푸시를 실행하지 않는다. 사용자가 직접 실행한다.

### 2. VOC 데이터 전처리 (모델링 세션)

Core 1의 Context Broker가 쓸 RAG 지식 재료다. RAG는 질문에 답하기 전에 관련 자료를
찾아 읽는 방식을 말한다. 그 읽을 자료가 아직 원본 상태다.

| 데이터셋 | 원본 크기 | 전처리 |
|---|---|---|
| `voc/aihub_71844_llm_instruction_tuning` | 209M | 없음 |
| `voc/aihub_102_smb_order_qa` | 189M | 없음 |
| `voc/nikl_ne_2022` | 137M | 없음 |
| `voc/aihub_30716_callcenter_qa` | 83M | 없음 |
| `voc/aihub_71603_aspect_sentiment` | 63M | 없음 |

각 폴더의 `REPORT.md`에 데이터 성격이 적혀 있다. 전처리 결과는 `processed/`에 넣고
`datasets/README.md`의 폴더 규칙을 따른다.

**주의**: `commerce/courier_tracking`은 전처리 대상이 아니다. 학습 데이터가 아니라
실행 시점에 호출하는 도구다. `processed/`가 비어 있는 것이 정상이다.

★**2026-09-01 갱신 — 택배 제출본은 합쳤다.**
`courier_tracking/scripts/merge_incoming.py` 로 `raw/_incoming_20260829/` 를
`processed/` 로 합쳤다.

| 파일 | 건수 | 비고 |
|---|---:|---|
| `processed/tracking.jsonl` | **236** | 네이버 API 조회분. 이력 있는 건 49 |
| `processed/tracking_coupang.jsonl` | **1,782** | 쿠팡 화면 수집분. 이력 있는 건 67 |

★**두 형식을 한 파일에 섞지 않았다.** 쿠팡 쪽 `status` 는 네이버 스키마의 enum 이
아니라 "8/2(금) 도착" 같은 화면 문구이고 `level`·`complete`·`courier_code` 가
없다. 섞으면 "배송 상태" 의 뜻이 두 가지가 되므로 파일과 스키마를 나눴다
(`tracking_coupang_schema.json`). 둘 다 스키마 검증 **위반 0건**.

앞서 적었던 "질의 238건 · 이력 50건" 은 **질의 수**이고, 합친 뒤 236·49 는
**송장 수**다(송장번호 중복 59건을 합쳤다 — 대부분 기존 57건과 cyw 제출분이 같은
조회다). 쿠팡 넉 장은 서로 겹치는 건이 하나도 없었다.

★쿠팡 1,782건 중 이력이 남은 건 67건뿐이다 — 화면이 배송 완료 후 이력을 감춘다.
**없는 것을 "조회 실패" 로 읽으면 안 된다.**

남은 것은 파일명 규칙뿐이다 — `naver_tracking_2026-08-21_kjh` 만 확장자가 없다
(스크립트는 확장자가 아니라 내용으로 형식을 판별하므로 지금도 합쳐진다).

### 3. 네이버 주문 4건 누락 수정 (코드 세션)

★**2026-08-31 갱신.** 아래 "72건 중 68건"은 첫 수집분 한 사람(cyw) 기준이다.
그 뒤 팀원 세 명이 자기 계정에서 모은 것을 받아 2026-08-29에 함께 정규화했고,
지금 `processed/orders.jsonl`은 **270건**이다(cyw 68 · kjh 101 · syh 44 · csw 57).
kjh 제출본은 파일명이 `102건`인데 실제로는 101건이므로 파일명을 믿으면 안 된다.

나머지 세 명분은 각자의 실제 주문 수와 대조하지 않았다. 같은 크롤러로 받았으므로
같은 누락이 있을 가능성이 높지만, 확인된 것은 cyw분 4건뿐이다.

실제 주문 72건 중 68건만 수집됐다. 빠진 주문번호는 다음과 같다.

```
2022043085163701
2023051853027171
2023090698394101
2024032354706671
```

원인은 확인됐다. 목록 화면의 카드 하나에 주문이 여러 개 들어 있는 경우가 있는데,
크롤러가 카드마다 주문을 하나씩만 읽는다.

고치는 방향은 카드 단위가 아니라 주문 상세 링크 단위로 순회하는 것이다. 자세한
페이지별 수치는 `datasets/commerce/naver_order_history/REPORT.md`에 있다.

세션 파일을 지웠으므로 다시 수집하려면 로그인부터 해야 한다.

### 4. Composer 범위 재검토 (설계 세션)

운영 UI에서 팀 모듈과 GraphStore 같은 기능을 넣고 빼고, 인스턴스를 이름과 설정만
입력해 만들 수 있어야 한다는 요구가 있다.

기존 v3 설계 문서(`A-COP_Composer_v3_설계_토글전용_UI이관.md`)는 범위를 "켜고 끄기"로
좁혔는데, 이는 요구를 충족하지 못한다.

현재 `final_project_cs`에는 `/current`, `/validate`, `/apply`, `/toggle` 이 모두 있다.
v2(전체 선언 적용)와 v3(토글)가 공존하는 상태다.

재검토를 마쳤다. 결과는 `A-COP_Composer_범위재검토.md`에 있다.

남은 것은 구현이다. 순서는 다음과 같다.

1. 선언형 Team 실행기(`DeclarativeTeamRuntime`) 배포
2. Composer 인스턴스 CRUD 계약 확정
3. 카탈로그 HTTP 조회
4. UI 선택 생성 화면

앞의 것이 없으면 뒤의 것을 만들어도 동작하지 않는다. 근거는
`final_project_sample/docs/vision/VISION-10_예제_카탈로그_스캐폴딩_CLI.md` 3층이다.

> ★**2026-09-01 갱신 — 네 단계 모두 끝났고, 그 위에 두 가지가 더 붙었다.**
>
> | 단계 | 어디 |
> |---|---|
> | 1 선언형 Team 실행기 | `acop_basement/teams/declarative.py` (읽기 전용 tool 만 허용하는 grant ceiling 포함) |
> | 2 인스턴스 CRUD 계약 | `POST /composer/changes` (`acop_composer/api.py`), 계약 `docs/handoff/13` |
> | 3 카탈로그 HTTP 조회 | `GET /composer/catalog` |
> | 4 UI 선택 생성 화면 | `final_project_ui` `/composer` 의 "인스턴스 만들기(카탈로그)" |
>
> 그 뒤에 더해진 것:
>
> - **중앙 설정 저장소**(2026-08-30) — 대상마다 Composer 를 심지 않고 한 곳에서
>   수천 대상의 선언을 다룬다. 결정 `A-COP_Composer_중앙설정저장소_결정.md`.
>   UI 는 `direct`/`central` 두 방식을 프로필로 고른다
> - **재기동 없는 반영**(2026-08-31) — `POST /admin/reload`(scope `ops:reload`)와
>   `active_revision`/`desired_revision`/`reload_state`(introspection 계약 1.1).
>   그 전에는 저장 직후 반영도 안 됐는데 새 revision 을 보고하고 있었다.
>   구현·실측 `final_project_sample/docs/reports/2026-08-31_reload_계약_구현.md`

## 확인하지 못한 것

정직하게 적는다. 아래는 미확인이거나 다른 세션의 결과를 봐야 하는 항목이다.

| 항목 | 상태 |
|---|---|
| 쿠팡 배송이력 5건 중 4건만 수집 | 5.4.6에서 해결됐는지 미확인. `normalize.py` 실행 결과는 배송 4행 |
| `implementation_ref` 의 allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용된다 |
| v2 계약 문서 | 다른 세션에서 작업 중이라 열지 않았다. endpoint 이름·`config_revision`·인증 scope·감사 필드를 최종 계약에서 하나로 맞춰야 한다 |

### 5. UI가 import할 패키지 이름 확정 (설계 세션)

`A-COP_Composer_소유권_정정.md`의 후속 조치 세 가지 중 둘은 끝냈다. v3 문서 정정과
UI 원칙 명시다.

남은 하나는 **UI가 import할 패키지의 이름과 경계 확정**이다. 정정 문서에서는
`acop_composer_ui`를 예시로 썼으나 실제 이름은 정해지지 않았다.

이것은 `A-COP_Composer_v3_설계_토글전용_UI이관.md` §8.1의 명명 확정 때 함께 정한다.
endpoint 이름, `config_revision`, 인증 scope, 감사 로그 필드도 같은 자리에서 하나로
맞춘다.

## 참고 문서

| 문서 | 내용 |
|---|---|
| `program/plan/A-COP_구현계획서_v8.md` | 전체 계획. Core 1/Core 2 구조는 §8 |
| `datasets/README.md` | 데이터 폴더 규칙 |
| 각 데이터셋의 `REPORT.md` | 그 데이터가 무엇이고 어디에 쓰이는지 |
| `CLAUDE.md` (루트) | 작업 기준선. 데이터 폴더 절 포함 |
