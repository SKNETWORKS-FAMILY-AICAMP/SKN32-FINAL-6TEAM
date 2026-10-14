"""배포가 남기는 도커 이미지를 개수·기한 기준으로 지우고, 달마다 하나는 복원용으로 남긴다.

표준 라이브러리만 쓴다(서버 호스트의 python3 로 바로 돈다). 기본은 계획만 출력하고 `--apply` 가 있어야 지운다.

지우는 대상은 **이름과 태그 모양이 정해진 것뿐**이다.
  앱 이미지   : `--app-repo` 로 준 저장소의 `<커밋 해시>` 모양 태그(7~40자리 16진수)
  복구 이미지 : `--recovery-repo` 의 `<32자리 16진수>-<서비스>` 태그(migration_safe_deploy.py 가 붙인다)
`local`·`keep-*`·손으로 붙인 이름·다른 저장소는 건드리지 않는다. 실행 중 컨테이너가 쓰는 이미지와 현재 배포 태그도 지키지 않고 지나가지 않는다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import re
import shutil
import subprocess
from pathlib import Path

APP_TAG = re.compile(r"^[0-9a-f]{7,40}$")
KEEP_TAG = re.compile(r"^keep-(\d{4})-(\d{2})$")
RECOVERY_TAG = re.compile(r"^([0-9a-f]{32})-([a-z0-9-]+)$")
DEPLOYED = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) 반영 완료 ([0-9a-f]{7,40})\b")
SAFETY_DIR = re.compile(r"^migration-safety-([0-9a-f]+)-(\d+)$")


class RetentionError(RuntimeError):
    pass


class Docker:
    def run(self, args, timeout=120):
        try:
            result = subprocess.run(["docker", *args], text=True, capture_output=True,
                                    timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RetentionError(f"docker {args[0]} 시간 초과({timeout}초)") from exc
        if result.returncode:
            raise RetentionError(f"docker {args[0]} 실패(코드 {result.returncode})")
        return result.stdout


def parse_time(text):
    """`docker images` 의 CreatedAt("2026-10-14 03:12:45 +0900 KST")이나 inspect 의 ISO 시각을 UTC 로."""
    # 두 가지 모양을 모두 읽는다: `2026-10-14 03:12:45 +0900 KST`(images)와
    # `2026-10-14 03:12:45.123456789 +0900 KST`(inspect 의 Go 기본 출력), ISO `2026-10-14T03:12:45.1+09:00`.
    match = re.match(r"^\s*(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)(?:\.\d+)?\s*(Z|[+-]\d\d:?\d\d)", text)
    if not match:
        raise RetentionError("시각 해석 실패")
    zone = match.group(3)
    zone = "+00:00" if zone == "Z" else zone if ":" in zone else zone[:3] + ":" + zone[3:]
    return datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}{zone}").astimezone(timezone.utc)


def list_images(docker):
    rows = []
    out = docker.run(["images", "--no-trunc", "--format",
                      "{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}"])
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4 or "<none>" in parts[:2]:
            continue
        rows.append({"repo": parts[0], "tag": parts[1], "id": parts[2], "created": parse_time(parts[3])})
    return rows


def used_image_ids(docker):
    ids = docker.run(["ps", "-a", "-q"]).split()
    if not ids:
        return set()
    return set(docker.run(["inspect", "--format", "{{.Image}}", *ids]).split())


def read_deploy_log(path):
    """서버 deploy.log 의 「반영 완료 <해시>」 줄 → {해시: 반영 시각(UTC로 간주)}. 없으면 빈 표."""
    good = {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return good
    for line in text.splitlines():
        m = DEPLOYED.match(line)
        if m:
            y, mo, d, h, mi, s = (int(x) for x in m.groups()[:6])
            # deploy.log 의 시각은 서버 지역 시각이다(`date '+%F %T'`) — 시간대 없는 값은 지역 시각으로 읽어 UTC 로 바꾼다.
            good[m.group(7)] = datetime(y, mo, d, h, mi, s).astimezone(timezone.utc)
    return good


def lookup(good, tag):
    for key, when in good.items():
        if key.startswith(tag) or tag.startswith(key):
            return when
    return None


def month_key(when):
    when = when.astimezone()       # 달이 바뀌는 시각은 서버 지역 시각 기준(KST 서버에서 11월 1일 새벽이 10월로 읽히지 않게)
    return f"{when.year:04d}-{when.month:02d}"


def recent_months(now, count):
    now = now.astimezone()
    months, year, month = [], now.year, now.month
    for _ in range(max(count, 0)):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months


def plan_apps(images, app_repos, now, keep_recent, keep_months, protected_tags, used_ids, good):
    """앱 이미지 계획. 같은 커밋 태그는 저장소가 달라도 한 묶음으로 보고 함께 남기거나 함께 지운다."""
    by_tag = {}
    for img in images:
        if img["repo"] in app_repos and APP_TAG.match(img["tag"]):
            by_tag.setdefault(img["tag"], []).append(img)
    when = {tag: (lookup(good, tag) or max(i["created"] for i in group)) for tag, group in by_tag.items()}
    ordered = sorted(by_tag, key=lambda t: when[t], reverse=True)
    keep = {}
    for tag in ordered[:keep_recent]:
        keep[tag] = "최근"
    for tag in protected_tags:
        if tag in by_tag:
            keep.setdefault(tag, "현재 배포")
    # 달마다 하나 — 성공한 반영 기록이 있으면 그 중에서만, 기록이 전혀 없으면 만들어진 시각으로 고른다.
    eligible = [t for t in ordered if (lookup(good, t) is not None or not good)]
    aliases = {}
    for month in recent_months(now, keep_months):
        pick = next((t for t in eligible if month_key(when[t]) == month), None)
        if pick:
            keep.setdefault(pick, "달별 보존 " + month)
            aliases[month] = pick
    # 실행 중(정지된 컨테이너 포함)인 이미지는 「그 이미지 자체」만 지키고 같은 커밋 이름표의 다른 저장소 이미지까지 지키지 않는다.
    # 웹처럼 바뀌지 않아 이미지 ID 를 여러 커밋이 공유하면, 묶음째 지키는 순간 api 이미지가 영영 안 지워진다.
    kept_ids = {i["id"] for tag in keep for i in by_tag[tag]}
    delete, in_use = [], []
    for tag in ordered:
        if tag in keep:
            continue
        for i in by_tag[tag]:
            if i["id"] in used_ids and i["id"] not in kept_ids:
                in_use.append((i["repo"], i["tag"]))      # 이 이름표가 마지막 참조다 — 쓰는 동안은 둔다
            else:
                delete.append((i["repo"], i["tag"]))
    # 달별 별칭(`keep-YYYY-MM`): 창 안의 달은 고른 태그로 옮겨 붙이고, 창 밖의 달은 뗀다.
    retag, drop_alias = [], []
    existing = {(i["repo"], i["tag"]): i for i in images if i["repo"] in app_repos and KEEP_TAG.match(i["tag"])}
    for month, tag in aliases.items():
        for img in by_tag[tag]:
            current = existing.get((img["repo"], "keep-" + month))
            if current is None or current["id"] != img["id"]:
                retag.append((img["repo"], tag, "keep-" + month))
    for (repo, alias), _ in existing.items():
        if alias[len("keep-"):] not in aliases:
            drop_alias.append((repo, alias))
    return {"keep": keep, "delete": delete, "in_use": in_use, "retag": retag, "drop_alias": drop_alias, "tags": by_tag}


def safety_dirs(state_dir):
    dirs = {}
    for path in Path(state_dir).glob("migration-safety-*"):
        m = SAFETY_DIR.match(path.name)
        if m and path.is_dir():
            tokens = set()
            try:
                baseline = json.loads((path / "baseline.json").read_text(encoding="utf-8"))
                for record in baseline.values():
                    match = RECOVERY_TAG.match(str(record.get("recovery_tag", "")).split(":", 1)[-1])
                    if match:
                        tokens.add(match.group(1))
            except (OSError, ValueError, AttributeError):
                pass
            dirs[path] = {"epoch": datetime.fromtimestamp(int(m.group(2)), timezone.utc), "tokens": tokens}
    return dirs


def plan_recovery(docker, images, recovery_repo, state_dir, now, keep_sets, min_age):
    """복구 이미지 계획. 세트(= 한 번의 배포 시도가 붙인 서비스 셋) 단위로 최신 `keep_sets` 개만 남긴다."""
    sets = {}
    for img in images:
        if img["repo"] != recovery_repo:
            continue
        m = RECOVERY_TAG.match(img["tag"])
        if m:
            sets.setdefault(m.group(1), []).append(img)
    dirs = safety_dirs(state_dir)
    token_time = {}
    for info in dirs.values():
        for token in info["tokens"]:
            token_time[token] = info["epoch"]
    unknown = 0
    for token, group in sets.items():
        if token in token_time:
            continue
        # 상태 폴더가 없는 세트: 이미지에 마지막으로 이름표를 붙인 시각은 이 이름표 시각 이상이므로,
        # 그것이 기한보다 오래됐으면 이 이름표는 확실히 기한이 지났다(젊게 잘못 읽는 쪽이 아니라 늙게 읽는 쪽으로 안전).
        stamp = None
        try:
            stamp = parse_time(docker.run(["image", "inspect", "--format", "{{.Metadata.LastTagTime}}", group[0]["id"]]))
        except RetentionError:
            pass
        if stamp and stamp.year > 1:
            token_time[token] = stamp
        else:
            token_time[token] = now      # 나이를 모르면 지우지 않는 쪽으로 읽는다 — 대신 아래에서 드러낸다
            unknown += 1
    ordered = sorted(sets, key=lambda t: token_time[t], reverse=True)
    keep = set(ordered[:keep_sets]) | {t for t in ordered if now - token_time[t] < min_age}
    delete = [(i["repo"], i["tag"]) for t in ordered if t not in keep for i in sets[t]]
    drop_dirs = []
    for path, info in dirs.items():
        age = now - info["epoch"]
        if info["tokens"]:
            if info["tokens"].isdisjoint(keep) and age >= min_age:
                drop_dirs.append(path)
        elif age >= max(min_age, timedelta(hours=24)):
            drop_dirs.append(path)   # 스냅샷이 끝나지 못한 폴더(이미지 이름표 없음)
    return {"keep_sets": keep, "delete": delete, "drop_dirs": drop_dirs, "sets": sets, "unknown_age": unknown}


def apply_plan(docker, plan, say):
    removed = failed = 0
    for repo, tag, alias in plan.get("retag", []):
        docker.run(["tag", f"{repo}:{tag}", f"{repo}:{alias}"])
        say(f"달별 이름표 {repo}:{alias} <- {tag}")
    for repo, tag in [*plan["delete"], *plan.get("drop_alias", [])]:
        try:
            docker.run(["rmi", f"{repo}:{tag}"])
            removed += 1
        except RetentionError:
            failed += 1   # 사용 중이거나 이미 없다 — 다음 회차에 다시 본다
    for path in plan.get("drop_dirs", []):
        shutil.rmtree(path, ignore_errors=True)
    return removed, failed


def prune_release_dirs(releases, keep_tags, protected, apply, say):
    """오라클처럼 `releases/<커밋>` 에 소스를 풀어 두는 곳: 이미지가 모두 사라진 판의 소스 폴더를 지운다."""
    removed = []
    base = Path(releases)
    if not base.is_dir():
        return removed
    for path in sorted(base.iterdir()):
        if not path.is_dir():
            continue
        if any(path.name.startswith(t) for t in keep_tags):
            continue
        if any(path.name.startswith(p) for p in protected if p):
            continue
        removed.append(path.name)
        say(("지움 " if apply else "지울 예정 ") + "releases/" + path.name[:12])
        if apply:
            shutil.rmtree(path, ignore_errors=True)
    return removed


def run_retention(docker, *, app_repos, recovery_repo=None, state_dir=None, protected_tags=(), good=None,
                  now=None, keep_recent=3, keep_months=6, recovery_keep=2, min_age_hours=2, apply=False,
                  builder_keep_gb=0, say=print):
    now = now or datetime.now(timezone.utc)
    images = list_images(docker)
    used = used_image_ids(docker)
    apps = plan_apps(images, set(app_repos), now, keep_recent, keep_months, set(protected_tags), used, good or {})
    say(f"앱 이미지 묶음 {len(apps['tags'])}개 중 남김 {len(apps['keep'])} · 지움 {len(apps['delete'])}개 이미지 이름표"
        f" · 실행 중이라 둠 {len(apps['in_use'])}개")
    for tag, why in sorted(apps["keep"].items()):
        say(f"  남김 {tag} ({why})")
    for repo, tag in apps["in_use"]:
        say(f"  둠 {repo}:{tag} (실행 중인 컨테이너가 쓰는 이미지)")
    plan = {"retag": apps["retag"], "delete": list(apps["delete"]), "drop_alias": apps["drop_alias"], "drop_dirs": []}
    if recovery_repo and state_dir:
        rec = plan_recovery(docker, images, recovery_repo, state_dir, now, recovery_keep, timedelta(hours=min_age_hours))
        say(f"복구 이미지 세트 {len(rec['sets'])}개 중 남김 {len(rec['keep_sets'])} · 지움 {len(rec['delete'])}개 이름표 · "
            f"상태 폴더 {len(rec['drop_dirs'])}개")
        if rec["unknown_age"]:
            say(f"  주의: 나이를 못 읽은 복구 세트 {rec['unknown_age']}개는 안전하게 남겼다")
        plan["delete"] += rec["delete"]
        plan["drop_dirs"] += rec["drop_dirs"]
    if not apply:
        say(f"(계획만 — 지우지 않았다) 이름표 {len(plan['delete']) + len(plan['drop_alias'])}개, 상태 폴더 {len(plan['drop_dirs'])}개")
        return {"plan": plan, "apps": apps, "removed": 0, "failed": 0}
    removed, failed = apply_plan(docker, plan, say)
    try:
        docker.run(["image", "prune", "-f", "--filter", "until=24h"])
    except RetentionError:
        pass
    if builder_keep_gb > 0:
        # 빌드 캐시: 도커의 자동 정리 설정(gc)만으로는 상한이 지켜지지 않았다(77GB). 가장 오래 안 쓴 것부터 상한까지만 남긴다.
        try:
            docker.run(["builder", "prune", "-f", "--keep-storage", f"{builder_keep_gb}GB"], timeout=900)
            say(f"빌드 캐시를 {builder_keep_gb}GB 상한으로 정리했다")
        except RetentionError:
            say("경고: 빌드 캐시 정리 실패 — 이미지 정리는 끝났다")
    say(f"이름표 {removed}개 지움, 실패 {failed}개")
    return {"plan": plan, "apps": apps, "removed": removed, "failed": failed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, help="x600 서버 배포 폴더(state/ 를 읽는다)")
    parser.add_argument("--app-repo", action="append", default=[])
    parser.add_argument("--recovery-repo")
    parser.add_argument("--keep-recent", type=int, default=3)
    parser.add_argument("--keep-months", type=int, default=6)
    parser.add_argument("--recovery-keep", type=int, default=2)
    parser.add_argument("--min-age-hours", type=int, default=2)
    parser.add_argument("--builder-keep-gb", type=int, default=0, help="빌드 캐시 상한(GB). 0 이면 건드리지 않는다")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.app_repo:
        parser.error("--app-repo 가 하나는 필요하다")
    state, protected, good = None, [], {}
    if args.base:
        state = args.base / "state"
        for name in ("current_tag", "admin_tag"):
            try:
                protected.append((state / name).read_text(encoding="utf-8").strip())
            except OSError:
                pass
        good = read_deploy_log(args.base / "deploy.log")
    try:
        run_retention(Docker(), app_repos=args.app_repo, recovery_repo=args.recovery_repo, state_dir=state,
                      protected_tags=[p for p in protected if p], good=good, keep_recent=args.keep_recent,
                      keep_months=args.keep_months, recovery_keep=args.recovery_keep,
                      min_age_hours=args.min_age_hours, apply=args.apply,
                      builder_keep_gb=args.builder_keep_gb)
    except RetentionError as exc:
        print(f"이미지 정리 실패: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
