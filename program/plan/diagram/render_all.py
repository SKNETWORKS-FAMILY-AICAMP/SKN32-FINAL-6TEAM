"""A-COP 다이어그램 8종을 PlantUML 서버로 렌더링한다.

사용법:  python render_all.py
전제:    pip install plantuml, 그리고 plantuml.com 접속 가능한 네트워크.

렌더링 후 A-COP_다이어그램_모음.html도 다시 만들려면 build_showcase.py를 실행한다.
"""

import pathlib
import plantuml

ROOT = pathlib.Path(__file__).parent
SERVER = "http://www.plantuml.com/plantuml/svg/"

DIAGRAMS = (
    "acop_usecase_v2",
    "acop_class_v2",
    "acop_sequence_v2",
    "acop_state_v2",
    "acop_erd_v2",
    "acop_component_v2",
    "acop_a2a_sequence_v2",
    "acop_deploy_v2",
)


def main() -> int:
    server = plantuml.PlantUML(url=SERVER)
    failed = []
    for name in DIAGRAMS:
        src = ROOT / f"{name}.puml"
        if not src.exists():
            print(f"SKIP {name}: {src.name} 없음")
            failed.append(name)
            continue
        try:
            svg = server.processes(src.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"FAIL {name}: {exc!r}")
            failed.append(name)
            continue
        (ROOT / f"{name}.svg").write_bytes(svg)
        print(f"OK   {name}.svg {len(svg)} bytes")

    if failed:
        print(f"\n실패 {len(failed)}건: {', '.join(failed)}")
        return 1
    print(f"\n{len(DIAGRAMS)}종 전부 렌더링 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
