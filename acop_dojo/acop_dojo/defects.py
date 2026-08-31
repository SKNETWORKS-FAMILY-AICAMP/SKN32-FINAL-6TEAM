"""결함 카탈로그.

자동 뮤테이션은 쓰지 않는다. 구글의 대규모 사례에서 개발자가 뮤턴트의 85%를
무의미하다고 분류했고, equivalent mutant 비율도 연구에 따라 4~39%다. 무작위로 뽑으면
정답이 없는 문제와 아무 테스트도 깨지지 않는 문제가 대량으로 섞인다.

그래서 이 저장소가 문서로 못 박은 불변식에서 사람이 손으로 만들고, 등록 전에
"지정한 테스트를 실제로 죽이는가"를 기계가 확인한 것만 카탈로그에 넣는다.
"""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DOJO_ROOT

CATALOG_PATH = DOJO_ROOT / "defects" / "catalog.json"
PATCH_DIR = DOJO_ROOT / "defects" / "patches"


@dataclass
class Defect:
    defect_id: str
    title: str
    invariant: str
    path: str
    #: 원본에 있는 정확한 조각
    old: str
    #: 결함을 심은 뒤의 조각
    new: str
    #: 왜 이것이 규칙 위반인가 — 학습자가 설명해야 할 것
    lesson: str
    #: 흔한 오개념. 학습자의 설명이 이쪽이면 아직 이해한 게 아니다.
    counterfactuals: list[str] = field(default_factory=list)
    difficulty: int = 1
    #: 게이트를 통과해도 문제로 내지 않는 이유. 비어 있으면 낸다.
    excluded: str = ""


DEFECTS: list[Defect] = [
    Defect(
        defect_id="INV-STATE-001",
        title="버전 대조가 헐거워져 지난 상태로 덮어쓴다",
        invariant="낙관적 동시성 — 상태 변경은 읽은 시점의 version 과 정확히 맞아야 한다",
        path="app/core/transition.py",
        old="    if current.version != expected_version:",
        new="    if current.version < expected_version:",
        lesson=(
            "!= 를 < 로 바꾸면 내가 읽은 뒤 남이 먼저 바꾼 경우(현재 version 이 더 큼)를 "
            "충돌로 보지 않는다. 두 실행이 같은 Case 를 각자 계산한 결과로 덮어쓴다."
        ),
        excluded=(
            "잡히는지가 실행마다 갈린다. 같은 문제를 두 번 풀면 다른 답이 나온다. "
            "낙관적 동시성 가드가 파이썬과 SQL 양쪽에 있어 상태는 보존되고, 진 쪽이 "
            "언제 읽느냐에 따라 StateConflict 가 나기도 InvalidTransition 이 나기도 한다. "
            "final_project_cs/docs/reports/debugs/2026-08-31_버전대조_가드_중복.md"
        ),
        counterfactuals=[
            "트랜잭션이 있으니 버전 대조는 없어도 된다",
            "버전이 작아지는 경우만 막으면 충분하다",
        ],
    ),
    Defect(
        defect_id="INV-PII-001",
        title="저장 전 마스킹에서 이메일 규칙이 빠졌다",
        invariant="PII 는 저장 시 마스킹하고 LLM 에는 masked 만 넘긴다",
        path="app/core/redaction.py",
        old='lambda m: m.group(1)[0] + "***@" + m.group(2)',
        new='lambda m: m.group(1) + "@" + m.group(2)',
        lesson=(
            "마스킹은 저장 직전에 한 번 걸리는 관문이다. 규칙 하나가 빠지면 그 종류의 원문이 "
            "DB 와 감사 로그를 지나 LLM 프롬프트까지 그대로 흘러간다."
        ),
        counterfactuals=[
            "API 인증이 있으니 저장된 원문은 안전하다",
            "이메일은 민감정보가 아니다",
        ],
    ),
    Defect(
        defect_id="INV-DEGRADED-001",
        title="축소했는데 무엇을 뺐는지 남기지 않아도 통과한다",
        invariant="신호 없는 축소는 폴백이다 — degraded 면 omissions 를 반드시 남긴다",
        path="app/core/contracts.py",
        old="        if self.degraded and not self.omissions:",
        new="        if self.degraded and self.omissions is None:",
        lesson=(
            "omissions 는 기본값이 빈 리스트라 None 이 되는 일이 없다. 조건이 영영 참이 되지 않아 "
            "검사가 사라진다. 근거가 빠진 답변이 빠졌다는 표시 없이 나간다."
        ),
        counterfactuals=[
            "degraded 플래그만 켜져 있으면 충분하다",
            "빈 리스트와 None 은 어차피 같은 뜻이다",
        ],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-SCOPE-001",
        title="Case 목록이 customer 경계를 무시한다",
        invariant="모든 조회에 tenant_id 와 customer_id(또는 case_id) 조건을 적용한다",
        path="app/infrastructure/db/repository.py",
        old='    if customer_id is not None: query += " AND customer_id=%s"; params.append(customer_id)',
        new="",
        lesson=(
            "조건 없는 조회는 그 자체가 보안 결함이다. tenant 안에서도 고객끼리 섞이면 "
            "한 사람의 Case 가 다른 사람에게 보인다."
        ),
        counterfactuals=[
            "tenant 로 걸렀으니 충분하다",
            "화면에서 다시 거르면 된다",
        ],
    ),
    Defect(
        defect_id="INV-IDEM-001",
        title="멱등키에서 대상 필드가 빠졌다",
        invariant="같은 요청을 두 번 실행해도 side effect 는 한 번만 난다",
        path="app/core/idempotency.py",
        old="        for part in (tenant_id, request_id, action_type, business_subject)",
        new="        for part in (tenant_id, request_id, action_type)",
        lesson=(
            "키에서 대상이 빠지면 같은 요청 안의 서로 다른 대상이 같은 키를 갖는다. "
            "두 번째 대상에 대한 실행이 이미 처리된 것으로 취급돼 조용히 사라진다."
        ),
        counterfactuals=[
            "tenant 와 request 가 같으면 같은 요청이다",
            "DB 유니크 제약이 있으니 키는 대충 만들어도 된다",
        ],
    ),
    Defect(
        defect_id="INV-STATE-002",
        title="전이표에 없는 전이가 기본값으로 통과한다",
        invariant="상태표에 없는 전이는 거부한다",
        path="app/domain/events.py",
        old="    return TRANSITIONS.get((current, event))",
        new="    return TRANSITIONS.get((current, event), CaseStatus.RESOLVED)",
        lesson=(
            "None 을 돌려주는 것이 '이 전이는 없다'는 신호다. 기본값을 주면 그 신호가 사라져 "
            "아무 상태에서나 종료로 건너뛴다."
        ),
        counterfactuals=[
            "기본값을 주면 None 처리 코드를 줄일 수 있어 낫다",
            "어차피 상위에서 막으니 여기선 관대해도 된다",
        ],
        difficulty=2,
    ),
    Defect(
        defect_id="INV-PII-002",
        title="API 키 마스킹 규칙이 사라졌다",
        invariant="감사 로그에 API key 원문을 기록하지 않는다",
        path="app/core/redaction.py",
        old='"[REDACTED_API_KEY]"',
        new='"[REDACTED_API_KEY]" if False else text',
        lesson="마스킹 치환이 무력화되면 키 원문이 그대로 저장된다.",
        counterfactuals=["키는 어차피 만료되니 로그에 남아도 된다"],
    ),
]


