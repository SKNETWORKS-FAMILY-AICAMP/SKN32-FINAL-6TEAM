"""★basement 층에 업무 도메인 어휘가 들어오지 못하게 막는다.

이 저장소의 목표는 **어떤 CS 플랫폼 요청이 와도 바로 대응 가능한 범용 basement** 다.
쇼핑몰 CS 는 이 프로젝트를 **복사해서** 만든다.

그래서 지켜야 할 경계가 있다:

    basement (도메인을 몰라야 함)      app/core, app/domain, app/application,
                                       app/infrastructure, app/presentation
    도메인 자리 (알아도 됨)            app/modules/**, config/**, 도메인 마이그레이션

★검사하지 않는 규칙은 지켜지지 않는다. 이 저장소에서 여러 번 겪었다.
  실제로 2026-08-16 에 `app/core/verification.py` 가 구독·결제 어휘를 Core 에 박았고,
  그 결과 **쇼핑몰의 `order_id` 가 basement 의 "확인 불가 → 거부" 목록에 올라 있었다.**
  가장 중요한 식별자가 거부 대상이 되는 정반대 상황이다.

이 테스트는 그 재발을 막는다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path("app")

#: basement — 업무 도메인 어휘가 있으면 안 되는 곳
BASEMENT_DIRS = ("core", "domain", "application", "infrastructure", "presentation")

#: 도메인 자리 — 여기서는 도메인을 알아도 된다
DOMAIN_DIRS = ("modules",)

#: 업무 도메인 어휘. ★"고객·케이스·팀" 처럼 CS 일반 개념은 넣지 않는다 —
#:  그건 이 플랫폼이 다루는 대상 자체다.
DOMAIN_WORDS = (
    # 구독·결제 (현재 sample 도메인)
    "payment", "subscription", "entitlement", "refund", "invoice",
    # 커머스 (복사본이 쓸 도메인)
    "order_id", "line_item", "shipment", "sku", "cart",
)

PATTERN = re.compile("|".join(DOMAIN_WORDS), re.IGNORECASE)

#: ★예외는 **이유와 함께** 적는다. 목록이 늘어나면 그 자체가 신호다.
ALLOWED = {
    # PII 마스킹 패턴. 결제 식별자 모양을 알아야 가릴 수 있다 —
    # 도메인 로직이 아니라 **보안 규칙**이다.
    "app/core/redaction.py",
    # 원격 Agent 데모. A-COP 본체가 아니라 **왕복 검증용 상대역**이며,
    # 복사본은 이 파일을 자기 도메인으로 갈아 끼운다.
    "app/presentation/a2a/remote_agent.py",
    # Composer 쓰기채널의 KNOWN_IMPLEMENTATION_REFS allowlist(2026-08-24,
    # S-BASEMENT-08). 인증된 사용자가 임의 모듈을 import 시키는 걸 막으려면
    # 이 제품이 실제로 등록한 구현체 이름을 알아야 화이트리스트가 동작한다 —
    # 도메인 로직이 아니라 **보안 규칙**이다(redaction.py와 같은 성격).
    # ★한때 문자열을 쪼개("return_re"+"fund") 이 검사를 우회한 적이 있다 —
    #   재발 금지: 도메인 어휘가 필요하면 숨기지 말고 여기 예외로 적는다.
    "app/core/project_config.py",
}


def _python_files(*roots: str) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        base = APP / root
        if base.exists():
            out.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return out


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    hits = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        # 주석·docstring 안의 언급은 봐준다 — 설명은 도메인 결합이 아니다.
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("★"):
            continue
        if PATTERN.search(line):
            hits.append((number, stripped[:110]))
    return hits


def test_basement_layers_do_not_know_the_business_domain():
    """★basement 가 특정 업무 도메인을 알면 복사본이 그것을 물려받는다."""
    problems: dict[str, list[tuple[int, str]]] = {}
    for path in _python_files(*BASEMENT_DIRS):
        rel = path.as_posix()
        if rel in ALLOWED:
            continue
        hits = _offending_lines(path)
        if hits:
            problems[rel] = hits

    assert not problems, (
        "basement 에 업무 도메인 어휘가 있다. 도메인은 app/modules/ 또는 선언(config/)으로 내린다:\n"
        + "\n".join(f"  {f}:{n}  {t}" for f, hits in problems.items() for n, t in hits))


def test_domain_modules_are_allowed_to_know_their_domain():
    """★반대 방향도 확인한다. 도메인 자리가 비어 있으면 이 게이트는 무의미하다.

    (게이트가 '아무 데도 도메인이 없다' 를 통과시키면 잘못 만든 것이다.)
    """
    hits = [p for p in _python_files(*DOMAIN_DIRS) if _offending_lines(p)]
    assert hits, "app/modules/ 에 도메인 구현이 없다 — 게이트가 헛돌고 있다"


def test_allow_list_stays_small():
    """★예외 목록이 늘어나면 경계가 무너지는 중이라는 뜻이다."""
    assert len(ALLOWED) <= 3, f"예외가 {len(ALLOWED)}개다. 늘리기 전에 설계를 의심하라: {sorted(ALLOWED)}"


@pytest.mark.parametrize("path", sorted(p.as_posix() for p in _python_files(*BASEMENT_DIRS)))
def test_no_basement_file_imports_a_domain_module(path: str):
    """★basement 는 `app.modules` 를 import 하지 않는다.

    조립은 composition root 가 **선언을 읽어** 한다. basement 가 특정 모듈을
    직접 부르면 그 모듈 없이는 못 뜬다.
    """
    if path == "app/composition.py":
        pytest.skip("composition root 는 선언대로 도메인 모듈을 조립하는 자리다")
    text = Path(path).read_text(encoding="utf-8")
    assert "from app.modules" not in text and "import app.modules" not in text, \
        f"{path} 가 도메인 모듈을 직접 import 한다"
