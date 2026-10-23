"""Read-only companion: active SQL references and view dependencies, no row values."""
import ast
import json
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

OLD = {'orders','order_items','shipments','returns','products'}
SQL_REF = re.compile(r'\b(?:FROM|JOIN|UPDATE|INSERT\s+INTO|DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?)\s+(?:public\.)?"?(orders|order_items|shipments|returns|products)\b', re.I)

def code_references(root):
    hits=[]
    files=0
    for area in ('app','scripts','eval','tests'):
        for folder,dirs,names in os.walk(root/area):
            dirs[:]=[d for d in dirs if d not in {'_backup','legacy','__pycache__','.git'}]
            for name in names:
                p=Path(folder)/name
                if p.suffix!='.py': continue
                files+=1
                try: tree=ast.parse(p.read_text(encoding='utf-8-sig'))
                except (SyntaxError,UnicodeError):
                    hits.append({'path':p.relative_to(root).as_posix(),'kind':'parse_error'});continue
                for node in ast.walk(tree):
                    if isinstance(node,(ast.Constant,ast.JoinedStr)):
                        value=(node.value if isinstance(node,ast.Constant) and isinstance(node.value,str)
                               else ''.join(v.value for v in node.values if isinstance(v,ast.Constant) and isinstance(v.value,str)) if isinstance(node,ast.JoinedStr) else '')
                        for m in SQL_REF.finditer(value):
                            hits.append({'path':p.relative_to(root).as_posix(),'line':node.lineno,'table':m[1].lower(),'kind':'SQL reference candidate'})
    # String constants under f-strings can be visited twice; keep unique candidates.
    hits=list({json.dumps(h,sort_keys=True):h for h in hits}.values())
    return {'python_files_checked':files,'hits':hits,
            'limits':'AST strings/f-string literal segments only; dynamically assembled names, ORM and manual queries are not fully covered. Guard tests and retired-asset checker hits need manual classification.'}

def view_dependencies(dsn):
    with psycopg.connect(dsn.replace('postgresql+psycopg://','postgresql://',1),connect_timeout=8,
        row_factory=dict_row,options='-c default_transaction_read_only=on -c statement_timeout=15000') as c:
        rows=c.execute("""SELECT DISTINCT nv.nspname AS view_schema,v.relname AS view_name,
            nt.nspname AS target_schema,t.relname AS target_name
            FROM pg_rewrite r JOIN pg_class v ON v.oid=r.ev_class
            JOIN pg_namespace nv ON nv.oid=v.relnamespace
            JOIN pg_depend d ON d.classid='pg_rewrite'::regclass AND d.objid=r.oid
            JOIN pg_class t ON t.oid=d.refobjid AND d.refclassid='pg_class'::regclass
            JOIN pg_namespace nt ON nt.oid=t.relnamespace
            WHERE v.relkind IN ('v','m') AND v.oid<>t.oid
            AND nv.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3,4""").fetchall()
        return {'all_view_dependencies':rows,'legacy_view_dependencies':[r for r in rows if r['target_name'] in OLD],
                'transaction_read_only':c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']}

if __name__=='__main__':
    import app
    from app.core.settings import get_settings
    root=Path(app.__file__).resolve().parent.parent
    print(json.dumps({'code':code_references(root),'views':view_dependencies(get_settings().database_url)},ensure_ascii=False))
