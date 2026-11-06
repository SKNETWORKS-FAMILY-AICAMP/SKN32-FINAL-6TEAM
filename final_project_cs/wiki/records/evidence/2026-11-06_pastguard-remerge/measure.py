"""Measure exact bytes/files of this session's deletion candidates (pastguard-final-20261106 subfolders) + already-missing targets."""
import json, os, sys

S = r'C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch'
W = os.path.join(S, 'pastguard-final-20261106')
LONG = '\\\\?\\'


def size(path):
    total = files = 0
    for root, dirs, names in os.walk(LONG + path):
        for n in names:
            try:
                total += os.lstat(os.path.join(root, n)).st_size
                files += 1
            except OSError:
                pass
    return total, files


out = {'session_folder': W, 'children': {}, 'old_targets': {}}
for child in sorted(os.listdir(W)):
    p = os.path.join(W, child)
    if os.path.isdir(p):
        out['children'][child] = size(p)
    else:
        out['children'][child] = (os.path.getsize(p), 1)
for name in ['mgr-merge-20261026-0045', 'past-guard-ext-20261026', 'past-edit-delete-only-20261026', 'past-edit-delete-only-20261026-evidence',
             'llm-date-read-20261026', 'fullrun-20261026', 'integ-mgr-a465c6022-20261026', 'integ-mgr-a465c6022-20261026-tools']:
    p = os.path.join(S, name)
    out['old_targets'][name] = 'exists' if os.path.exists(p) else 'missing'
out['total'] = [sum(v[0] for v in out['children'].values()), sum(v[1] for v in out['children'].values())]
json.dump(out, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out['total']))
