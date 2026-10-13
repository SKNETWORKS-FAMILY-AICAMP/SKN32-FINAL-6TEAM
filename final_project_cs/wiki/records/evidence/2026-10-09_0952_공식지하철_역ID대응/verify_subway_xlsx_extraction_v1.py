from pathlib import Path
from datetime import datetime
import hashlib
import json
import openpyxl

root = Path(__file__).resolve().parents[2]
state = json.loads((Path(__file__).parent / 'subway-station-map-work-v2.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
raw = root / 'datasets/mobility/raw/subway_realtime_station_20261009_v1/realtime_station_20260902.xlsx'
derived = root / 'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json'
doc = json.loads(derived.read_text(encoding='utf8'))
book = openpyxl.load_workbook(raw, read_only=True, data_only=True)
rows = list(book['Data'].iter_rows(values_only=True))
assert len(rows) - 1 == doc['station_count'] == 696
assert doc['source_sha256'] == hashlib.sha256(raw.read_bytes()).hexdigest()
for offset, (row, actual) in enumerate(zip(rows[1:], doc['stations'], strict=True), start=2):
    assert [str(row[0]), str(row[1]), row[2], row[3], row[2], offset] == [actual[k] for k in
           ('line_id', 'station_id', 'station', 'line', 'query_station', 'source_row')]
book.close()
with (ev / 'xlsx-row-verification-v1.json').open('x', encoding='utf8') as f:
    json.dump({'created_at': datetime.now().astimezone().isoformat(), 'raw_sha256': doc['source_sha256'],
               'exact_source_row_matches': 696, 'station_count': 696, 'sheet': 'Data', 'range': 'A2:D697',
               'columns': ['SUBWAY_ID', 'STATN_ID', 'STATN_NM', '호선이름'], 'read_only': True}, f, ensure_ascii=False, indent=2)
print('Official source rows and extracted identity: 696/696 match')
