"""Load an explicitly supplied public business-fact snapshot into the isolated test DB."""
import json
from datetime import datetime
from pathlib import Path
from psycopg.types.json import Jsonb
from uuid import NAMESPACE_URL, uuid5


def seed(conn, path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    load=uuid5(NAMESPACE_URL,'nambu-public-csv-replay')
    conn.execute("INSERT INTO dining.dn_load_meta (load_id,source_code,fetched_at,schema_version,scope,row_count,raw_uri,status) "
        "VALUES (%s,'tourapi_kor_food',now(),'public-csv-facts-v1','nambu-vicinity',%s,'public-dining-export','loaded') "
        "ON CONFLICT (load_id) DO NOTHING",(load,len(data['places'])))
    for place in data['places']:
        uid=place['place_uid']
        conn.execute("INSERT INTO dining.dn_place (place_uid,name_ko,road_address,lat,lng,coord_source,area,record_status,is_synthetic) "
            "VALUES (%s,%s,%s,%s,%s,'tourapi_kor_food',%s,'unknown',false) ON CONFLICT (place_uid) DO NOTHING",
            (uid,place['name'],place['road_address'],place['lat'],place['lon'],place['area']))
        record=uuid5(NAMESPACE_URL,f'nambu-public-csv-record:{uid}')
        conn.execute("INSERT INTO dining.dn_source_record (record_id,load_id,source_code,external_id,place_uid,match_status,raw_json) "
            "VALUES (%s,%s,'tourapi_kor_food',%s,%s,'confirmed',%s) ON CONFLICT (record_id) DO NOTHING",
            (record,load,place['content_id'],uid,Jsonb({'name':place['name'],'weekly':place['weekly'],
                'source_snapshot':data['source'],'source_updated_at':place['source_updated_at']})))
        for weekday,rule in place['weekly'].items():
            rid=uuid5(NAMESPACE_URL,f'nambu-public-replay:{uid}:{weekday}')
            conn.execute("INSERT INTO dining.dn_hours_rule (rule_id,place_uid,source_code,record_id,rule_kind,weekday,coverage,break_state,"
                "extract_method,rules_version,valid_from) VALUES (%s,%s,'tourapi_kor_food',%s,'weekly',%s,%s,'unknown',"
                "'regex','public-csv-replay',%s) ON CONFLICT (rule_id) DO NOTHING",
                (rid,uid,record,int(weekday),rule['coverage'],datetime.fromisoformat(place['source_updated_at']).date()))
            for seq,(start,end) in enumerate(rule['intervals'],1):
                conn.execute("INSERT INTO dining.dn_hours_interval (rule_id,seq,open_min,close_min,last_order_state) "
                    "VALUES (%s,%s,%s,%s,'unknown') ON CONFLICT (rule_id,seq) DO NOTHING",(rid,seq,start,end))
    return len(data['places'])
