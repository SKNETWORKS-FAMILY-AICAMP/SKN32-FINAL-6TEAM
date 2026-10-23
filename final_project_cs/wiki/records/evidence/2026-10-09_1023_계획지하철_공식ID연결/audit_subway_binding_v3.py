from pathlib import Path
from datetime import date, datetime
import json
import sys
import time

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.departure_context import capture

scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-binding-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
started = time.perf_counter()
rt = build_verifier(data_dir=root / 'datasets/mobility/processed', gh_url='', seoul_key='',
                    quiet=True, local_router=False)
index = rt.subway_stations
assert index is not None and index.station_count == 696
sc = json.loads((root / 'datasets/mobility/processed/mobility/station_coords.json').read_text(encoding='utf8'))
coordinates = sc if isinstance(sc, list) else list(sc['stations'].values())
matched = [row for row in coordinates if index.lookup(row['line'], row['station_nm'])]
assert len(coordinates) == 793 and len(matched) == 587
legs = [{'mode': 'subway', 'line': '05호선', 'from': '양평', 'to': '영등포구청'}]
case = {'id': 'official-station-binding', 'date': '2026-10-09', 'stage': 'planning',
        'depart_at': 600, 'arrive_by': 660, 'legs': legs, 'party': {}, 'first_visit': False,
        'no_alternatives': True}
route_result = rt.verify_case(case)
assert route_result.verdict == 'feasible', route_result.reason
contexts = []
for _ in range(4):
    context = capture([{'id': 'p', 'eta_min': route_result.arrive_min - 600, '_start': 600,
                       '_legs': legs, '_check': {'legs': legs}, '_lr': route_result.legs}],
        runtime=rt, origin={'lat': 37.52, 'lon': 126.88}, destination={'lat': 37.52, 'lon': 126.90},
        stage='planning', party={}, first_visit=False, service_date=date(2026, 10, 9), start_min=600)
    assert context['options']['p']['subway_identity']['station_id'] == '1005000522'
    assert context['options']['p']['subway_identity']['target_station_id'] == '1005000523'
    contexts.append({'basis': context['basis'], 'binding': context['options']['p']['subway_identity']})
assert not rt.changed_sources()
result = {'created_at': datetime.now().astimezone().isoformat(), 'runtime_stats': rt.stats,
          'source_signature': {'path': str(Path(rt.subway_station_source[0]).relative_to(root)), 'sha256': rt.subway_station_source[1]},
          'loaded_official_stations': index.station_count, 'loaded_official_lines': index.line_count,
          'coordinate_exact_matches': len(matched), 'coordinate_total': len(coordinates),
          'route_model_verdict': route_result.verdict, 'route_model_arrive_min': route_result.arrive_min,
          'native_capture_runs': contexts, 'unique_native_routes': 1,
          'run_elapsed_seconds': time.perf_counter() - started,
          'claim': 'Native runtime with owned datasets, one fixed route repeated four times. No live arrival, mapped trip, web comparison or measured boarding.'}
with (ev / 'native-runtime-binding-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps({'loaded_stations': index.station_count, 'exact_coordinate_matches': len(matched),
                  'route_verdict': route_result.verdict, 'captures': len(contexts)}, ensure_ascii=False))

