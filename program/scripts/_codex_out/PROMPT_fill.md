# 작업 — 계약 문서에서 빠진 내용을 찾아 wiki 보강안을 낸다

## 배경

`final_project_cs/docs/handoff/` 의 계약 문서를 wiki 로 옮겼는데,
절 단위로 대조해 보니 **100개 절 중 완전 반영이 31개뿐**이었다.
55개가 "일부" 였다 — 주제는 wiki 에 있는데 **필드 이름·제약·숫자가 빠져 있다.**

**계약은 필드 이름과 제약이 전부다.** 설명이 비슷하다고 반영된 게 아니다.

## 무엇을 하나

아래 원본 4건을 wiki 대응 문서와 대조해서 **빠진 것을 채우는 보강안**을 낸다.

| 원본 | wiki 대응 |
|---|---|
| `final_project_cs/docs/handoff/01_계약_Pydantic.md` | `program/final_project_cs/wiki/teams/team-contract/index.md` |
| `final_project_cs/docs/handoff/02_DB_스키마.md` | `program/final_project_cs/wiki/data/schema/index.md` |
| `final_project_cs/docs/handoff/03_REST_MCP_인터페이스.md` | `program/final_project_cs/wiki/external/rest-api.md` · `mcp-tools.md` |
| `final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md` | `program/final_project_cs/wiki/teams/index.md` |

## ★ 절대 하지 말 것

1. **원본을 고치지 마라.** 읽기만 한다.
2. **wiki 문서를 통째로 다시 쓰지 마라.** **추가할 절만** 낸다.
3. **원본에 없는 사실을 넣지 마라.** 필드 이름·타입·제약·숫자는 원문 그대로.
4. **이미 wiki 에 있는 것을 다시 넣지 마라.** 중복이 생긴다.
5. `build/`·`dist/`·`__pycache__`·`legacy/` 는 읽지 마라.

## 무엇을 채우나 — 이런 것들이다

- Pydantic 모델의 **필드 이름 · 타입 · 필수 여부 · 기본값 · 검증 규칙**
- DB 테이블의 **컬럼 · 타입 · UNIQUE · FK · NOT NULL · 인덱스**
- REST/MCP 의 **경로 · 메서드 · 요청/응답 필드 · 상태 코드 · scope**
- 모듈 목록의 **모듈 이름 · 의존 · 토글 가능 여부**

★**"이런 게 있다" 가 아니라 "정확히 이 이름과 이 제약" 을 적는다.**

## 출력 형식

wiki 문서마다 이렇게 낸다. **추가할 마크다운 절만** 낸다.

```
===== APPEND TO: final_project_cs/wiki/teams/team-contract/index.md =====
## 필드 전체 목록

`[실측]` `docs/handoff/01_계약_Pydantic.md` 에서 이관.

| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| ... |

===== APPEND TO: final_project_cs/wiki/data/schema/index.md =====
...
```

## 문체

- 한국어. 결론 먼저. 부제·훈계조 금지.
- 원본에서 확인한 값에는 [실측], 원본이 안 밝힌 것은 [미확보].
- 표를 적극적으로 쓴다. 계약은 표가 읽기 좋다.
- 각 절 끝에 근거 파일과 줄 번호. 예: `docs/handoff/01_계약_Pydantic.md:120-145`

다른 설명은 붙이지 마라.
