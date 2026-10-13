"""고정 v12 후보를 실제 지정 Claude 모델로 읽기 감사하고 원문·해시를 보존한다."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parents[4]
evidence = Path(__file__).resolve().parent
candidate = root / "legacy/deployment_candidates/2026-10-12_022208_plugin_v12"
label = sys.argv[1]
assert label in ("opus", "sonnet")
model = "claude-" + label + "-5-5"
prefix = evidence / (label + "-v12-read-boundary-closing-2026-10-12_0227")
runner = evidence / "v12-read-boundary-final-unit.py"
fixed = '"C:/Users/playdata2/anaconda3/python.exe" ' + runner.relative_to(root).as_posix()
files = [f for d in ("app", "config", "tests", "merge-evidence") for f in (candidate/d).rglob("*") if f.is_file() and "__pycache__" not in f.parts and f.suffix in (".py", ".yaml", ".yml", ".json", ".diff", ".md")]
files += [candidate/"release-manifest.json", root/"RULE.md", root/"AGENTS.md", root/"wiki/teams/team-contract/plugin-availability.md", runner, evidence/"v12-read-boundary-exact-command-hook.py", candidate/"review-notes/read-boundary-followup.md", Path(str(prefix)+"-prompt.txt"), Path(str(prefix)+"-permissions.json")]
def hashes():
    return [{"path":str(f.relative_to(root)).replace(chr(92),"/"), "sha256":hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None} for f in sorted(set(files))]
start=hashes()
Path(str(prefix)+"-start-sha256.json").write_text(json.dumps(start,ensure_ascii=False,indent=2),encoding="utf-8")
cli=shutil.which("claude.cmd")
if not cli:
    raise RuntimeError("claude.cmd not found")
command=[cli,"--model",model,"--print","--output-format","stream-json","--verbose","--permission-mode","dontAsk","--strict-mcp-config","--mcp-config",'{"mcpServers":{}}',"--setting-sources","","--settings",str(prefix)+"-permissions.json","--no-session-persistence","--disable-slash-commands","--tools","Read,Glob,Grep,Bash","--allowedTools","Read","Glob","Grep","Bash("+fixed+")"]
Path(str(prefix)+"-command.json").write_text(json.dumps({"model":model,"argv":command},ensure_ascii=False,indent=2),encoding="utf-8")
with Path(str(prefix)+"-review.jsonl").open("w",encoding="utf-8") as out, Path(str(prefix)+"-stderr.txt").open("w",encoding="utf-8") as err:
    result=subprocess.run(command,cwd=root,input=Path(str(prefix)+"-prompt.txt").read_text(encoding="utf-8"),text=True,encoding="utf-8",stdout=out,stderr=err,check=False)
end=hashes()
Path(str(prefix)+"-end-sha256.json").write_text(json.dumps(end,ensure_ascii=False,indent=2),encoding="utf-8")
Path(str(prefix)+"-exit.json").write_text(json.dumps({"exit_code":result.returncode}),encoding="utf-8")
messages=[json.loads(line) for line in Path(str(prefix)+"-review.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
res=next((m for m in reversed(messages) if m.get("type")=="result"),{})
uses={}; reads=[]; outputs=[]
for m in messages:
    msg=m.get("message")
    for b in msg.get("content",[]) if isinstance(msg,dict) else []:
        if not isinstance(b,dict): continue
        if b.get("type")=="tool_use":
            uses[b["id"]]=b
            if b["name"]=="Read": reads.append(b["input"])
        elif b.get("type")=="tool_result" and uses.get(b.get("tool_use_id"),{}).get("name")=="Bash": outputs.append(b)
metadata={"requested_model":model,"exit_code":result.returncode,"is_error":res.get("is_error"),"canonical_models":{k:v.get("canonicalModel") for k,v in res.get("modelUsage",{}).items()},"modelUsage":res.get("modelUsage"),"permission_denials":res.get("permission_denials"),"direct_Read_calls":reads,"tools":{name:sum(v["name"]==name for v in uses.values()) for name in {v["name"] for v in uses.values()}},"num_turns":res.get("num_turns")}
Path(str(prefix)+"-model-metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
Path(str(prefix)+"-result.txt").write_text(res.get("result",""),encoding="utf-8")
Path(str(prefix)+"-test-output.json").write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding="utf-8")
endmap={r["path"]:r["sha256"] for r in end}
diff={r["path"]:{"start":r["sha256"],"end":endmap.get(r["path"])} for r in start if r["sha256"] is None or r["sha256"]!=endmap.get(r["path"])}
Path(str(prefix)+"-sha256-diff.json").write_text(json.dumps(diff,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"requested_model":model,"exit":result.returncode,"canonical_models":metadata["canonical_models"],"is_error":metadata["is_error"],"input_count":len(start),"changed_or_missing":list(diff),"tools":metadata["tools"]},ensure_ascii=False))
