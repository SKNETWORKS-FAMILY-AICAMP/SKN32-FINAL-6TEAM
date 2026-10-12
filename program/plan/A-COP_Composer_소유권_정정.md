# Composer 소유권 정정 — sample이 만들고 UI가 가져다 쓴다

작성 2026-08-24. 사용자 결정에 따른 정정 문서다.

## 왜 이 문서가 필요한가

여러 세션이 같은 질문에서 반복해서 틀린 답을 냈다. 원인은 기존 v3 설계 문서에
Composer의 **소유권**이 잘못 적혀 있기 때문이다.

이 문서가 그 부분의 정본이다. 충돌하면 이 문서를 따른다.

## 결정

**Composer 관련 기능은 `final_project_sample`에서 만든다. `final_project_ui`는 그것을
가져다 쓴다.**

UI가 Composer 로직을 처음부터 다시 만들지 않는다.

## 기존 문서의 무엇이 틀렸나

`A-COP_Composer_v3_설계_토글전용_UI이관.md`에 다음 두 대목이 있다.

§3 표
> `final_project_sample` — 이번 v3 UI 이관 설계의 **구현 대상이 아님**

§8.1
> `final_project_ui` — pip 패키지가 아니다. **아무것도 pip install하지 않아도 동작해야
> 하며**

이 두 문장이 "UI가 Composer를 자체 구현해야 한다"로 읽힌다. 그래서 세션마다
"UI에서 새로 만들자"는 결론이 나왔다.

## 무엇을 혼동했나

`final_project_ui/CLAUDE.md` §0.3의 원칙은 이것이다.

> 대상 프로젝트의 파이썬을 import 하지 않는다

여기서 **대상**은 `final_project_cs`다. 릴리스 대상 제품을 말한다.

`final_project_sample`은 대상이 아니다. Core 계약과 인프라를 먼저 검증하는 참고
구현체이고, 거기서 만든 것을 패키지로 배포하는 것이 원래 계획이다.

즉 원칙이 금지하는 것은 다음이다.

| 금지 | 이유 |
|---|---|
| UI가 `final_project_cs`의 Python을 import | 남의 프로세스 코드를 UI에서 실행하는 셈. 분리가 무너진다 |
| UI가 대상의 파일·DB를 직접 수정 | 대상 프로세스 밖에서 쓰면 검증·감사를 우회한다 |

원칙이 금지하지 **않는** 것은 다음이다.

| 허용 | 이유 |
|---|---|
| UI가 sample에서 만든 패키지를 import | sample은 대상이 아니다. 공용 라이브러리를 쓰는 것과 같다 |
| UI가 대상의 인증된 HTTP API를 호출 | §0.3이 명시한 예외 |

## 정정된 구조

```
final_project_sample  (개발 저장소)
   │
   ├── acop_basement    → cs가 pip install. Core/Team/Registry/Controller
   ├── acop_composer    → 대상 쪽 glue. 관리용 빌드에만 설치
   └── acop_composer_ui → UI가 pip install. 판단·요청 로직
                            ▲
                            │ import
                   final_project_ui  (독립 서비스)
                            │
                            │ HTTP 호출만
                            ▼
                   final_project_cs  (릴리스 대상)
```

`acop_composer_ui`라는 이름은 예시다. 실제 패키지 이름은 §8.1의 명명 확정 때 정한다.

핵심은 **UI가 import하는 대상이 sample의 산출물이지 cs가 아니라는 점**이다.

## 무엇이 바뀌고 무엇이 그대로인가

| 항목 | 변경 |
|---|---|
| Composer 로직을 누가 만드나 | UI가 자체 구현 → **sample이 만들고 UI가 import** |
| UI가 cs의 Python을 import하나 | 안 한다 (그대로) |
| UI가 대상 파일을 직접 쓰나 | 안 한다 (그대로) |
| 쓰기는 어디서 실행되나 | 대상 프로세스 안 (그대로) |
| 인증·scope·감사 | 그대로 |

원칙은 하나도 깨지지 않는다. 바뀌는 것은 **같은 코드를 두 번 만들지 않는다**는 점뿐이다.

## 왜 이 방향이 맞나

Composer 판단 로직을 UI가 자체 구현하면 다음이 생긴다.

- sample에 이미 있는 것과 같은 코드를 UI에 다시 만든다
- 계약이 바뀌면 두 곳을 고쳐야 한다
- 두 구현이 어긋나면 어느 쪽이 맞는지 알 수 없다

sample에서 만들어 배포하면 계약이 한 곳에만 있다. 이것이 §8.1이 말한
"개발은 전부 `final_project_sample` 한 저장소에서 진행하되 배포만 나눈다"의 취지와도
맞는다. 그 취지를 UI 쪽 패키지까지 확장하는 것이다.

## 후속 조치

1. `A-COP_Composer_v3_설계_토글전용_UI이관.md` §3 표와 §8.1을 이 문서에 맞게 고친다.
2. `final_project_ui/CLAUDE.md` §0.3에 "대상은 cs를 말하며 sample 패키지 import는
   금지 대상이 아니다"를 명시한다.
3. UI가 import할 패키지의 이름과 경계를 §8.1 명명 확정 때 함께 정한다.

이 세 가지가 끝나기 전에는 세션마다 같은 혼동이 반복된다.
