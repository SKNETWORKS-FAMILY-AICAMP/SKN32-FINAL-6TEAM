"""보존한 두 좌표의 도로 선택을 새 출력 파일로 재계산한다."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('기존 결과를 덮지 않습니다. 새 출력 이름을 지정하세요.')
    evidence = Path(__file__).resolve().parent
    repo = next(root for root in evidence.parents if (root/'app/domains/travel_ops').is_dir())
    previous = json.loads((evidence/'legacy-snap-real-probe-v1.json').read_text(encoding='utf8'))
    conditions = previous['observations'][:2]
    sys.path.insert(0, str(repo))
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    router = GraphRouter(repo.parent/'datasets/mobility/processed/mobility/road_graph_v2')
    router.warm(('car',))
    rows = []
    for repeat in range(3):
        for condition in conditions:
            path = router.route(condition['requested_start'], condition['requested_end'], profile='car')['paths'][0]
            rows.append(dict(repeat=repeat+1, label=condition['label'],
                             requested_start=condition['requested_start'], requested_end=condition['requested_end'],
                             distance_m=path['distance'], model_seconds=path['time']/1000,
                             snap_m=path['snap_m'], quality=path['quality'], turns=path['turn_restrictions']))
    result = dict(created_at=datetime.now().astimezone().isoformat(), calls=len(rows), api_calls=0,
                  independent_holdout=False, observations=rows)
    with args.output.open('x', encoding='utf8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(dict(calls=len(rows), snap_m=[row['snap_m'] for row in rows]), ensure_ascii=True))


if __name__ == '__main__':
    main()