def by_id(defect_id: str) -> Defect:
    for defect in DEFECTS:
        if defect.defect_id == defect_id:
            return defect
    known = ", ".join(d.defect_id for d in DEFECTS)
    raise SystemExit(f"모르는 결함이다: {defect_id}\n아는 것: {known}")


def build_patch(defect: Defect, target: Path) -> str:
    """원본에서 조각 하나를 바꾼 unified diff 를 만든다.

    AST 변환 규칙이나 결함별 브랜치를 쓰지 않는 이유는 단순하다 — diff 는 사람이
    검토할 수 있고, 학습자가 낸 패치와 나란히 놓고 비교하기 쉽다.
    """
    source_path = target / defect.path
    # 대상 파일은 CRLF 다. 개행을 정규화해서 읽으면 되돌린 뒤 바이트가 달라진다.
    with source_path.open(encoding="utf-8", newline="") as handle:
        original = handle.read()
    # 대상 파일은 CRLF 다. 앵커를 LF 로 적어도 찾을 수 있게 한 번 더 시도한다.
    anchor, replacement = defect.old, defect.new
    if anchor not in original:
        crlf = anchor.replace(chr(10), chr(13) + chr(10))
        if crlf in original:
            anchor = crlf
            replacement = replacement.replace(chr(10), chr(13) + chr(10))
    if anchor not in original:
        raise SystemExit(
            f"{defect.defect_id}: 기준 코드가 바뀌었다. 카탈로그를 갱신해야 한다.\n  찾던 것: {defect.old!r}"
        )
    if original.count(anchor) != 1:
        raise SystemExit(f"{defect.defect_id}: 기준 조각이 {original.count(anchor)}번 나온다. 더 좁혀야 한다.")
    mutated = original.replace(anchor, replacement, 1)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True), mutated.splitlines(keepends=True),
        fromfile=f"a/{defect.path}", tofile=f"b/{defect.path}", n=3,
    )
    return "".join(diff)


def write_patches(target: Path) -> list[Path]:
    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for defect in DEFECTS:
        path = PATCH_DIR / f"{defect.defect_id}.patch"
        path.write_text(build_patch(defect, target), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {"schema_version": "acop-defect/1.0", "entries": {}}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def save_catalog(data: dict[str, Any]) -> Path:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    return CATALOG_PATH


# 목록을 파일 하나에 다 넣으면 읽기 어려워 나눴다. 순환 import 처럼 보이지만
# Defect 와 DEFECTS 가 이미 정의된 뒤라 정상 동작한다.
from .defects_more import MORE  # noqa: E402
from .defects_more2 import MORE2  # noqa: E402
from .defects_more3 import MORE3  # noqa: E402
from .defects_more4 import MORE4  # noqa: E402

DEFECTS.extend(MORE)
DEFECTS.extend(MORE2)
DEFECTS.extend(MORE3)
DEFECTS.extend(MORE4)
