"""여러 하차 후보 사이 거리가 12m 이내라는 가정의 회귀 시험입니다."""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.mobility.engine.car import hav
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter


def _encode(points):
    out=[];lat0=lon0=0
    for lon,lat in points:
        for value,old in ((round(lat*1e6),lat0),(round(lon*1e6),lon0)):
            value-=old;value=~(value<<1) if value<0 else value<<1
            while value>=32:out.append(chr((32|(value&31))+63));value>>=5
            out.append(chr(value+63))
        lat0,lon0=round(lat*1e6),round(lon*1e6)
    return ''.join(out)


def _records():
    points={1:(127.,37.5),2:(127.00005,37.5),3:(127.002,37.499001),4:(127.0022,37.499001),
            5:(127.002,37.501),6:(127.0022,37.501)}
    nodes=[{'id':n,'lon':p[0],'lat':p[1],'r':1} for n,p in points.items()]
    edges=[]
    for u,v,way,speed,main in [(1,2,10,15,1),(3,4,20,55,1),(5,6,30,70,1),(2,3,40,55,0),(2,5,50,70,0)]:
        ps=[points[u],points[v]]
        edges.append({'u':u,'v':v,'way':way,'len':round(hav(*ps),1),'ow':0,'hw':'primary','ms':str(speed),
                      'car':1,'bike':0,'bow':0,'g':_encode(ps),'main':main,'bmain':0})
    return {'nodes':nodes,'edges':edges}


def test_astar_preserves_fastest_of_spatially_separated_car_goal_candidates():
    records=_records();start=(127.,37.5);goal=(127.002,37.5)
    astar=GraphRouter(records=records);astar._load()
    snaps=astar._snap_many('car',*goal)
    assert len(snaps)==2
    assert abs(snaps[0].dist-snaps[1].dist)<12
    assert hav(snaps[0].pt,snaps[1].pt)>200
    got=astar.route(start,goal,'car')['paths'][0]
    reference=GraphRouter(records=records);reference.force_dijkstra=True
    expected=reference.route(start,goal,'car')['paths'][0]
    assert expected['time']<13000
    assert got['time']==pytest.approx(expected['time'],abs=1)
    assert got['points']['coordinates'][-1]==pytest.approx(expected['points']['coordinates'][-1])


def test_goal_within_one_metre_of_endpoint_keeps_fastest_candidate():
    records=_records();start=(127.,37.5);goal=(127.002005,37.5)
    astar=GraphRouter(records=records);astar._load()
    snaps=astar._snap_many('car',*goal)
    assert len(snaps)==2
    assert all(0<sn.d_u<1 for sn in snaps)
    got=astar.route(start,goal,'car')['paths'][0]
    reference=GraphRouter(records=records);reference.force_dijkstra=True
    expected=reference.route(start,goal,'car')['paths'][0]
    assert expected['time']<13000
    assert got['time']==pytest.approx(expected['time'],abs=1)
    assert got['points']['coordinates'][-1]==pytest.approx(expected['points']['coordinates'][-1])
