"""Resolve git conflict hunks one by one with an explicit per-hunk choice (bytes-preserving).

usage: python resolve.py <file> <idx>:<ours|theirs|both|theirs_then_ours> ...
Every hunk must be given a mode; otherwise the file is left untouched.
"""
import sys

path = sys.argv[1]
modes = {int(a.split(':')[0]): a.split(':')[1] for a in sys.argv[2:]}
lines = open(path, 'rb').read().splitlines(keepends=True)
out, i, h = [], 0, 0
while i < len(lines):
    line = lines[i]
    if line.startswith(b'<<<<<<< '):
        ours, theirs = [], []
        i += 1
        while not lines[i].startswith(b'======='):
            ours.append(lines[i]); i += 1
        i += 1
        while not lines[i].startswith(b'>>>>>>> '):
            theirs.append(lines[i]); i += 1
        i += 1
        mode = modes[h]; h += 1
        out += {'ours': ours, 'theirs': theirs, 'both': ours + theirs, 'theirs_then_ours': theirs + ours}[mode]
        continue
    out.append(line); i += 1
if h != len(modes):
    sys.exit(f'hunk count {h} != modes {len(modes)}; file untouched')
open(path, 'wb').write(b''.join(out))
print(path, 'hunks', h)
