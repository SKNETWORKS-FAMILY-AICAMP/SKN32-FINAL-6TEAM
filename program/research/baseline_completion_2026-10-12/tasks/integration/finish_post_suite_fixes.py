"""여행 전체 종료 뒤에만 단독 시험 준비·차단 계정 안내 접합을 적용합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
whole=HERE/'checks/2026-10-12_060205_589376_isolated_integration'
assert (whole/'result.json').is_file(), 'Wait for the full travel result before changing product source'
assert json.loads((whole/'cleanup.json').read_text())['own_cluster_stopped']
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
backup=CS/'_backup'/(stamp+'_post_suite_integration')
changes={
 'tests/scenario/test_departure_express_db_v1.py': (
    "    wiring._STATE.update(mode='enabled', kw={})",
    "    # 먼저 실제 조립의 프로세스 설정 키를 준비한 뒤 합성 계산기를 꽂는다.\n    composition._configure_mobility(composition.get_settings())\n    wiring._STATE.update(mode='enabled', kw={})"),
 'tests/scenario/test_departure_party_db_v1.py': (
    "    wiring._STATE.update(mode='enabled',kw={})",
    "    # 단독 수집에서도 실제 조립의 설정 키와 합성 이동 상태를 맞춘다.\n    composition._configure_mobility(composition.get_settings())\n    wiring._STATE.update(mode='enabled',kw={})"),
 'app/domains/travel_ops/modules/web_account/web_cookie.py': (
    '이 계정은 이용이 제한되었습니다. 문의 화면에서 운영자에게 문의해 주세요.',
    '이 계정은 이용이 제한되었습니다. 문제 신고·건의 기록은 남길 수 있지만 개별 상담 답변이나 제한 해제를 약속하지 않습니다.'),
}
for path,(before,after) in changes.items():
    p=CS/path
    old=p.read_text(encoding='utf-8')
    assert old.count(before)==1,path
    dest=backup/path
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest)
    p.write_text(old.replace(before,after),encoding='utf-8')
print(json.dumps({'backup':backup.relative_to(ROOT).as_posix(),'changed':list(changes)},ensure_ascii=True))
