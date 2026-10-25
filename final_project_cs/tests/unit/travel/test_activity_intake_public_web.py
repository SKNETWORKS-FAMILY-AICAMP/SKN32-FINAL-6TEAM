import inspect
from datetime import date
from app.domains.travel_ops.components.intake import places, pipeline, review

class Web:
 def __init__(self): self.calls=[]
 def lookup(self,name):
  self.calls.append(name)
  return {'status':'unknown','via':'public_web','reason':'search_http_429','checked_at':'2026-10-25T09:00:00+00:00','facts':{},'unknown':['business_hours','closed_days','date_specific']}

class Kakao:
 misses={'http_403':1}
 def search(self,*a,**k): return None

def test_normal_read_source_preserves_public_unknown():
 assert 'activity_web' in inspect.signature(pipeline.read_source).parameters, 'intake provider injection missing'
 web=Web()
 rows=pipeline.read_source('2026-10-26\n10:00 N서울타워',today=date(2026,10,25),our_places=[],kakao=Kakao(),activity_web=web)
 claim=next(r for r in rows if r['field']=='items[0].place')
 assert web.calls==['N서울타워']
 assert claim['value'] is None and claim['method']=='lookup' and claim['needs_review']
 ev=claim['evidence']
 assert ev['source']=='public_web' and ev['method']=='public_web_supplement'
 assert ev['public_web']['reason']=='search_http_429'
 assert ev['public_web']['upstream_status']=='unknown'
 assert ev['public_web']['checked_at']=='2026-10-25T09:00:00+00:00'
 assert 'kakao:http_403' in ev['blocked']
 row={'title':'N서울타워','kind':'activity','place':None,'claims':{'place':claim}}
 state,value=review.place_state(row)
 assert state=='unresolved' and value is None
 line=review._place_line(row,state,value)
 assert 'search_http_429' in line['text'] and '2026-10-25' in line['text']
 assert '없는 곳' in line['text']

def test_normal_api_passes_registered_provider_to_process():
 import ast
 from pathlib import Path
 assert 'activity_web' in inspect.signature(pipeline.process).parameters
 source=Path(pipeline.__file__).parents[2]/'entry/trip_api.py'
 tree=ast.parse(source.read_text(encoding='utf8'))
 calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and n.func.attr=='add_task' and n.args and isinstance(n.args[0],ast.Name) and n.args[0].id=='process']
 assert len(calls)==1
 provider=next(k.value for k in calls[0].keywords if k.arg=='activity_web')
 assert 'travel_sources' in ast.unparse(provider) and 'activity_web' in ast.unparse(provider)
 assert 'activity_web=activity_web' in inspect.getsource(pipeline.process)

def test_real_searxng_wildcard_robots_blocks_query_before_dispatch(monkeypatch):
 from app.domains.travel_ops.ports.data_sources.public_web_transport import PublicWebTransport, WebFailure
 import pytest
 transport=PublicWebTransport({'timeout_seconds':2,'max_response_bytes':10000,'max_url_chars':2048})
 calls=[]
 def wire(url,hosts):
  calls.append(url)
  return 'User-agent: *\nAllow: /info/en/about\nDisallow: /*?*q=*\n'
 monkeypatch.setattr(transport,'_wire',wire)
 with pytest.raises(WebFailure,match='robots_blocked'):
  transport('https://priv.au/search?q=public&format=json',['priv.au'],allow=lambda:True)
 assert calls==['https://priv.au/robots.txt']

def test_reviewed_official_query_uses_only_public_anchor():
 from app.domains.travel_ops.ports.data_sources.activity_public_web import PublicWebSearch
 from types import SimpleNamespace
 from urllib.parse import urlsplit,parse_qs
 urls=[]
 def fetch(url,hosts):
  urls.append(url)
  return {'results':[]}
 search=PublicWebSearch(limits={'timeout_seconds':1,'max_response_bytes':10000,'max_url_chars':2048},
  limiter=SimpleNamespace(acquire=lambda name:None),cache=None,fetch=fetch)
 search.discover({'name':'N서울타워','address':'서울특별시 용산구 남산공원길 105'},
  {'search_endpoint':'https://priv.au/search','search_hosts':['priv.au'],'query_style':'official'})
 assert parse_qs(urlsplit(urls[0]).query)=={'q':['N서울타워 공식'],'format':['json']}


