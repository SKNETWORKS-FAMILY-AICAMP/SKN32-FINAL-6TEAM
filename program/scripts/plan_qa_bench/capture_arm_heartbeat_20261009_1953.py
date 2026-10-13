"""Read ARM runtime and archive newly completed jobs; connection comes from CLI only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ssh', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    (out / '.gitignore').write_text('*\n', encoding='utf-8')
    prefix = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', args.ssh]
    observer = Path(__file__).parent / 'server/observe_arm_serving.py'
    raw = subprocess.check_output(prefix + ['python3 -'], input=observer.read_bytes(), timeout=55)
    obs = json.loads(raw)
    (out / 'observation.json').write_bytes(raw)
    completed = [jid for jid, row in obs['state']['jobs'].items() if row['status'] == 'completed']
    collected = []
    for jid in completed:
        if jid in ('e4bt_q4_d3', 'e4bt_q8_d3', 'e4bt_q4_grouped60_cache_ABBA_1', 'e4bt_q4_grouped60_cache_ABBA_2'):
            continue  # Previous verified archives already own these completed runs.
        if not re.fullmatch(r'[A-Za-z0-9_-]+', jid):
            raise ValueError('Unsafe job id')
        code = ("from pathlib import Path; import json,hashlib; p=Path.home()/'bench/continuous-travel-20261008'; "
                "s=json.loads((p/'state.json').read_text()); jid=" + repr(jid) + "; assert s['jobs'][jid]['status']=='completed'; "
                "print(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/jid).iterdir() if f.is_file()}))")
        hashes = json.loads(subprocess.check_output(prefix + ['python3 -'], input=code.encode(), timeout=40))
        archive = out / (jid + '.tar.gz')
        with archive.open('xb') as stream:
            subprocess.run(prefix + ['tar -czf - -C "$HOME/bench/continuous-travel-20261008" ' + jid],
                           stdout=stream, check=True, timeout=55)
        target = out / 'completed'
        target.mkdir(exist_ok=True)
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                if member.issym() or member.islnk() or not (target / member.name).resolve().is_relative_to(target.resolve()):
                    raise ValueError('Unsafe archive member')
            bundle.extractall(target, filter='data')
        job = target / jid
        checks = {name: hashlib.sha256((job / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items()}
        assert all(checks.values())
        answers = [json.loads(line) for line in (job / 'answers.jsonl').read_text(encoding='utf-8').splitlines()]
        collected.append(dict(id=jid, saved=len(answers), unique_ids=len({r['i'] for r in answers}),
                              hashes=hashes, hash_checks=checks, summary=json.loads((job / 'summary.json').read_text())))
    result = dict(observed_at=obs['observed_at'], service=obs['service'], active=obs['active'],
                  resource_summary=obs['resource_summary'], free_bytes=obs['free_bytes'],
                  states={jid: row['status'] for jid, row in obs['state']['jobs'].items()},
                  registered=len(obs['manifest']['jobs']), collected=collected)
    (out / 'capture.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('observed_at', 'service', 'active', 'resource_summary', 'free_bytes', 'states', 'registered')}, ensure_ascii=False))
    print(json.dumps({'collected': [{key: job[key] for key in ('id', 'saved', 'unique_ids')} for job in collected]}))


if __name__ == '__main__':
    main()
