"""Oracle ARM control/ 환경 파일을 x600 서버와 같은 두 파일(.env + .env.apikeys)로 나눈다.
MODE=dry 면 쓰지 않고 결과만 보인다. MODE=apply 면 백업 후 적용한다(컨테이너는 건드리지 않는다)."""
import fcntl, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

MODE = sys.argv[1]
KEYNAMES = set(sys.argv[2].split())
BASE = Path("/home/ubuntu/tripilot-serving")
C = BASE / "control"
os.chdir(C)

lock = open(BASE / "deploy.lock", "w")
for _ in range(180):
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except BlockingIOError:
        time.sleep(5)
else:
    sys.exit("LOCK_TIMEOUT")
print("lock acquired")

if not (C / "app.env").exists() or not (C / "control.env").exists():
    sys.exit("app.env/control.env 없음 — 이미 옮겼나?")
TAG = json.loads((BASE / "state.json").read_text())["current"][:12]
print("current tag", TAG)


def read(p):
    return [l.rstrip("\r\n") for l in open(p, encoding="utf-8") if l.strip() and not l.lstrip().startswith("#")]


app, ctl = read("app.env"), read("control.env")
names = [l.split("=", 1)[0] for l in app + ctl]
dups = {n for n in names if names.count(n) > 1}
assert not dups, dups
env_lines = ["# guguroute Oracle ARM (develop) — x600 서버와 같은 구조: 설정·비밀값 = .env, 외부 API 키·호출 한도 = .env.apikeys",
             "# compose 변수(DB_PASSWORD·CHAT_URL·EMBED_URL·MOBILITY_DIR·CHAT_ID·EMBED_ID)는 옛 control.env 에서 옮겼다(2026-10-13)"]
env_lines += ctl + [l for l in app if l.split("=", 1)[0] not in KEYNAMES]
key_lines = ["# guguroute Oracle ARM (develop) — 외부 API 키·호출 한도. 이름은 저장소 .env.apikeys.example 을 따른다"]
key_lines += [l for l in app if l.split("=", 1)[0] in KEYNAMES]
print(".env names:", [l.split("=", 1)[0] for l in env_lines if not l.startswith("#")])
print(".env.apikeys names:", [l.split("=", 1)[0] for l in key_lines if not l.startswith("#")])

EDITS = {
    "compose.yml": [("env_file: [app.env]", "env_file: [.env, .env.apikeys]       # x600 서버와 같은 두 파일 — 뒤가 이긴다", 2)],
    "deploy.py": [('CONTROL / "control.env"', 'CONTROL / ".env"', 2)],
    "pin_model.py": [("base/'control'/'control.env'", "base/'control'/'.env'", 1)],
    "fix_env.py": [("p=base/'control'/'app.env'", "p=base/'control'/'.env'", 1), ("backup/'app.env'", "backup/'.env'", 1)],
    "bootstrap.py": [("[('app.env',app),('control.env',{", "[('.env',{**app,", 1),
                     ("(base/'mobility'/'processed').mkdir",
                      "(control/'.env.apikeys').touch(mode=0o600,exist_ok=True)  # 외부 API 키는 x600 서버처럼 .env.apikeys 에 따로 둔다\n"
                      "(base/'mobility'/'processed').mkdir", 1)],
}
new_text = {}
for f, reps in EDITS.items():
    s = (C / f).read_text(encoding="utf-8")
    for a, b, n in reps:
        assert s.count(a) == n, (f, a, s.count(a))
        s = s.replace(a, b)
    if f.endswith(".py"):
        compile(s, f, "exec")
    new_text[f] = s
print("edits validated:", list(EDITS))


def fingerprint(env_file, compose_text):
    tmp = C / ".compose.check.yml"
    tmp.write_text(compose_text, encoding="utf-8")
    try:
        raw = subprocess.check_output(["docker", "compose", "--env-file", env_file, "-f", str(tmp), "config", "--format", "json"],
                                      env={**os.environ, "IMAGE_TAG": TAG}, text=True, cwd=C)
    finally:
        tmp.unlink()
    d = json.loads(raw)
    out = {}
    for s, v in sorted(d["services"].items()):
        env = v.get("environment") or {}
        out[s] = {k: hashlib.sha256(str(val).encode()).hexdigest()[:12] for k, val in env.items()}
        out[s]["__volumes"] = [x.get("source") for x in v.get("volumes") or []]
        out[s]["__image"] = v.get("image")
    return out


before = fingerprint(str(C / "control.env"), (C / "compose.yml").read_text(encoding="utf-8"))

if MODE != "apply":
    # 새 파일을 임시 이름으로 만들어 같은 결과가 나오는지만 본다
    td = C / ".envcheck"
    td.mkdir(exist_ok=True)
    try:
        (td / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        (td / ".env.apikeys").write_text("\n".join(key_lines) + "\n", encoding="utf-8")
        ctext = new_text["compose.yml"].replace("[.env, .env.apikeys]", "[.envcheck/.env, .envcheck/.env.apikeys]")
        after = fingerprint(str(td / ".env"), ctext)
    finally:
        shutil.rmtree(td)
else:
    bk = C / "_backup" / (time.strftime("%Y-%m-%d_%H%M") + "_env_layout_like_x600")
    bk.mkdir(parents=True)
    for f in ["app.env", "control.env", "app.env.bak_20261013_0958_serpapi", *EDITS]:
        if (C / f).exists():
            shutil.copy2(C / f, bk / f)
    print("backup", bk)
    for p, ls in ((".env", env_lines), (".env.apikeys", key_lines)):
        (C / p).write_text("\n".join(ls) + "\n", encoding="utf-8")
        os.chmod(C / p, 0o600)
    for f, s in new_text.items():
        st = (C / f).stat()
        (C / f).write_text(s, encoding="utf-8")
        os.chown(C / f, st.st_uid, st.st_gid)
    after = fingerprint(str(C / ".env"), new_text["compose.yml"])
    (bk / "fingerprint.json").write_text(json.dumps({"before": before, "after": after}, indent=1))
    # 옛 파일은 지우지 않고 백업 폴더로 옮긴다
    for f in ["app.env", "control.env", "app.env.bak_20261013_0958_serpapi"]:
        if (C / f).exists():
            (C / f).unlink()  # 위에서 이미 bk 에 복사했다
    print("moved old env files into backup")

diff = {}
for s in sorted(set(before) | set(after)):
    b, a = before.get(s, {}), after.get(s, {})
    ks = {k for k in set(b) | set(a) if b.get(k) != a.get(k)}
    if ks:
        diff[s] = sorted(ks)
print("services:", {s: len(v) for s, v in after.items()})
print("DIFF (빈 값이면 컨테이너가 받는 설정이 똑같다):", diff)
