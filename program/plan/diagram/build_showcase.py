"""렌더링된 SVG 8종을 하나의 자체완결 HTML로 묶는다.

사용법:  python build_showcase.py
전제:    render_all.py를 먼저 실행해 .svg가 최신이어야 한다.

SVG를 파일 안에 직접 넣으므로 결과 HTML 하나만 있으면 어디서 열어도 그림이 보인다.
"""

import pathlib

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "A-COP_다이어그램_모음.html"

# (파일명, 제목, 설명, 근거 절)
ITEMS = [
    ("acop_usecase_v2", "유스케이스",
     "고객·운영자·외부 개인 AI(REST/MCP)·외부 기업 Agent(A2A) 4개 액터와 CS Pack 2개 + Commerce Ops Pack 4개 Team",
     "§1-2, §8-B, §9, §9-C, §10"),
    ("acop_class_v2", "클래스",
     "통합 계약 전문 기준. Registered Team Modules / Access & Action Platform / Core Runtime & Coordination / Core Contracts 4개 패키지",
     "§21, §8, §8-B"),
    ("acop_sequence_v2", "시퀀스",
     "Case 접수 → 분류 → Context Pack → Team 실행(LOCAL/A2A) → 승인·재개·에스컬레이션",
     "§19, §8, §8-A"),
    ("acop_state_v2", "상태도",
     "케이스 생명주기 12개 상태와 허용 전이. 영문 라벨은 §19 원문, 한글 라벨은 설명용 추가",
     "§19"),
    ("acop_erd_v2", "ERD",
     "PostgreSQL 테이블 14개와 ENUM 2개. UNIQUE 제약(이벤트 소싱 동시성·idempotency·메시지 중복 방지) 표기",
     "§22, §11"),
    ("acop_component_v2", "컴포넌트",
     "Core 1 / Core 2 경계와 Basement 8개 구성요소. Message Broker와 Context Broker의 역할 구분",
     "§7-B, §8, §8-A"),
    ("acop_a2a_sequence_v2", "A2A 시퀀스",
     "Agent Card → Task → Artifact 생명주기와 A2A Task ↔ Case 상태 매핑",
     "§9, §9-C, §9-C-1"),
    ("acop_deploy_v2", "배포",
     "패키지 3분할. 고객용 릴리즈 빌드에 acop_composer가 존재하지 않는다는 것이 핵심",
     "§12, §13, Composer v3 §8"),
]

STYLE = """
:root { color-scheme: light; font-family: system-ui, -apple-system, sans-serif; }
body { margin:0; background:#f5f3ff; color:#24133f; }
main { max-width:1600px; margin:0 auto; padding:28px; }
h1 { color:#5b21b6; margin-bottom:6px; }
.lead { color:#5b5568; margin-top:0; }
nav { background:#fff; border:1px solid #ddd6fe; border-radius:12px; padding:12px 16px; margin:18px 0; }
nav a { color:#6d28d9; text-decoration:none; font-weight:600; }
nav a:hover { text-decoration:underline; }
section { margin:24px 0; padding:22px; background:#fff; border:1px solid #ddd6fe; border-radius:14px; }
h2 { margin:0 0 6px; color:#5b21b6; }
.d { color:#5b5568; margin:0 0 4px; }
.b { color:#8b84a3; font-size:13px; margin:0 0 14px; }
.wrap { overflow-x:auto; }
.wrap svg { display:block; max-width:100%; height:auto; }
footer { color:#8b84a3; font-size:13px; padding:8px 0 24px; }
"""


def main() -> int:
    parts, missing = [], []
    for name, title, desc, basis in ITEMS:
        svg_path = ROOT / f"{name}.svg"
        if not svg_path.exists():
            missing.append(name)
            continue
        svg = svg_path.read_text(encoding="utf-8")
        svg = svg[svg.find("<svg"):]
        parts.append(
            f'<section id="{name}"><h2>{title}</h2><p class="d">{desc}</p>'
            f'<p class="b">근거: {basis}</p><div class="wrap">{svg}</div></section>'
        )

    if missing:
        print(f"경고: SVG 없음 {len(missing)}건 — {', '.join(missing)}")
        print("render_all.py를 먼저 실행하라.")

    nav = " · ".join(
        f'<a href="#{n}">{t}</a>' for n, t, _, _ in ITEMS
        if (ROOT / f"{n}.svg").exists()
    )
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>A-COP 다이어그램 모음</title>
<style>{STYLE}</style></head><body><main>
<h1>A-COP 다이어그램 모음</h1>
<p class="lead">A-COP 구현계획서 v8을 근거로 작성한 순수 PlantUML 다이어그램입니다.
실제 구현 코드가 아니라 계획서가 목표로 하는 구조를 반영합니다.</p>
<nav>{nav}</nav>
{''.join(parts)}
<footer>원본 .puml과 근거는 같은 폴더에 있습니다. 다시 만들려면 render_all.py 실행 후 build_showcase.py를 실행합니다.</footer>
</main></body></html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"OK {OUT.name} {OUT.stat().st_size} bytes ({len(parts)}종 수록)")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
