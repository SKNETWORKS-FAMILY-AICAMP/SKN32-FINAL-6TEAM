# S-DEAD-CODE-AUDIT — 죽은 코드 감사 (리포트만, 삭제 금지)

## 배경 (읽지 않아도 되는 맥락)

이 세션에서 이미 두 번 죽은 코드를 발견했다: `app/presentation/ui/routes.py` 에
콘솔 분리 이후 아무도 쓰지 않는 `router = APIRouter(prefix="/ui", ...)` 선언이
남아 있었고(제거함), 그전엔 `app/presentation/ui/console.py`/`composer.py` 가
통째로 orphan 이었다(삭제함). 비슷한 게 더 있을 가능성이 있다 — 특히 이전
세션에서 `app/console/` 패키지를 통째로 없애고 `docs/console/**` 관련 문서·
라우팅을 여러 번 옮겼기 때문이다.

## 이번엔 다르게 한다 — ★삭제하지 않는다, 보고만 한다

지난 세션들에서 Codex 산출물을 검수 없이 신뢰하지 않는 습관이 이 저장소의
원칙이다(`RULE.md` §3.6-3). 이번엔 사용자가 잠들어 있어 그 검수를 내(Claude)가
대신 해야 하므로, **더 보수적으로 간다**: 이 스트림은 **아무 파일도 수정하지
않는다.** 후보를 찾아 근거와 함께 리포트만 낸다. 삭제는 Claude 가 검수 후
직접 한다.

## 스캔 범위

`app/**` 전체 (basement 층: `core`, `domain`, `application`, `infrastructure`,
`presentation` — `app/modules/**` 는 도메인 코드라 스캔은 하되 우선순위 낮음).

## 찾을 것

각 `.py` 파일의 top-level 함수·클래스·모듈 수준 변수 중:

1. **어디서도 import 되지 않는 모듈** — 다른 `.py` 파일의 `import`/`from ... import`
   에 전혀 등장하지 않는 파일. `__init__.py`, `conftest.py`, FastAPI 앱 엔트리포인트
   (`app/presentation/api/app.py`)는 예외로 취급 — 프레임워크가 암묵적으로 불러온다.
2. **정의됐지만 아무도 참조하지 않는 top-level 함수·클래스** — 정의한 파일 밖에서
   이름이 한 번도 등장하지 않는 것. `tests/**`, `docs/**`, `scripts/**` 에서의
   참조도 "쓰인다"로 친다 — 테스트에서만 쓰여도 죽은 코드가 아니다.
3. **`app/presentation/ui/routes.py` 같은 패턴** — 선언은 됐는데 어디에도
   `include_router`/직접 마운트되지 않는 `APIRouter` 인스턴스.

## 반드시 지킬 것

- **grep 결과를 그대로 보고한다.** "아마 안 쓰일 것"이 아니라 실제로 돌린
  검색 명령과 그 출력(0건이었다는 것)을 리포트에 원문으로 남긴다.
- 동적 import(`importlib.import_module`, 문자열 기반 `implementation_ref` —
  `config/project.yaml` 의 Team/Port 조립 패턴이 이렇게 동작한다)에 걸리는
  대상은 **후보에서 제외**한다. 정적 grep 이 못 잡는 진짜 사용처가 있을 수 있다.
  헷갈리면 "확실하지 않음"으로 표시하고 후보에서 뺀다 — 틀리게 지우는 것보다
  덜 지우는 게 안전하다.
- **아무 파일도 수정하지 않는다.** `.py`·`.md`·설정 파일 전부 읽기 전용.
  리포트 파일 하나만 새로 만든다.

## 만들 것

`wiki/records/reports/2026-08-17_죽은코드_감사.md` 하나만. 형식:

```
## 후보 N개

### 1. <파일:줄번호> — <함수/클래스/모듈 이름>
- 무엇: <한 줄 설명>
- 근거: <실제로 돌린 grep 명령과 0건 출력을 그대로>
- 확신도: 높음 | 보통 (동적 참조 가능성 있으면 보통으로 낮춘다)
```

후보가 없으면 없다고 정직하게 적는다 — 억지로 만들지 않는다.

## 완료 기준

```powershell
python -m pytest -q   # 이 스트림은 코드를 안 건드리므로 그대로 334 passed 여야 한다
```
