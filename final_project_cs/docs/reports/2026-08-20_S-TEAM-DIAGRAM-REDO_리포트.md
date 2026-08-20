# S-TEAM-DIAGRAM-REDO

## 변경 내용

- `scratch_team_diagram_reference.html`은 수정하지 않고, 전체 페이지를 복사한 `scratch_team_diagram_redo.html`을 새로 만들었다.
- `#diagram` 안의 SVG만 `viewBox="0 0 1100 620"`으로 다시 그렸다. Case → Controller → TeamRegistry는 기존 의미를 유지한 수직 일자 흐름이다.
- 팀 박스 6개는 각각 `220×110`이며, `x=190/430/670`, `y=210/344`에 배치한 3열×2행 격자다. 열 간격은 30px, 행 간격은 24px이다.
- 정책 RAG 4개 팀에는 `var(--rag)` 5px 왼쪽 바, VOC & Store Manager에는 `var(--sim)` 5px 왼쪽 바를 붙였다. Catalog & Verification은 `var(--gap)` 회색 점선 전체 테두리로만 표시했다.
- 격자 아래에는 데이터 소스별 3줄 텍스트 범례를 넣었고, 그 아래에 `text-embedding-3-small`, 1536차원 모델 하나를 공유한다는 문장을 넣었다. 별도 데이터 저장소 박스나 데이터 소스 연결선은 다시 그리지 않았다.
- 기존 CSS 토큰과 팀별 카드, 임베딩 섹션, 데이터 공백 섹션은 복사본에서 그대로 재사용했다. 따라서 라이트/다크 테마 토큰도 기존 구조를 따른다.

## 교차가 원천적으로 사라지는 이유

새 레이아웃에는 팀 박스와 데이터 소스 박스를 연결하는 선이 없다. 상단의 제어 흐름은 수직 직선 2개뿐이며, 팀별 데이터 관계는 각 박스의 왼쪽 컬러 바와 아래 3줄 텍스트 범례로 표현한다. 따라서 데이터 소스에서 여러 팀으로 향하는 곡선·대각선·팬아웃 선이 존재하지 않고, 교차를 계산할 선 자체가 없다. `Catalog & Verification`에도 데이터 박스나 연결 화살표를 추가하지 않았다.

## 좌표 및 텍스트 검증

`scripts/verify_team_diagram_redo.py`가 완성 HTML에서 `220×110` 사각형 6개를 직접 추출해 다음을 검사한다.

1. 모든 팀 사각형 쌍의 직사각형 교집합이 없는지 검사한다.
2. 열 좌표가 `190, 430, 670`, 행 좌표가 `210, 344`인지 검사한다.
3. 교체 SVG에 곡선 연결용 `path`/`C` 경로가 없는지 검사한다.
4. 팀 내부 라벨을 보수적으로 ASCII 8px, 비ASCII 14px 기준으로 추정해 박스 내부 사용 가능 폭 `220-20=200px`을 넘지 않는지 검사한다.

실행 결과:

```text
PASS: 6 team boxes, exact 220x110 size, no rectangle overlap
PASS: 3 columns x 2 rows at x=190/430/670 and y=210/344
PASS: no curved/path connectors in the replacement SVG
PASS: conservative team-label width estimates stay within 200px
```
