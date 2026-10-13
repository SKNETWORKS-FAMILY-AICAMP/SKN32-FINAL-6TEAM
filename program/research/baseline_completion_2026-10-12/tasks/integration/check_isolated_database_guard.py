"""수정된 연결 경계의 허용·거절을 DB 연결 없이 확인합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast, hashlib, json
from psycopg.conninfo import conninfo_to_dict

HERE=Path(__file__).resolve().parent
runner=HERE/'run_isolated_integration.py'
tree=ast.parse(runner.read_text(encoding='utf-8'))
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='guarded_db')
port=43117
connected=[]
namespace={'port':port,'blocks':[],'conninfo_to_dict':conninfo_to_dict,'connect_db':lambda *a,**kw:connected.append((a,kw)) or True}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(runner),'exec'),namespace)
rows=[]
for label,conninfo,allowed in [
 ('own database',f'host=127.0.0.1 port={port} dbname=integration_test',True),
 ('own cluster administration',f'host=127.0.0.1 port={port} dbname=postgres',True),
 ('new migration fixture',f'host=127.0.0.1 port={port} dbname=acop_migtest_a012345678',True),
 ('new improvement fixture',f'host=127.0.0.1 port={port} dbname=acop_improve_f012345678',True),
 ('business name refused',f'host=127.0.0.1 port={port} dbname=business',False),
 ('existing port refused','host=127.0.0.1 port=5433 dbname=integration_test',False),
 ('foreign address refused',f'host=outside.invalid port={port} dbname=integration_test',False),
 ('default port refused','host=127.0.0.1 dbname=integration_test',False),
 ('default host refused',f'port={port} dbname=integration_test',False),
 ('unbounded scratch name refused',f'host=127.0.0.1 port={port} dbname=acop_migtest_not_owned',False),
]:
    try: actual=bool(namespace['guarded_db'](conninfo))
    except RuntimeError as exc:
        assert str(exc)=='isolated_database_required'
        actual=False
    rows.append(dict(label=label,expected=allowed,actual=actual,passed=allowed==actual))
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
output=HERE/'checks'/('isolated-db-guard-'+stamp+'.json')
output.write_text(json.dumps(dict(rows=rows,runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest(),scope='연결 함수를 대역으로 바꾼 순수 경계 검사; 실제 DB·외부 통신 없음'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=str(output),passed=sum(x['passed'] for x in rows),total=len(rows))))
assert all(x['passed'] for x in rows)
