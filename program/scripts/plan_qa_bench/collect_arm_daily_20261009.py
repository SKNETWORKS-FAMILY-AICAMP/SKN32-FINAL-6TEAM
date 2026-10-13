"""Archive one completed ARM job; SSH target comes only from the caller."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", required=True)
    args = parser.parse_args()
    root = Path("program/scripts/plan_qa_bench/results/daily_20261009_arm_v1")
    archive = root / "e4bt_q8_d3_completed.tar.gz"
    if archive.exists():
        raise FileExistsError(archive)
    prefix = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.ssh]
    remote_code = "from pathlib import Path; import json,hashlib; p=Path.home()/'bench/continuous-travel-20261008'; s=json.loads((p/'state.json').read_text()); assert s['jobs']['e4bt_q8_d3']['status']=='completed'; print(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'e4bt_q8_d3').iterdir() if f.is_file()}))"
    hashes = json.loads(subprocess.check_output(prefix + ["python3 -"], input=remote_code.encode(), timeout=40))
    with archive.open("xb") as stream:
        subprocess.run(prefix + ['tar -czf - -C "$HOME/bench/continuous-travel-20261008" e4bt_q8_d3'], stdout=stream, check=True, timeout=60)
    target = root / "completed"
    target.mkdir()
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            if member.issym() or member.islnk() or not (target / member.name).resolve().is_relative_to(target.resolve()):
                raise ValueError("Unsafe archive member")
        bundle.extractall(target, filter="data")
    job = target / "e4bt_q8_d3"
    checks = {name: sha(job / name) == expected for name, expected in hashes.items()}
    assert all(checks.values())
    answers = [json.loads(line) for line in (job / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(answers) == 360 and len({r['i'] for r in answers}) == 360
    summary = json.loads((job / "summary.json").read_text())
    verification = dict(job_id="e4bt_q8_d3", saved=len(answers), expected=360, unique_ids=360,
                        files_verified=sum(checks.values()), files_expected=len(checks), checks=checks,
                        remote_file_sha256=hashes, archive_sha256=sha(archive), summary=summary,
                        training="existing merged E4B; exact oos recipe not matched", product_adoption=False,
                        speed_comparison="different quantization and sequential run; no engine superiority claim")
    (root / "archive_verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
