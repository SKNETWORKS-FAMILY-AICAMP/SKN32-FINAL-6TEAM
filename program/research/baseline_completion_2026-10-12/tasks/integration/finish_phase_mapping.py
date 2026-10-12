"""현재 이력에서 확인한 통합 구성 경로 세 개를 역사적 단계 분류에 연결합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil, json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
run=HERE/'checks/2026-10-12_063901_843730_isolated_integration'
assert (run/'result.json').is_file()
assert json.loads((run/'cleanup.json').read_text(encoding='utf-8'))['own_cluster_stopped']
p=CS/'scripts/map_commits_to_phase.py'
old=p.read_text(encoding='utf-8')
anchor='    ("app/composition.py", "Claude-Core", "P10"),'
addition='''
    # 실행 엔진 연결·대체 모델 조립·환경 템플릿은 과거 P10 통합 구성으로 분류한다.
    # 현재 팀 소유나 해당 모델의 채택·출시 판정을 뜻하지 않는다.
    ("app/infrastructure/llm_failover.py", "Claude-Core", "P10"),
    ("app/infrastructure/ollama_chat.py", "Claude-Core", "P10"),
    (".env.example", "Claude-Core", "P10"),'''
assert old.count(anchor)==1
backup=CS/'_backup'/(datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')+'_phase_mapping_integration')/p.relative_to(CS)
backup.parent.mkdir(parents=True)
shutil.copy2(p,backup)
p.write_text(old.replace(anchor,anchor+addition),encoding='utf-8')
print(json.dumps({'backup':backup.relative_to(ROOT).as_posix(),'paths':3}))
