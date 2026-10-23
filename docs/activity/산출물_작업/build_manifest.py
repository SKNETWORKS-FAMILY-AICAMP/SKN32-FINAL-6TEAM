import json, re, sys, yaml
from pathlib import Path
base = Path(sys.argv[1])
docs = []
for p in sorted((base / "documents").glob("*.md")):
    text = p.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
    fm = yaml.safe_load(m.group(1))
    sections = len(re.findall(r"(?m)^##\s+", m.group(2)))
    docs.append({"document_id": fm["document_id"], "file": f"documents/{p.name}", "section_count": sections})
(base / "manifest.json").write_text(json.dumps({"version": "1.0", "tenant_id": "demo", "collection": "travel-scratch", "documents": docs}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(docs), "docs,", sum(d["section_count"] for d in docs), "chunks")
