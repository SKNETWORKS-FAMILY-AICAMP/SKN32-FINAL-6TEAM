"""SQL 목록과 불변식 집계를 정본 파일에서 생성한다."""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]


def state_inventory(root: Path = ROOT) -> dict:
    """현재 허브·cs 결정/계약과 W01~W25의 현재 wiki 대상만 열거한다."""
    spec = importlib.util.spec_from_file_location('wiki_check_inventory', Path(__file__).with_name('check_wiki.py'))
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    roots = [root/'wiki', root/'final_project_cs/wiki']
    docs, _, _ = check.collect_docs([str(p) for p in roots])
    findings = root/'program/research/wiki_review_2026-10-11/findings-v2.json'
    targets = defaultdict(list)
    if findings.exists():
        for item in json.loads(findings.read_text(encoding='utf-8-sig'))['findings']:
            for target in item.get('targets', []):
                targets[target].append(item['id'])
    rows = []
    for name in docs:
        path = Path(name)
        rel = path.relative_to(root).as_posix()
        raw = path.read_text(encoding='utf-8-sig')
        fm = check.front_matter(raw) or {}
        if fm.get('type') not in {'decision', 'contract'} and rel not in targets:
            continue
        if path.name.endswith('.generated.md') or fm.get('status') == 'deprecated':
            continue
        required = ['implementation_status', 'validation_status']
        if fm.get('type') == 'decision':
            required.insert(0, 'decision_status')
        rows.append({
            'path': rel, 'type': fm.get('type'), 'w_ids': targets.get(rel, []),
            'review_status': fm.get('status', 'draft'),
            'decision_status': fm.get('decision_status', 'unverified'),
            'implementation_status': fm.get('implementation_status', 'unverified'),
            'validation_status': fm.get('validation_status', 'unverified'),
            'verified_at': fm.get('verified_at', 'unverified'),
            'deployment_status': 'unverified',
            'missing_fields': [f for f in required if not fm.get(f)],
        })
    return {'scope': 'hub・cs current decision/contract + W01-W25 current wiki targets; excludes deprecated/generated/records/backup/staging/sample',
            'meaning': 'Metadata inventory only. Missing fields and uninspected deployment are unverified; no runtime or semantic acceptance claim.',
            'documents': rows}


def render_state_inventory() -> dict[Path, str]:
    inventory = state_inventory()
    rows = inventory['documents']
    missing = sum(bool(r['missing_fields']) for r in rows)
    body = f'''[실측: 작업 트리] 현재 적용 대상 **{len(rows)}개**, 상태 필드 미적용 **{missing}개**. 실행·배포 완료 수가 아닙니다.

범위: 허브·cs의 현재 `decision`·`contract` 전체와 W01~W25의 현재 wiki 대상. `deprecated`·생성물·기록·백업·이관 폴더·sample 참고 구현은 제외합니다. 사용자 선택을 결정 필드로 자동 복사하거나 상태를 승격하지 않습니다.

아래 값은 각 페이지 머리말을 그대로 읽은 것입니다. 필드가 없으면 `unverified`입니다. 환경별 본문 표·실행 근거는 페이지를 열어 확인해야 하며 이 생성기는 배포를 조사하지 않아 모두 `unverified`로 표시합니다.

| 현재 문서 | 문서 검토 | 결정 | 구현 | 검증 | 환경 배포 | 확인 시각 | 미적용 필드 |
|---|---|---|---|---|---|---|---|
'''
    destination = ROOT/'wiki/governance/implementation-inventory.generated.md'
    import os
    for row in rows:
        link = Path(os.path.relpath(ROOT/row['path'], destination.parent)).as_posix()
        body += f"| [{row['path']}]({link}) | {row['review_status']} | {row['decision_status']} | {row['implementation_status']} | {row['validation_status']} | unverified | {row['verified_at']} | {', '.join(row['missing_fields']) or '—'} |\n"
    body += '''
## 읽는 법·후속 적용

미적용 필드는 검사 위반과 다릅니다. 기존 초안의 선택 필드를 일괄 필수로 바꾸지 않습니다. 문서 담당자는 기능 구현 결과를 받으면 해당 변경의 범위·실행 시각·증거를 본문 환경별 표에 연결하고 필드를 채웁니다. 병렬 작업 중인 기능 문서는 담당자가 적용합니다.

`implemented-local`·`implemented-partial`은 기존 표기이며 새 표준 값으로 채택하지 않습니다. 개별 담당자의 범위 확인이 필요합니다. `draft`는 채택 취소, `accepted`는 구현 완료를 뜻하지 않습니다.

## 관계

- [상태 표시 안내](implementation-state.md) — 필드 의미와 환경별 근거
- [리뷰 정책](review-policy.md) — 문서 검토와 승격 조건
'''
    page = generated('현재 결정·계약 상태 적용 목록', '현재 결정·계약과 개정 대상의 미적용 필드를 자동 열거한다', body)
    page = page.replace('domain: neutral\n', 'domain: neutral\nimpl_scope: cs — 현재 제품과 허브 결정·계약의 적용 목록이며 sample 참고 구현의 실행 상태를 추정하지 않는다\n', 1)
    return {destination: page,
            destination.with_suffix('.json'): json.dumps(inventory, ensure_ascii=False, indent=2)+'\n'}


