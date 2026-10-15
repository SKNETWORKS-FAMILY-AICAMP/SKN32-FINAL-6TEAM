import datetime
import json
import pathlib
import shutil
import subprocess

folder = pathlib.Path(__file__).resolve().parent
root = folder.parents[5]
base = 'final_project_cs/frontend/apps/web/'
paths = {
    'menu': base + 'src/components/layout/settings-menu.tsx',
    'frame': base + 'src/components/layout/journey-shell.tsx',
    'settings': base + 'src/lib/settings.ts',
    'tests': base + 'tests/live/menu.spec.ts',
    'records': base + 'DEVELOPMENT.md',
}
sources = {}
for key, path in paths.items():
    for side in ['own', 'team']:
        args = ['git', 'diff', '--no-ext-diff', '--no-color', 'bc750713', '--', path] if side == 'own' else ['git', 'diff', '--no-ext-diff', '--no-color', '8fd211fb', 'team/role-eval-ui', '--', path]
        result = subprocess.run(args, cwd=root, capture_output=True, check=True)
        sources[key + '-' + side] = result.stdout.decode('utf-8')

page = folder / 'index.html'
backup = folder / '_backup' / (datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_원문추가전')
backup.mkdir(parents=True)
shutil.copy2(page, backup / page.name)
source = page.read_text(encoding='utf-8')
source = source.replace("'項路 지킴이는", "'항로 지킴이는").replace(";note.textContent=note.textContent.replace('項路','항로')", '')
payload = json.dumps(sources, ensure_ascii=False).replace('<', '\\u003c')
embedded = '<script>const sourceData=' + payload + ';document.querySelectorAll("[data-source]").forEach(el=>el.textContent=sourceData[el.dataset.source]);</script>'
assert '<!--SOURCE_DATA-->' in source
page.write_text(source.replace('<!--SOURCE_DATA-->', embedded), encoding='utf-8')
print('Five pairs of actual Git diffs embedded. Original HTML backed up before replacement.')

