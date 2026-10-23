"""로컬 원본 자료를 줄이거나 덮는 셸 명령의 실행 전 검사. 파일을 변경하지 않는다."""
from __future__ import annotations

import json
import re
import sys

REASON = "로컬 자료 보호: 삭제·원본 동기화 명령은 차단합니다. 원본을 유지하고 별도 사본에서 작업하세요."

# [2026-10-19 사용자 지시] 시험이 끝난 도커 컨테이너·이미지·빌드 캐시는 세션이 직접 지운다.
# 아래 도커 명령의 `rm` 은 파일 삭제가 아니라 도커 객체 삭제라서 검사 전에 빼 둔다.
# 이름 붙은 볼륨·전체 정리는 운영 DB 를 지울 수 있어 계속 막는다.
DOCKER_DENIED = (
    r"\bdocker(?:\.exe)?\s+volume\s+(?:rm|prune)\b",
    r"\bdocker(?:\.exe)?\s+system\s+prune\b",
    r"\bdocker(?:\.exe)?\s+compose\b[^\r\n;&|]*\bdown\b[^\r\n;&|]*(?:\s-v\b|--volumes\b)",
)
DOCKER_RUN_AUTO_REMOVE = re.compile(r"(\bdocker(?:\.exe)?\s+(?:container\s+)?(?:run|create)\b[^\r\n;&|]*?)--rm\b", re.IGNORECASE)
DOCKER_OBJECT_DELETE = re.compile(
    r"\bdocker(?:\.exe)?\s+(?:(?:container\s+)?rm|rmi|image\s+(?:rm|prune)|builder\s+prune|buildx\s+prune)\b", re.IGNORECASE
)


def _without_docker_object_deletes(command: str) -> str:
    previous = None
    while previous != command:
        previous = command
        command = DOCKER_RUN_AUTO_REMOVE.sub(r"\1--auto-remove", command)
    return DOCKER_OBJECT_DELETE.sub("docker delete-test-object", command)


def blocked(command: str) -> bool:
    if any(re.search(pattern, command, re.IGNORECASE) for pattern in DOCKER_DENIED):
        return True
    command = _without_docker_object_deletes(command)
    # Shell composition and a nested shell still contain these command words.
    patterns = (
        r"\bgit(?:\.exe)?\b[^\r\n;&|]*\b(?:clean|reset|restore|checkout|switch|pull|sparse-checkout|read-tree|update-index|prune)\b",
        r"\bgit(?:\.exe)?\b[^\r\n;&|]*\bworktree\s+(?:remove|prune|move)\b",
        r"\bgit(?:\.exe)?\b[^\r\n;&|]*\brm\b",
        r"\b(?:remove-item|clear-content|rmdir|rd|del|erase|rm|unlink|move-item)\b",
        r"\brobocopy(?:\.exe)?\b[^\r\n]*\s/(?:mir|purge|mov|move)\b",
        r"\brsync\b[^\r\n]*--delete\b",
        r"\b(?:shutil\s*\.\s*rmtree|os\s*\.\s*(?:remove|unlink|rmdir)|\.unlink\s*\(|\.rmdir\s*\()",
    )
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in patterns)


def hook(payload: dict) -> dict | None:
    command = payload.get("tool_input", {}).get("command", "")
    if isinstance(command, str) and blocked(command):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": REASON}}
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf8")
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        denied = ["git clean -fdx", "git -C elsewhere reset --hard HEAD", "git sparse-checkout set app", "git restore .", "git checkout -- .", "git update-index --skip-worktree file", "git worktree remove --force path", "powershell -Command Remove-Item -Recurse datasets", "robocopy a b /MIR", "rsync --delete a b", "python -c \"shutil.rmtree('datasets')\"", "rm -rf .tmp",
                  "docker volume rm tripilot_tripilot_pg", "docker volume prune -f", "docker system prune -af --volumes", "docker compose -p t down -v", "docker rm test-db && rm -rf datasets", "docker run --rm img sh -c 'rm -rf /data'"]
        allowed = ["git status --short", "git fetch team", "git diff --stat", "python tools/safe_git.py status", "python -m pytest tests/unit", "git log --oneline",
                   "docker run --rm --name t-20261019 img pytest", "ssh x600 \"wsl -e docker rm -v t-db-20261019\"", "docker container rm t-1", "docker rmi tripilot-api:t-20261019-v1", "docker image rm a:b", "docker image prune -f", "docker builder prune -f --keep-storage 20GB", "docker compose -p t down"]
        for command in denied:
            assert blocked(command), command
        for command in allowed:
            assert not blocked(command), command
        assert hook({"tool_input": {"command": denied[0]}})["hookSpecificOutput"]["permissionDecision"] == "deny"
        print(f"삭제 없는 명령 판정 시험 {len(denied)+len(allowed)+1}/{len(denied)+len(allowed)+1}")
        return 0
    try:
        result = hook(json.load(sys.stdin))
    except (ValueError, TypeError, AttributeError):
        result = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "로컬 자료 보호: 실행 전 검사 입력을 읽지 못해 차단했습니다."}}
    if result:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
