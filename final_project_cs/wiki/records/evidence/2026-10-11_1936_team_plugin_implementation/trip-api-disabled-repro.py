"""Real HTTP routes with synthetic identity/store/SQL cursor; no database or network."""
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services
from app.domains.travel_ops.entry import trip_api
from app.domains.travel_ops.instances.mobility import route_shape
from app.domains.travel_ops.modules.web_account import web_guard
from app.presentation.security import Principal
from app.presentation.errors import install_error_handlers

customer = uuid4()
trip_id = uuid4()
items = [SimpleNamespace(seq=0, kind="activity", title="출발", item_id=uuid4(), place={"name":"출발","latitude":37.57,"longitude":126.98}, detail={}),
         SimpleNamespace(seq=1, kind="mobility", title="도보", item_id=uuid4(), place=None, detail={"route_def":{"planned":"walk","options":[{"id":"walk"}]}}),
         SimpleNamespace(seq=2, kind="activity", title="도착", item_id=uuid4(), place={"name":"도착","latitude":37.571,"longitude":126.981}, detail={})]
calls = []
class Cursor:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,*args):
        assert "FROM dining.dn_place" in sql, "unexpected SQL: refuse synthetic reproduction"
        calls.append("dining_sql")
    def fetchall(self):return [(True,False)]
class Connection:
    def cursor(self):return Cursor()
@contextmanager
def connection():
    calls.append("connection")
    yield Connection()
class Store:
    def __init__(self,tenant):pass
    def latest(self,conn,identifier):return {"customer_id":customer},items
class Router:
    def route(self,a,b,profile):
        calls.append("mobility_graph_route")
        return {"paths":[{"points":{"coordinates":[list(a),list(b)]}}]}

results=[]
for reason in ("disabled","not_installed"):
    registry=TeamRegistry()
    if reason=="disabled":
        registry.declare_unavailable("dining",reason)
        registry.declare_unavailable("mobility",reason)
    table=BindingTable({},registry,"synthetic-disabled-http")
    with patch.object(trip_api,"get_connection",connection),patch.object(trip_api,"TripStore",Store),patch.object(web_guard,"assert_human_check_configured",lambda:None),patch.object(route_shape,"_engine",lambda:(Router(),None)),patch.object(route_shape,"_line_order",lambda:None):
        router=trip_api.build_trip_router()
        app=FastAPI();app.include_router(router);install_error_handlers(app)
        for route in router.routes:
            if route.path in ("/v1/trips","/v1/web/trips/{trip_id}/route-shapes"):
                dependency=route.dependant.dependencies[0].call
                app.dependency_overrides[dependency]=(lambda:Principal("synthetic-review",frozenset({"trip:write"}),"synthetic")) if route.path=="/v1/trips" else (lambda:("synthetic-review",customer))
        @app.middleware("http")
        async def bind(request,call_next):
            with bind_services(table):return await call_next(request)
        with TestClient(app) as client:
            before=len(calls)
            body={"request_id":"synthetic-review","customer_id":str(customer),"title":"합성 식사 검증","places":[{"key":"meal","name":"합성 식당","kind":"dining","lat":37.57,"lon":126.98,"attributes":{"dining_place_uid":str(uuid4())}}],"items":[{"seq":1,"kind":"dining","title":"합성 식사","place":"meal","starts_at":"2026-10-12T12:00:00+09:00","ends_at":"2026-10-12T13:00:00+09:00"}]}
            response=client.post("/v1/trips",json=body)
            results.append({"reason":reason,"route":"POST /v1/trips","status":response.status_code,"error":response.json().get("error"),"events":calls[before:]})
            before=len(calls)
            response=client.get(f"/v1/web/trips/{trip_id}/route-shapes")
            results.append({"reason":reason,"route":"GET /v1/web/trips/{id}/route-shapes","status":response.status_code,"shape_source":response.json().get("shapes",[{}])[0].get("source"),"events":calls[before:]})
print(json.dumps(results,ensure_ascii=False,indent=2))
