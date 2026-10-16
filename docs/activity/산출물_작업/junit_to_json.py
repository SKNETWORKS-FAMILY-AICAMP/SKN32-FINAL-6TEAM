import xml.etree.ElementTree as ET, collections, json, sys
t=ET.parse(sys.argv[1]).getroot(); agg=collections.OrderedDict()
for tc in t.iter("testcase"):
    key=tc.get("classname").replace("tests.","",1)
    st="pass"
    if tc.find("failure") is not None or tc.find("error") is not None: st="fail"
    elif tc.find("skipped") is not None: st="skip"
    d=agg.setdefault(key,{"pass":0,"fail":0,"skip":0,"sec":0.0}); d[st]+=1; d["sec"]+=float(tc.get("time") or 0)
for d in agg.values(): d["sec"]=round(d["sec"],2)
out={"run_date":"2026-10-14","command":"pytest tests/unit/travel/activity + 활동 관련 단위·eval·DB 통합 + tests/scenario -m \"not live\"",
     "python":"3.12.15","pytest":"8.4.2","files":agg,
     "total":{k:sum(v[k] for v in agg.values()) for k in ("pass","fail","skip")}}
open(sys.argv[2],"w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=1))
print(out["total"], len(agg))
