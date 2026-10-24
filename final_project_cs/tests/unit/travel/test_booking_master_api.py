"""Real limits router/auth/runtime reader with a disk-backed SQLite SQL adapter.
No PostgreSQL/external API is opened; this is not a PostgreSQL integration claim.
"""
import hashlib
import json
import sqlite3
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Json
from app.presentation import security
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard, web_limits_api, features_api

NAME = 'travel.booking.enabled'

class Cursor:
    def __init__(self, conn):self.cur=conn.cursor();self.query=''
    def __enter__(self):return self
    def __exit__(self,*args):self.cur.close()
    def execute(self,query,args=()):
        self.query=query
        query=query.replace('%s','?').replace(' FOR UPDATE','').replace('now()',"CURRENT_TIMESTAMP")
        args=tuple(json.dumps(x.obj) if isinstance(x,Json) else x for x in args)
        self.cur.execute(query,args)
    def fetchone(self):return self.cur.fetchone()
    def fetchall(self):
        rows=self.cur.fetchall()
        if self.query.startswith('SELECT name, value, updated_at'):
            return [(n,json.loads(v),datetime.fromisoformat(at),actor) for n,v,at,actor in rows]
        if self.query.startswith('SELECT at, revision, actor'):
            return [(datetime.fromisoformat(r[0]),*r[1:5],json.loads(r[5]) if r[5] is not None else None,json.loads(r[6]) if r[6] is not None else None,r[7]) for r in rows]
        return rows

class Connection:
    def __init__(self,path):self.conn=sqlite3.connect(path,check_same_thread=False)
    def __enter__(self):return self
    def __exit__(self,*args):self.conn.close()
    def cursor(self):return Cursor(self.conn)
    def transaction(self):return self.conn

@pytest.fixture
def api(tmp_path,monkeypatch):
    db=tmp_path/'runtime.sqlite'
    with sqlite3.connect(db) as conn:
        conn.executescript('''
        CREATE TABLE runtime_limit_state(tenant_id TEXT PRIMARY KEY, revision INTEGER DEFAULT 0);
        CREATE TABLE runtime_limits(tenant_id TEXT,name TEXT,value TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_by TEXT,PRIMARY KEY(tenant_id,name));
        CREATE TABLE runtime_limit_events(seq INTEGER PRIMARY KEY,at TEXT DEFAULT CURRENT_TIMESTAMP,tenant_id TEXT,revision INTEGER,name TEXT,old_value TEXT,new_value TEXT,actor TEXT,key_id TEXT,reason TEXT);
        ''')
    monkeypatch.setattr(web_guard,'get_connection',lambda:Connection(db))
    monkeypatch.setattr(web_limits_api,'get_connection',lambda:Connection(db))
    monkeypatch.setattr(web_guard,'usage_today',lambda conn,tenant:{})
    keys=[('read','booking-test',{'limits:read'}),('write','booking-test',{'limits:write'}),('other','other-tenant',{'limits:write'})]
    monkeypatch.setattr(security,'_configured_keys',lambda:[(hashlib.sha256(k.encode()).hexdigest(),t,frozenset(s)) for k,t,s in keys])
    web_guard.clear_cache()
    settings_hook.register(lambda tenant,name:web_guard.values(tenant).get(name))
    app=FastAPI();app.include_router(web_limits_api.build_limits_router());app.include_router(features_api.build_public_features_router())
    with TestClient(app) as client:yield client,db
    settings_hook.clear();web_guard.clear_cache()

def headers(key):return {'Authorization':f'Bearer {key}'}
def read(client):return client.get('/admin/limits',headers=headers('read')).json()
def change(client,value,revision=None,key='write',**extra):
    revision=read(client)['revision'] if revision is None else revision
    return client.patch('/admin/limits',headers=headers(key),json={'expected_revision':revision,'actor':'test-operator','reason':'예약 OFF 검증','changes':{NAME:value},**extra})
def cell(view):return next(c for c in view['limits'] if c['name']==NAME)

def test_public_booking_default_then_explicit_on_then_current_off_persists(api):
    client,db=api
    assert cell(read(client))['value'] is False
    assert client.get('/v1/web/features').json().get('booking') is False
    assert change(client,True).status_code==200
    assert client.get('/v1/web/features').json()['booking'] is True
    assert settings_hook.booking_enabled('booking-test') is True
    assert change(client,False).status_code==200
    web_guard.clear_cache()
    assert cell(read(client))['value'] is False
    assert client.get('/v1/web/features').json()['booking'] is False
    assert settings_hook.booking_enabled('booking-test') is False
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT value FROM runtime_limits WHERE tenant_id=? AND name=?',('booking-test',NAME)).fetchone()==('false',)
    events=client.get('/admin/limits/events',headers=headers('read')).json()['events']
    assert [(e['old'],e['new']) for e in events]==[(True,False),(None,True)]
    assert all(e['actor']=='test-operator' and e['reason']=='예약 OFF 검증' for e in events)

def test_limits_auth_validation_revision_and_tenant_ownership(api):
    client,_=api
    assert client.get('/admin/limits').status_code==401
    assert client.patch('/admin/limits',json={}).status_code==401
    assert change(client,True,key='read').status_code==403
    for value in ['true',1,{},[]]:assert change(client,value).status_code==422
    assert change(client,True,reason='').status_code==422
    assert change(client,True,actor='').status_code==422
    assert change(client,True).status_code==200
    assert change(client,False,revision=0).status_code==409
    assert change(client,False,key='other',revision=0).status_code==200
    assert settings_hook.booking_enabled('booking-test') is True
    assert settings_hook.booking_enabled('other-tenant') is False
    assert change(client,None).status_code==200
    assert cell(read(client))['source']=='default'
    assert settings_hook.booking_enabled('booking-test') is False
