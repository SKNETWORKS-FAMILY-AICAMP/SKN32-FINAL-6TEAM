"""백업 때문에 검사 결과가 바뀌거나 현재 깨진 링크를 숨기는 회귀를 막는다."""
import importlib.util
import io
import json
from pathlib import Path
from contextlib import redirect_stdout

import pytest


def load(name):
    path = Path(__file__).resolve().parents[1] / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_and_generated_are_checked_but_backups_staging_records_are_separate(tmp_path):
    check = load('check_wiki')
    for name in ['index.md', 'current.md', 'state.generated.md', '_backup/a/bad.md', '_migration/old.md', 'records/report.md', 'records/_backup/a/bad.md']:
        p = tmp_path/'wiki'/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('bad metadata', encoding='utf-8')
    docs, records, counts = check.collect_docs([str(tmp_path/'wiki')])
    assert {Path(p).name for p in docs} == {'index.md', 'current.md', 'state.generated.md'}
    assert [Path(p).name for p in records] == ['report.md']
    assert counts['generated_documents'] == 1
    assert counts['excluded_backup_directories'] == 2


def test_missing_current_target_fails_even_when_parent_exists_and_anchor_is_present(tmp_path, monkeypatch):
    check = load('check_wiki')
    monkeypatch.chdir(tmp_path)
    (tmp_path/'wiki').mkdir()
    (tmp_path/'wiki/index.md').write_text('---\ntype: guide\ndomain: neutral\n---\n[x](missing.md#part)\n', encoding='utf-8')
    monkeypatch.setattr(check, 'ROOTS', ['wiki'])
    monkeypatch.setattr(check.sys, 'argv', ['check_wiki.py', '--json-output', 'result.json'])
    with redirect_stdout(io.StringIO()):
        result = check.main()
    data = json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    assert result == 1
    assert data['problems']['깨진 링크 (대상 파일 없음)'] == ['wiki/index.md -> missing.md']


def test_catalog_counts_definition_rows_not_repeated_prose_and_rejects_duplicates():
    build = load('build_wiki_catalogs')
    row = '| `INV-CS-ARCH-007` | rule | automated | `test.py` |\n'
    assert build.catalog_rows('Mention `INV-CS-ARCH-007`\n' + row) == [('INV-CS-ARCH-007', 'automated')]
    with pytest.raises(ValueError, match='중복'):
        build.catalog_rows(row + row)


@pytest.mark.parametrize('fields', [
    {'implementation_status': 'done'},
    {'validation_status': 'implemented'},
    {'verified_at': '2026-10-12'},
    {'verified_at': '2026-10-12T04:00:00'},
    {'decision_status': ''},
])
def test_invalid_state_fields_are_rejected(fields):
    check = load('check_wiki')
    errors, _ = check.state_fields(fields)
    assert errors


def test_review_and_decision_are_independent_and_legacy_values_need_review():
    check = load('check_wiki')
    assert check.state_fields({'status': 'draft', 'decision_status': 'accepted',
        'implementation_status': 'unverified', 'validation_status': 'unverified'}) == ([], [])
    errors, notes = check.state_fields({'implementation_status': 'implemented-local'})
    assert not errors and notes
    assert check.state_fields({'validation_status': 'verified'})[1]
    assert check.state_fields({'validation_status': 'verified',
        'verified_at': '2026-10-12T04:00:00+09:00'}) == ([], [])


def test_backup_only_code_markers_do_not_add_current_invariants(tmp_path):
    check = load('check_wiki')
    for name, ident in [('current.py', 'INV-CS-ARCH-007'),
                        ('_backup/old.py', 'INV-CS-OLD-001'),
                        ('.cache/old.py', 'INV-CS-OLD-002')]:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# invariant: '+ident, encoding='utf-8')
    assert check.collect_code_ids(str(tmp_path)) == {'INV-CS-ARCH-007'}


def test_inventory_covers_current_contracts_without_promoting_accepted_decisions(tmp_path):
    build = load('build_wiki_catalogs')
    cases = {
        'wiki/decisions/current.md': 'decision',
        'wiki/runtime/input.md': 'contract',
        'wiki/records/old.md': 'decision',
        'wiki/_backup/old.md': 'decision',
        'final_project_sample/wiki/reference.md': 'contract',
    }
    for name, kind in cases.items():
        p = tmp_path/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'---\ntype: {kind}\nstatus: draft\ndecision_status: accepted\n---\n', encoding='utf-8')
    rows = build.state_inventory(tmp_path)['documents']
    assert {r['path'] for r in rows} == {'wiki/decisions/current.md', 'wiki/runtime/input.md'}
    assert all(r['implementation_status'] == r['validation_status'] == r['deployment_status'] == 'unverified' for r in rows)
    assert all('implementation_status' in r['missing_fields'] for r in rows)


def test_invalid_state_in_current_page_fails_and_missing_front_matter_is_unmarked(tmp_path, monkeypatch):
    check = load('check_wiki')
    monkeypatch.chdir(tmp_path)
    (tmp_path/'wiki').mkdir()
    (tmp_path/'wiki/index.md').write_text('---\ntype: guide\nimplementation_status: done\n---\n', encoding='utf-8')
    (tmp_path/'wiki/no-metadata.md').write_text('# 본문', encoding='utf-8')
    monkeypatch.setattr(check, 'ROOTS', ['wiki'])
    monkeypatch.setattr(check.sys, 'argv', ['check_wiki.py', '--json-output', 'result.json'])
    with redirect_stdout(io.StringIO()):
        result = check.main()
    data = json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    assert result == 1
    assert data['problems']['상태 필드 형식 위반'] == ['wiki/index.md  (implementation_status: done)']
    assert set(data['unmarked_domain']) == {'wiki/index.md', 'wiki/no-metadata.md'}
