# 검증 요청 — Composer v3 전환, 지금 하면 무슨 일이 생기나

★**read-only 다. 아무것도 고치지 마라.** 사실 확인과 판단만 한다.

## 0. 이번엔 다른 폴더를 읽어도 된다 (사용자 허가받음)

평소와 달리 이번에는 아래를 **읽어도 된다**(쓰기는 금지):

```
C:\Users\playdata2\Documents\final_workspace\final_project_ui        (자기 자신)
C:\Users\playdata2\Documents\final_workspace\final_project_sample     (읽기만)
C:\Users\playdata2\Documents\final_workspace\final_project_cs         (읽기만)
C:\Users\playdata2\Documents\final_workspace\program\plan\A-COP_Composer_v3_설계_토글전용_UI이관.md
```

## 1. 배경

`final_project_ui` 의 Composer 화면은 지금 **v2 모델**이다 — 전체 config 를
편집해서 `validate`·`apply` 로 통째로 제출한다. 실제로 동작하고 테스트 98건이 있다.

그런데 새 설계 문서 `A-COP_Composer_v3_설계_토글전용_UI이관.md` 가 이걸
**토글 전용**으로 바꾸라고 한다(§6-5: "전체 JSON 편집, `validate_candidate`,
전체 `apply_candidate` … 제거하거나 토글 경로로 대체").

v3 는 대상에게 두 가지를 요구한다:
1. introspection 응답에 `registered_ids`(+ 토글 가능한 현재 상태)
2. `POST /composer/toggle` (`target_type`·`target_id`·`active`·`base_revision`·`reason`)

## 2. ★확인할 것 — 전부 코드를 열어서 확인하라, 문서만 믿지 마라

### 2-1. 대상이 v3 를 받을 준비가 됐는가 (가장 중요)
- `final_project_sample` 과 `final_project_cs` 각각에서:
  - introspection 응답에 **`registered_ids` 가 실제로 있는가?** 없으면 지금
    응답이 어떤 모양인지 적어라(`contract_version` 값도)
  - **`POST /composer/toggle` 라우트가 실제로 있는가?** 없으면 지금 있는
    Composer 라우트가 무엇인지 나열하라
- 새 패키지 `acop_composer` 가 있다면 그 안이 **v2 인지 v3(토글) 인지** 확인하라

### 2-2. 지금 UI 를 v3 로 바꾸면 무슨 일이 생기나
2-1 결과를 근거로 답하라:
- 대상이 아직 v2 뿐이라면, UI 만 v3 로 바꿨을 때 화면은 어떻게 되는가?
  (404? 빈 화면? 오동작?) — **추측하지 말고 코드 경로로 설명하라**
- 지금 동작하는 v2 흐름을 잃는가? 잃는다면 무엇을?

### 2-3. 순서 문제
- v3 문서 §6 의 8단계 중 **UI(4·5번) 보다 먼저** 되어 있어야 하는 것이
  실제로 되어 있는가? (1: 계약 확정 / 2: introspection 확장 / 3: cs endpoint)
- 안 되어 있다면, UI 를 먼저 바꾸는 것이 가능한가? 가능하다면 어떤 조건에서인가?

### 2-4. 되돌릴 수 없는 것이 있는가
- v3 로 바꾸면서 지우는 코드·테스트 중, 나중에 v2 가 다시 필요해질 때
  복구하기 어려운 것이 있는가?

## 3. 판단해서 답하라

★"상황에 따라 다르다" 는 금지. **당신의 추천을 하나 고르고 이유를 대라.**

선택지 예시(이것만 있는 건 아니다):
- (a) 지금 UI 를 v3 로 전면 전환한다
- (b) 대상(cs) 의 toggle endpoint 가 생긴 뒤에 UI 를 바꾼다
- (c) UI 에 v2·v3 를 **둘 다** 두고 대상의 `contract_version` 으로 분기한다
- (d) 지금은 v2 를 유지하고 v3 는 계획만 남긴다

각 선택지의 **비용과 위험**을 적고, 추천안을 고른 이유를 대라.

## 4. 하지 말 것
- ❌ 파일 수정 (read-only — sample·cs 는 특히 절대 쓰지 마라)
- ❌ 문서만 읽고 "되어 있을 것이다" 라고 추정 — **라우트·함수를 직접 찾아라**
- ❌ 회피성 결론

## 5. 출력 형식

★파일 만들지 말고 마지막 메시지로만:

```
## 사실 확인 (코드 근거 필수)
- sample introspection registered_ids: 있음/없음 — 파일:줄
- sample /composer/toggle: 있음/없음 — 파일:줄
- cs introspection registered_ids: 있음/없음 — 파일:줄
- cs /composer/toggle: 있음/없음 — 파일:줄
- acop_composer 의 계약 버전: v2/v3/없음 — 파일:줄

## 지금 UI 를 v3 로 바꾸면
(코드 경로로 설명)

## 순서 문제
(§6 선행 단계 실제 상태)

## 추천
- 선택: (a)/(b)/(c)/(d)/기타
- 이유:
- 위험:
```
