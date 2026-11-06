"""Added-line preservation check for merge 43a3ced29: every '+' line of each side's diff must exist in the merged file."""
import subprocess, collections, json, sys

WT = r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt'
MERGE = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'


def git(*a):
    return subprocess.run([r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/mingit/cmd/git.exe', '-C', WT, *a], capture_output=True, check=True).stdout


def added(base, tip):
    out = collections.defaultdict(list)
    cur = None
    for line in git('diff', '--no-color', '--no-ext-diff', '-U0', base, tip, '--', '.', ':!*.docx', ':!*.png', ':!*.jpg', ':!*.avif').decode('utf-8', 'replace').splitlines():
        if line.startswith('+++ '):
            cur = line[6:] if line.startswith('+++ b/') else None
        elif line.startswith('+') and cur and line[1:].strip():
            out[cur].append(line[1:])
    return out


report = {}
for name, (base, tip) in {'ours': ('a465c6022', '60af7a7d2'), 'remote': ('a465c6022', '1cf4542a1')}.items():
    miss, total = [], 0
    for path, lines in added(base, tip).items():
        try:
            text = git('show', f'{MERGE}:{path}').decode('utf-8', 'replace')
        except subprocess.CalledProcessError:
            miss.append((path, '<file missing>'))
            continue
        merged = set(text.splitlines())
        for l in lines:
            total += 1
            if l not in merged:
                miss.append((path, l[:160]))
    report[name] = {'added_lines': total, 'missing': len(miss), 'missing_sample': miss[:40]}
print(json.dumps(report, ensure_ascii=False, indent=1))
