import pathlib
import plantuml

root = pathlib.Path(__file__).parent
server = plantuml.PlantUML(url="http://www.plantuml.com/plantuml/svg/")
for name in ("acop_state_v2", "acop_erd_v2"):
    source = (root / f"{name}.puml").read_text(encoding="utf-8")
    (root / f"{name}.svg").write_bytes(server.processes(source))
    print("OK", name)

