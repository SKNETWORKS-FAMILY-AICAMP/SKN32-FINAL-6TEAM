# minimal kiwi decoder for figma/figjam canvas.fig
import struct, sys, json
sys.stdout.reconfigure(encoding="utf-8")


class R:
    def __init__(s, b): s.b, s.i = b, 0
    def byte(s):
        v = s.b[s.i]; s.i += 1; return v
    def vu(s):
        r = sh = 0
        while True:
            c = s.byte(); r |= (c & 127) << sh; sh += 7
            if c < 128 or sh >= 35: return r
    def vi(s):
        v = s.vu(); return (~(v >> 1)) if v & 1 else (v >> 1)
    def vu64(s):
        r = sh = 0
        while True:
            c = s.byte(); r |= (c & 127) << sh; sh += 7
            if c < 128 or sh >= 70: return r
    def fl(s):
        first = s.byte()
        if first == 0: return 0.0
        bits = first | (s.byte() << 8) | (s.byte() << 16) | (s.byte() << 24)
        bits = ((bits << 23) | (bits >> 9)) & 0xFFFFFFFF
        return struct.unpack("<f", struct.pack("<I", bits))[0]
    def st(s):
        j = s.b.index(0, s.i); v = s.b[s.i:j].decode("utf-8", "replace"); s.i = j + 1; return v


def schema(b):
    r = R(b); defs = []
    for _ in range(r.vu()):
        name = r.st(); kind = r.byte(); fields = []
        for _ in range(r.vu()):
            fn = r.st(); t = r.vi(); arr = r.byte(); val = r.vu()
            fields.append((fn, t, arr, val))
        defs.append((name, kind, fields))
    return defs


BUILTIN = {-1: "bool", -2: "byte", -3: "int", -4: "uint", -5: "float", -6: "string", -7: "int64", -8: "uint64"}


def decode(defs, data, root="Message"):
    r = R(data); byname = {d[0]: i for i, d in enumerate(defs)}

    def val(t, arr):
        if arr:
            return [val(t, 0) for _ in range(r.vu())]
        if t < 0:
            k = BUILTIN[t]
            if k == "bool": return bool(r.byte())
            if k == "byte": return r.byte()
            if k == "int": return r.vi()
            if k == "uint": return r.vu()
            if k == "float": return r.fl()
            if k == "string": return r.st()
            if k == "int64":
                v = r.vu64(); return (~(v >> 1)) if v & 1 else (v >> 1)
            return r.vu64()
        name, kind, fields = defs[t]
        if kind == 0:
            v = r.vu()
            for f in fields:
                if f[3] == v: return f[0]
            return v
        if kind == 1:
            return {f[0]: val(f[1], f[2]) for f in fields}
        obj = {}
        byval = {f[3]: f for f in fields}
        while True:
            fid = r.vu()
            if fid == 0: return obj
            f = byval[fid]
            obj[f[0]] = val(f[1], f[2])
    return val(byname[root], 0)


if __name__ == "__main__":
    defs = schema(open("schema.bin", "rb").read())
    msg = decode(defs, open("data.bin", "rb").read())
    nodes = msg.get("nodeChanges", [])
    print("nodes", len(nodes))
    keep = []
    for n in nodes:
        tr = n.get("transform") or {}
        txt = (n.get("textData") or {}).get("characters")
        keep.append(dict(id=f"{n['guid']['sessionID']}:{n['guid']['localID']}",
                         parent=(f"{n['parentIndex']['guid']['sessionID']}:{n['parentIndex']['guid']['localID']}" if n.get("parentIndex") else None),
                         type=n.get("type"), name=n.get("name"), text=txt,
                         x=round(tr.get("m02", 0)), y=round(tr.get("m12", 0)),
                         w=round((n.get("size") or {}).get("x", 0)), h=round((n.get("size") or {}).get("y", 0)),
                         shape=(n.get("shapeWithTextType")),
                         conn=({"s": n["connectorStart"].get("endpointNodeID"), "e": n["connectorEnd"].get("endpointNodeID")} if n.get("connectorStart") else None)))
    json.dump(keep, open("nodes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0, default=str)