def test_canonical_alias_hit_never_calls_public_web(monkeypatch):
 from app.domains.travel_ops.components.team_hooks import place_aliases as hook
 from app.domains.travel_ops.instances.activity.db_search.place_by_name import alias_target
 monkeypatch.setattr(hook,'target',alias_target)
 web=Web()
 done=places.resolve('N서울타워',our_places=[{'name':'남산서울타워','place_id':'canonical',
  'latitude':37.55,'longitude':126.98,'kind':'activity'}],activity_web=web)
 assert done.status=='resolved' and done.name=='남산서울타워' and done.place_id=='canonical'
 assert web.calls==[] and done.public_web is None


def test_customer_alias_is_not_replaced_by_original_public_identity():
 web=Web()
 done=places.resolve('N서울타워',our_places=[],aliases={'n서울타워':'고객이 정정한 다른 장소'},activity_web=web)
 assert done.status=='unresolved' and web.calls==[]


def test_meal_prefix_does_not_activate_activity_web():
 web=Web()
 done=places.resolve('점심 N서울타워',our_places=[],activity_web=web)
 assert done.status=='unresolved' and web.calls==[]


def test_public_evidence_does_not_override_customer_selected_park():
 claim={'method':'customer','value':{'name':'남산공원'},'evidence':{'public_web':{'reason':'unknown'}},'needs_review':False}
 assert review.place_state({'claims':{'place':claim},'place':claim['value']})==('customer',claim['value'])


def test_robots_wildcard_agent_scope_longest_rule():
 from app.domains.travel_ops.ports.data_sources.public_web_transport import _wildcard_robots_allowed as allowed
 text='User-agent: *\nDisallow: /private*\nAllow: /private/public$\n\nUser-agent: GPTBot\nDisallow: /\n'
 assert not allowed(text,'https://example.com/private/a')
 assert allowed(text,'https://example.com/private/public')
 assert not allowed(text,'https://example.com/private/public/extra')
 assert allowed(text,'https://example.com/')
 assert not allowed(text,'https://example.com/','GPTBot')


def test_robots_wildcard_normalizes_encoded_unreserved_octets():
 from app.domains.travel_ops.ports.data_sources.public_web_transport import _wildcard_robots_allowed as allowed
 assert not allowed('User-agent: *\nDisallow: /private*\n','https://example.com/%70rivate/secret')
 assert not allowed('User-agent: *\nDisallow: /*?*q=*\n','https://example.com/search?%71=public')


class ClaimDB:
 """Owned SQLite fixture executes product claim INSERT/read SQL, not PG acceptance."""
 def __init__(self,path):
  import sqlite3
  self.db=sqlite3.connect(path)
  self.db.executescript('CREATE TABLE trip_intakes(tenant_id text,intake_id text,status text,updated_at text);'
   'CREATE TABLE intake_claims(claim_id integer primary key, intake_id text,tenant_id text,revision integer,'
   'source_id text,field text,value_json text,method text,evidence text,needs_review integer,note text,created_at text);')
  self.db.execute("INSERT INTO trip_intakes VALUES('fixture','intake','reading',NULL)")
 def __call__(self): return self
 def __enter__(self): return self
 def __exit__(self,*a): self.db.commit()
 def transaction(self): return self
 def cursor(self): return self
 def execute(self,sql,args=()):
  self.sql=sql
  self.cur=self.db.execute(sql.replace('%s','?').replace('now()',"datetime('now')"),args)
  self.rowcount=self.cur.rowcount
 def fetchall(self):
  import json
  rows=self.cur.fetchall()
  if self.sql.startswith('SELECT source_id, field, value_json'):
   return [(r[0],r[1],json.loads(r[2]),r[3],json.loads(r[4]),bool(r[5]),r[6]) for r in rows]
  return rows


def test_normal_claim_sink_reload_retains_source_and_ui_reason(tmp_path):
 web=Web(); db=ClaimDB(tmp_path/'claims.sqlite')
 rows=pipeline.read_source('2026-10-26\n10:00 N서울타워',today=date(2026,10,25),our_places=[],
  kakao=Kakao(),activity_web=web,on_rows=pipeline._claim_sink(db,'fixture','intake','source'))
 reloaded=pipeline._claims(db,'fixture','intake',1)
 before=next(r for r in rows if r['field']=='items[0].place')
 after=next(r for r in reloaded if r['field']=='items[0].place')
 assert after['evidence']['public_web']==before['evidence']['public_web']
 assert after['method']=='lookup' and after['value'] is None and after['needs_review']
 state,value=review.place_state({'claims':{'place':after},'place':None})
 line=review._place_line({'title':'N서울타워','kind':'activity','claims':{'place':after}},state,value)
 assert 'search_http_429' in line['text'] and '2026-10-25' in line['text']
 assert 'kakao:http_403' in after['evidence']['blocked']
 db.db.close()
