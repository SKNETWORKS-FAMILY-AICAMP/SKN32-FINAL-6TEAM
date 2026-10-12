import pathlib, plantuml
root = pathlib.Path(__file__).parent
server = plantuml.PlantUML(url="http://www.plantuml.com/plantuml/svg/")
for name in ("acop_component_v2", "acop_a2a_sequence_v2", "acop_deploy_v2"):
    source = (root / f"{name}.puml").read_text(encoding="utf-8")
    (root / f"{name}.svg").write_bytes(server.processes(source))
    print("OK", name)
