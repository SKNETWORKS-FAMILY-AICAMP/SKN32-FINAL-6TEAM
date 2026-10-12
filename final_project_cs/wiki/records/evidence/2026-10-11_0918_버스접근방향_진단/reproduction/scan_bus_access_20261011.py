exec(open(__file__.replace('scan_bus_access_','scan_bus_pairs_'),encoding='utf8').read().split('rows=[]')[0])
rows=[]
for p in design['pairs']:
    chosen=b.routes_between(p['alat'],p['alon'],p['blat'],p['blon'],radius)
    a=b.stops_near(p['alat'],p['alon'],radius);z=b.stops_near(p['blat'],p['blon'],radius)
    for r,x,y,span,da,db in chosen:
        def metric(x,y,da,db):
            dist=b.distance_m(r.route_id,x['seq'],y['seq'])
            return None if dist is None else (da+db)*1.3/1.04/60+dist/333.33
        before=metric(x,y,da,db)
        if before is None: continue
        alternatives=[]
        for da2,x2 in a:
            for db2,y2 in z:
                if x2['route_id']!=y2['route_id'] or x2['route_id']!=r.route_id or x2['seq']>=y2['seq']:continue
                m=metric(x2,y2,da2,db2)
                if m is not None:alternatives.append((m,x2,y2,da2,db2))
        best=min(alternatives,key=lambda t:t[0])
        if before-best[0]>3:
            rows.append({'pair':p,'route':r.route_nm,'before_pair':[x,y,da,db],'alternative':best[1:],'estimated_gain_min':before-best[0],'pair_count':len(alternatives)})
rows.sort(key=lambda r:r['estimated_gain_min'],reverse=True)
out=root/'final_project_cs/wiki/records/evidence/2026-10-11_0918_버스접근방향_진단/bus-access-scan-v1.json'
with out.open('x',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
print(json.dumps([{'id':r['pair']['id'],'a':r['pair']['a'],'b':r['pair']['b'],'route':r['route'],'gain_estimate':round(r['estimated_gain_min'],1),'count':r['pair_count']} for r in rows[:12]],ensure_ascii=False))
