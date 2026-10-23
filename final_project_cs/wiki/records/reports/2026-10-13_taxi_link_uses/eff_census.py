"""역·정류장 접근 걷기(_eff)가 어느 갈래로 계산되는지 센다 — 읽기 전용(제품 코드 안 바꿈).

갈래: routed(검증된 길) · optimistic(접근 미검증 → 직선×계수와 큰 쪽) · capped(직선 2배 상한) · no_route(길 없음 → 직선) · no_router(라우터 없음 → 직선)
대상: 예시 일정(test_plan_v1 _run · _ns_it) + 새로 고정한 택시 12쌍 좌표를 대중교통 일정으로(출발 10:00 평일).
"""
import collections, json, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'final_project_cs'))
from tests.unit.travel.mobility import test_plan_v1 as T
from app.domains.travel_ops.instances.mobility.engine import plan as P

cnt = collections.Counter(); samples = collections.defaultdict(list)
orig = P.Planner._eff
def eff(self, lat1, lng1, lat2, lng2, straight_m):
    br = getattr(self.v, 'bike_router', None)
    if not straight_m:
        return orig(self, lat1, lng1, lat2, lng2, straight_m)
    if br is None or not getattr(getattr(br, 'router', None), 'is_local', False) or not br.available():
        cnt['no_router'] += 1
        return orig(self, lat1, lng1, lat2, lng2, straight_m)
    r = br.route('foot', lat1, lng1, lat2, lng2)
    if not r:
        kind = 'no_route'
    elif r.get('optimistic'):
        kind = 'optimistic_used_detour' if straight_m * self.detour > r['distance_m'] else 'optimistic_routed_longer'
    elif r['distance_m'] > straight_m * P.WALK_ROUTED_CAP_PROPOSED:
        kind = 'capped'
    else:
        kind = 'routed'
    cnt[kind] += 1
    if len(samples[kind]) < 6:
        samples[kind].append({'from': [lat1, lng1], 'to': [lat2, lng2], 'straight_m': round(straight_m),
                              'routed_m': None if not r else r['distance_m'], 'q': None if not r else r.get('quality'),
                              'err': None if r else br.last_error})
    return orig(self, lat1, lng1, lat2, lng2, straight_m)
P.Planner._eff = eff

T._run(); T._ns_it(modes=T.MODES_ALL)
rt = T._runtime()
od = json.load(open(ROOT / 'datasets/mobility/raw/taxi_web_20261013_v1/od-frozen-v1.json', encoding='utf-8'))['rows']
for o in od:
    places = [{"key": "a", "name": "A", "kind": "activity", "lat": o['from'][0], "lon": o['from'][1]},
              {"key": "b", "name": "B", "kind": "activity", "lat": o['to'][0], "lon": o['to'][1]}]
    items = [{"seq": 1, "kind": "activity", "title": "A", "place": "a", "starts_at": "2026-10-14T09:00:00+09:00", "ends_at": "2026-10-14T10:00:00+09:00"},
             {"seq": 2, "kind": "activity", "title": "B", "place": "b", "starts_at": "2026-10-14T12:00:00+09:00"}]
    try:
        P.plan(places, items, 1, {}, runtime=rt, modes=T.MODES_ALL)
    except Exception as ex:
        cnt['plan_error'] += 1; print(o['id'], type(ex).__name__, ex)
tot = sum(v for k, v in cnt.items() if k != 'plan_error')
print(json.dumps({'counts': dict(cnt), 'total_calls': tot}, ensure_ascii=False))
json.dump({'counts': dict(cnt), 'total_calls': tot, 'samples': samples}, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