def catalog_rows(text: str) -> list[tuple[str, str]]:
    # 본문의 참조·예시·과거 집계는 세지 않고, 카탈로그 표의 첫 열만 센다.
    text = text.split('## 코드 쪽 역방향 표식', 1)[0]
    rows = re.findall(r'^\|\s*`(INV-CS-[A-Z]+-\d{3})`\s*\|[^\n]*?\|\s*(automated|review|manual)\s*\|', text, re.M)
    counts = Counter(x for x, _ in rows)
    duplicates = sorted(x for x, n in counts.items() if n > 1)
    if duplicates:
        raise ValueError('카탈로그 ID 중복: ' + ', '.join(duplicates))
    return rows


def generated(title: str, description: str, body: str) -> str:
    return f'''---
type: guide
title: {title}
description: {description}
status: draft
domain: neutral
domain_note: 코드·카탈로그 파일의 자동 집계이며 제품 도메인 사례를 판정하지 않는다
automation:
  command: python program/scripts/build_wiki_catalogs.py
  owner: process:wiki-catalogs
  manual_edit: false
---

# {title}

{body.rstrip()}
'''


def render() -> dict[Path, str]:
    base = ROOT / 'final_project_cs'
    sql_root = base / 'app/infrastructure/db/migrations'
    spec = importlib.util.spec_from_file_location('migration_plan', base/'app/infrastructure/db/migration_plan.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    active, historical = module.migration_files(sql_root)
    pending = sorted((sql_root / 'pending').glob('*.sql'))
    sql_body = f'''[실측: 작업 트리] 실행 대상 SQL **{len(active)}개**, 역사 보존 SQL **{len(historical)}개**, 보류 폴더 SQL **{len(pending)}개**. 파일 수이며 DB 적용 수가 아닙니다.

근거: [실행기](../../app/infrastructure/db/migrate.py), [SQL 적용 안내](migrations.md). 생성 명령은 워크스페이스 루트에서 실행합니다.

## 실행 대상

| SQL 파일 |
|---|
''' + '\n'.join(f'| [{p.name}](../../app/infrastructure/db/migrations/{p.name}) |' for p in active)
    sql_body += '\n\n## 역사 보존 — 실행 제외\n\n' + '\n'.join(f'- [{p.name}](../../app/infrastructure/db/migrations/{p.name})' for p in historical)
    sql_body += '\n\n## 보류 폴더\n\n' + '\n'.join(f'- [{p.name}](../../app/infrastructure/db/migrations/pending/{p.name})' for p in pending)
    sql_body += '\n\n## 관계\n\n- [여행 데이터 안내](index.md) — 데이터 문서 입구\n'
    source = base / 'wiki/quality/invariants.md'
    rows = catalog_rows(source.read_text(encoding='utf-8'))
    groups = defaultdict(Counter)
    for inv, kind in rows:
        groups[inv.split('-')[2]][kind] += 1
    counts = Counter(kind for _, kind in rows)
    inv_body = '''[실측: 작업 트리] [불변식 카탈로그](invariants.md)의 정의 표 첫 열만 집계했습니다. 본문에 반복된 ID·과거 요약·코드 주석 수를 불변식 등록 수와 섞지 않습니다.

| 영역 | 등록 수 | automated | review | manual |
|---|---:|---:|---:|---:|
'''
    for group, values in sorted(groups.items()):
        inv_body += f'| {group} | {sum(values.values())} | {values["automated"]} | {values["review"]} | {values["manual"]} |\n'
    inv_body += f'| 합계 | {len(rows)} | {counts["automated"]} | {counts["review"]} | {counts["manual"]} |\n'
    inv_body += '''
등록·automated 표시는 이번 실행의 시험 통과 수가 아닙니다. 사용 종료된 SEC-008·EVAL-001은 현재 정의 표에서 제외하고 번호를 재사용하지 않습니다. VER 항목은 합성 철도 패스 정책으로 검증합니다. 전체 항목이 현재 여행 제품에서 유효하고 통과했다고 해석하지 않습니다.

중복 ID가 있으면 생성기가 실패합니다. 실제 함수 연결은 wiki 검사기로, 동작은 해당 시험 실행으로 별도 확인합니다.

## 관계

- [불변식 카탈로그](invariants.md) — 개별 규칙과 시험 연결의 정본
- [시험 지도](test-map.md) — 동작 검증 위치
'''
    return {base/'wiki/data/migration-inventory.generated.md': generated('SQL 파일 목록', '실행기의 입력 파일과 보류 파일을 자동 집계한다', sql_body), base/'wiki/quality/invariant-summary.generated.md': generated('불변식 등록 집계', '카탈로그의 정의 행만 집계하며 실행 통과율과 구분한다', inv_body), **render_state_inventory()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    changed = []
    for path, text in render().items():
        if path.exists() and path.read_text(encoding='utf-8') == text:
            continue
        changed.append(path.relative_to(ROOT).as_posix())
        if args.check:
            continue
        if path.exists():
            backup = path.parent/'_backup'/(datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')+'_generated')/path.name
            backup.parent.mkdir(parents=True)
            shutil.copy2(path, backup)
        path.write_text(text, encoding='utf-8')
    print(('갱신 필요: ' if args.check else '생성: ') + ', '.join(changed) if changed else '생성물 일치')
    return int(args.check and bool(changed))


if __name__ == '__main__':
    raise SystemExit(main())
