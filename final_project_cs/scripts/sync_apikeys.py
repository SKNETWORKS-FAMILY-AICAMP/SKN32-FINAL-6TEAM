# -*- coding: utf-8 -*-
"""`.env.apikeys` 를 템플릿과 맞춘다. **있는 값은 절대 안 건드린다.**

★★왜 만들었나 (2026-09-10 사고).
  Claude 가 `cp .env.apikeys.example .env.apikeys` 를 세 번 돌렸고, 그때마다
  사용자가 넣어 둔 **실제 키가 빈 템플릿으로 덮여 사라졌다.** 사용자가
  세 번째에 알아채고 다시 넣었다.

  덮어쓰기 전에 대상을 봤어야 했다. 「템플릿을 복사한다」는 동작 자체가
  **파괴적**인데 그렇게 안 보였던 것이 문제다. 그래서 복사를 없애고
  **병합**만 남긴다 — 이 스크립트에는 값을 지우는 경로가 없다.

하는 일 둘:
  ① 템플릿에 있는데 대상에 **없는** 이름을 덧붙인다
  ② 대상 값이 **비어 있고** 템플릿에 기본값이 있으면 그 기본값을 채운다

  ②가 필요한 이유(2026-09-10, 같은 날 두 번째 사고): 처음엔 ①만 했는데
  덧붙인 줄이 전부 `NAME=` 이었다. API **키**는 비어 있는 게 맞지만
  `ACOP_RATE_..._PER_DAY` 같은 **숫자 설정**은 빈 문자열이 int 로 안 읽혀
  `ValidationError` 로 **앱이 아예 안 떴다.** 템플릿 기본값을 가져온다.

  ★②는 채워진 값을 **절대** 덮지 않는다. 비어 있을 때만 채운다.

사용:
    python -m scripts.sync_apikeys          # 맞춘다
    python -m scripts.sync_apikeys --check  # 무엇이 어긋났는지만 보고, 쓰지 않는다
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ★Windows 기본 콘솔이 cp949 라 특수문자에서 UnicodeEncodeError 로 죽는다.
#   스크립트가 자기 출력 때문에 실패하면 안 된다(2026-09-10 실제로 났다).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / ".env.apikeys.example"
TARGET = REPO_ROOT / ".env.apikeys"

_ASSIGN = re.compile(r"^(ACOP_[A-Z0-9_]+)=(.*)$")


def _pairs(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        matched = _ASSIGN.match(line)
        if matched:
            found[matched.group(1)] = matched.group(2).strip()
    return found


def main() -> int:
    check_only = "--check" in sys.argv

    if not TEMPLATE.exists():
        print(f"템플릿이 없다: {TEMPLATE}")
        return 1

    template_text = TEMPLATE.read_text(encoding="utf-8")
    wanted = _pairs(template_text)

    if not TARGET.exists():
        # ★없을 때만 템플릿을 그대로 쓴다. 있으면 절대 이 경로로 안 온다.
        if check_only:
            print(f"{TARGET.name} 이 없다. `python -m scripts.sync_apikeys` 로 만든다.")
            return 1
        TARGET.write_text(template_text, encoding="utf-8")
        print(f"{TARGET.name} 을 템플릿에서 새로 만들었다. 키 값을 채운다.")
        return 0

    current_text = TARGET.read_text(encoding="utf-8")
    current = _pairs(current_text)

    missing = [name for name in wanted if name not in current]
    # ★비어 있고 템플릿에 기본값이 있는 것만. 채워진 값은 후보에서 빠진다.
    blank = [name for name, value in current.items()
             if not value and wanted.get(name, "")]
    filled = sum(1 for value in current.values() if value)

    print(f"{TARGET.name}: 항목 {len(current)}개 · 값이 채워진 것 {filled}개")
    if not missing and not blank:
        print("어긋난 것 없음. 아무것도 쓰지 않았다.")
        return 0

    if missing:
        print(f"빠진 항목 {len(missing)}개: {', '.join(missing)}")
    if blank:
        print(f"비어 있어 기본값을 채울 항목 {len(blank)}개: {', '.join(blank)}")
    if check_only:
        return 1

    text = current_text
    for name in blank:
        # ★그 이름의 **빈 줄만** 바꾼다. 값이 있는 줄은 정규식이 안 잡는다.
        text = re.sub(rf"^{re.escape(name)}=\s*$", f"{name}={wanted[name]}",
                      text, count=1, flags=re.MULTILINE)

    if missing:
        block = ["", "", "# 아래는 sync_apikeys 가 나중에 덧붙인 항목이다"]
        block += [f"{name}={wanted[name]}" for name in missing]
        text = text.rstrip("\n") + "\n" + "\n".join(block) + "\n"

    TARGET.write_text(text, encoding="utf-8")
    print(f"덧붙임 {len(missing)}개 · 기본값 채움 {len(blank)}개. "
          f"**채워져 있던 값은 하나도 안 건드렸다.**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
