"""전체 원본 종료 후, 같은 새 전용 클러스터의 명시적 임시 DB 두 종류만 허용합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, shutil

HERE=Path(__file__).resolve().parent
whole=HERE/'checks/2026-10-12_060205_589376_isolated_integration'
assert (whole/'result.json').exists()
assert json.loads((whole/'cleanup.json').read_text())['own_cluster_stopped']
runner=HERE/'run_isolated_integration.py'
backup=HERE/'_backup'/(datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')+'_scratch_database_guard')
backup.mkdir()
shutil.copy2(runner,backup/runner.name)
old=runner.read_text(encoding='utf-8')
before="""        if (details.get('host', '127.0.0.1') not in ('127.0.0.1', 'localhost')
            or int(details.get('port', port)) != port
            or details.get('dbname', 'integration_test') not in ('integration_test', 'postgres')):"""
after="""        # 같은 새 전용 클러스터에서 아래 두 시험이 생성한 DB만 추가 허용한다.
        # 호스트·동적 포트 제한은 그대로이며 기존 업무 DB 이름은 허용하지 않는다.
        import re
        database = details.get('dbname', 'integration_test')
        allowed_database = (database in ('integration_test', 'postgres')
            or re.fullmatch(r'acop_(?:migtest|improve)_[0-9a-f]{10}', database) is not None)
        if (details.get('host') not in ('127.0.0.1', 'localhost')
            or str(details.get('port', '')) != str(port)
            or not allowed_database):"""
assert old.count(before)==1
runner.write_text(old.replace(before,after),encoding='utf-8')
print(json.dumps({'backup':str(backup),'before_sha256':hashlib.sha256((backup/runner.name).read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(runner.read_bytes()).hexdigest()}))
