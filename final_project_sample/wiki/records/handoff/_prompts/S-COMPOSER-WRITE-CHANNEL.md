# 검토 의뢰 — Composer 의 "쓰기" 를 릴리즈 이후에는 어떻게 하나

## 0. 배경 — 내가 놓친 것

오늘 개발 콘솔(대시보드·quality·experiments·runs·admin)을 이 저장소에서 전부 지우고
별도 프로그램 `final_project_ui` 가 read-only 로 담당하게 했다.
근거는 그 프로그램 자신의 규칙:

> §0.3 — **"대상을 쓰지 않는다. 이 프로그램은 read-only 다."**
> §0.2 — **"대상의 검증 모델을 가져오지 않는다 ... 그 순간 포크가 시작된다."**

Composer(`/ui/composer`, `config/project.yaml` 을 검증·저장)는 **쓰기**라서
저 원칙과 안 맞아 제품(`final_project_sample`)에 남겼다.

★그런데 이게 **반쪽 답**이었다. 사용자 지적:

> 그 컴포저 나중에 릴리즈 때 분리할 건데 그 이후에는 어떻게 작업하게?
> 이거에 대한 대안도 마련해야지?

즉 "지금은 제품 안에 두면 된다" 는 **개발 중** 답이다.
**릴리즈된 인스턴스**에서 우리가 나중에 점검·보수하러 콘솔을 다시 붙일 때
(이게 애초에 콘솔을 분리하자고 한 이유 — "점검및보수를 해야 할 때만 로컬에서
개발 콘솔 다시 붙여서 작업") **모듈을 켜고 끄는 쓰기 작업**을 어떻게 하나?

## 1. 지금 상태

```
config/project.yaml          제품이 소유. ProjectConfig 로 검증(app/core/project_config.py)
app/presentation/ui/composer.py   HTML 폼. 검증 통과해야 저장(같은 프로세스 안에서)
GET /introspection            신설. scope ops:introspect. 조립 상태를 JSON 으로 읽기만
final_project_ui              별도 프로그램. read-only. 파일·DB·introspection 을 읽는다
```

`/introspection` 은 **읽기**만 해결했다. **쓰기 채널이 없다.**

## 2. 내가 지금 생각하는 방향 (검토해 달라 — 동의만 하지 마라)

Composer 를 "HTML 페이지" 와 "쓰기 능력" 으로 쪼갠다.

```
basement (항상 존재, 제거 안 함)
  POST /composer/validate   후보 선언을 검증만 한다 (저장 안 함). 에러를 JSON 으로
  POST /composer/apply      검증 통과 시 config/project.yaml 에 실제로 쓴다

제품 개발용 (릴리즈에서 뺄 수 있음, 지금의 /ui/composer)
  HTML 폼 — 위 두 엔드포인트를 **같은 프로세스 안에서** 호출하는 것 중 하나일 뿐

final_project_ui (릴리즈 이후 우리가 붙이는 것)
  자기 화면에서 폼을 그리고, 위 두 엔드포인트를 **HTTP 로** 호출한다
```

★핵심: **검증 로직(`ProjectConfig`)은 여전히 제품 안에만 있다.** 콘솔은
`ProjectConfig` 를 import 하지 않는다 — raw YAML/dict 를 보내고, 제품이 검증해서
에러를 JSON 으로 돌려줄 뿐이다. "포크" 가 아니다.

★`final_project_ui` 의 "read-only" 원칙은 완전히 버리지 않는다 — **"대상의 파일을
직접 조작하지 않는다. 대상이 스스로 선언한 쓰기 API 를 통해서만, 대상이 검증한다"**
로 좁혀 다시 쓴다. 임의 쓰기가 아니라 **제품이 소유·검증하는 단일 통로**로 제한된다.

## 3. 물어보는 것 — 반박해 달라

1. ★이 분리(basement 에 API, 제품에 HTML 폼, 콘솔이 API 를 호출)가 맞는 방향인가?
   더 나은 대안이 있나 — 예를 들어 **릴리즈에서도 Composer HTML 페이지를
   안 빼는 것**(운영 중 잠깐 켜서 쓰는 방식)은 왜 안 되나, 또는 왜 되나?
2. ★쓰기 API 를 열어 두면 그 자체가 공격 표면이다. **어떻게 잠그나?**
   - scope 는? (`ops:introspect` 와 분리해야 하나?)
   - 릴리즈된 인스턴스에서 **기본은 꺼져 있어야** 하나? (모듈 토글처럼)
   - `final_project_ui` 가 이 API 를 호출할 때 그쪽에서 추가로 확인해야 할 것은?
3. **동시 편집** — 콘솔에서 쓰다가 그 인스턴스의 로컬 Composer 도 동시에 쓰면?
   revision(P1 에서 만든 구성 해시)으로 낙관적 동시성을 걸어야 하나?
4. ★**멀티 인스턴스**(수십·수백 프로젝트) 에서 이 쓰기 API 를 어떻게 관리하나?
   콘솔이 "이 인스턴스에 쓰기를 허용할지" 를 어떻게 판단해야 하나 —
   사용자가 명시적으로 켜야 하나, 아니면 scope 보유만으로 충분한가?
5. **하지 말아야 할 것** — 이런 "원격 설정 쓰기" 기능에서 흔한 실수는?

## 4. 형식

`wiki/records/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md` 로 답하라.
**코드는 건드리지 마라.** 결론은 하나를 고르고 근거를 대라 — "상황에 따라 다르다" 금지.
