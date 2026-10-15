"""원격 호출 없이 30ms 취소 시험의 실제 진행 단계를 측정한다."""
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
CS = HERE.parents[4] / 'final_project_cs'
sys.path.insert(0, str(CS))
from tests.unit.ports.test_team_ports import make_task, Team
from app.core.registry import TeamRegistry
from app.core.remote_team.a2a_executor import A2ATeamExecutor


def trial(mode):
    events = []
    start = perf_counter()
    def event(name):
        events.append({'stage': name, 'milliseconds': round((perf_counter()-start)*1000, 3)})
    def resolver(capability):
        event('resolver_entered')
        return 'endpoint'
    async def async_resolver(capability):
        event('resolver_entered')
        return 'endpoint'
    class Transport:
        async def submit(self, endpoint, task):
            event('submit')
            return {'status': 'running', 'task_id': 'remote-1'}
        async def poll(self, remote, task):
            event('poll')
            await asyncio.sleep(10)
        async def cancel(self, remote):
            event('cancel')
    async def execute():
        task = make_task().model_copy(update={'deadline_at': datetime.now(UTC)+timedelta(milliseconds=30)})
        event('deadline_set')
        executor = A2ATeamExecutor(Transport(), async_resolver if mode == 'async_control' else resolver, registry=TeamRegistry([Team()]))
        event('executor_constructed')
        result = await executor.execute(task)
        event('returned')
        return result.failure_code
    code = asyncio.run(execute())
    return {'mode': mode, 'failure_code': code, 'events': events}


rows = [trial(mode) for _ in range(3) for mode in ('original_sync', 'async_control')]
source = CS/'app/core/remote_team/a2a_executor.py'
result = {'measured_at': datetime.now(UTC).isoformat(), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'trials': rows, 'scope': 'in-process transport only; no HTTP, DB or model calls'}
output = Path(sys.argv[1])
if output.exists():
    raise SystemExit('출력 파일이 이미 존재합니다. 새 파일 이름이 필요합니다.')
output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
