# -*- coding: utf-8 -*-
"""추적되는 파일에 **인프라·접속 정보**가 없다 — 공인 IP · 웹훅 URL · SSH 접속 표기 · 개인키.

☆왜(2026-09-14 사고). 경유 서버의 IP·계정·SSH 별칭과 학원 IP 를 `.env.apikeys.example`
  ·`settings.py` 주석·커밋 메시지에 「설명」처럼 적었다. 공용 저장소에 서버 주소를 광고한
  셈이고, 이미 원격에 올라간 커밋까지 있어 이력 재작성이 필요해졌다. 사람이 조심하는 것으로는
  막히지 않았다 — 그래서 시험이 막는다.

★실제 값은 `.env.apikeys`(git 무시)·`~/.ssh/config`·개인 메모리에만 둔다. 템플릿의 값 칸은
  `<바로 부르는 자리의 외부 IP>` 같은 빈 표시로만 둔다.

★범위: 이 저장소(`final_project_cs`)에서 git 이 추적하는 **텍스트** 파일 전체. 바이너리는
  보지 않는다(이 방법이 놓칠 수 있는 것: 바이너리·이미지 속 문자열, 커밋 메시지·옛 이력).
"""
from __future__ import annotations

import ipaddress
from pathlib import Path
import re
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[2]

IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
WEBHOOK = re.compile(r"discord(?:app)?\.com/api/webhooks/\d+")
SSH_LOGIN = re.compile(r"\b[a-z_][a-z0-9_-]*@\d{1,3}(?:\.\d{1,3}){3}\b")
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

#: ★예외는 **이유와 함께** 적는다. 공인 IP 가 문서에 꼭 필요하면 여기에 넣는다 — 목록이 늘면 신호다.
ALLOWED_IPS: dict[str, str] = {}


def _is_public(text: str) -> bool:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False          # 999.1.1.1 같은 버전 번호 모양
    return address.is_global


#: 버전 번호 앞머리 — `numpy==1.26.4.0`·`version 2.0.0.1` 은 IP 가 아니다.
_VERSION_PREFIX = re.compile(r"(==|>=|<=|~=|!=|\bv|\bversion\s*)$", re.IGNORECASE)


def find_leaks(text: str) -> list[str]:
    """한 파일 내용에서 새면 안 되는 것들."""
    leaks = []
    for match in IPV4.finditer(text):
        ip = match.group(1)
        before = text[max(0, match.start() - 12):match.start()]
        if _is_public(ip) and ip not in ALLOWED_IPS and not _VERSION_PREFIX.search(before):
            leaks.append(f"공인 IP {ip}")
    leaks += [f"웹훅 URL {m.group(0)[:40]}…" for m in WEBHOOK.finditer(text)]
    # ★접속 표기는 **공인 IP** 일 때만 — `postgres@127.0.0.1`(로컬 DB 주소)은 노출이 아니다.
    leaks += [f"SSH 접속 표기 {m.group(0)}" for m in SSH_LOGIN.finditer(text)
              if _is_public(m.group(0).split("@", 1)[1])]
    leaks += ["개인키 머리글" for _ in PRIVATE_KEY.finditer(text)]
    return leaks


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True)
    files = []
    for name in out.stdout.decode("utf-8").split("\0"):
        path = REPO / name
        if not name or not path.is_file():
            continue
        head = path.read_bytes()[:4096]
        if b"\0" in head:     # 바이너리
            continue
        files.append(path)
    return files


# ── 검사기 자체 ──────────────────────────────────────────────────
#: ★표본은 **실행할 때 조립한다.** 글자 그대로 두면 이 파일이 추적되는 순간 아래 저장소
#:  검사가 이 파일을 잡는다(2026-09-14 실제로 걸렸다).
_PUBLIC_IP = ".".join(["8", "8", "8", "8"])
_SAMPLES = [
    f"# 등록한 key 2의 ip : {_PUBLIC_IP}",
    "ssh " + "ubuntu" + "@" + ".".join(["8", "8", "4", "4"]),
    "https://discord.com/api/" + "webhooks/" + "123456/abc",
    "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
]


@pytest.mark.parametrize("sample", _SAMPLES)
def test_the_detector_catches_each_kind(sample):
    assert find_leaks(sample), f"검사기가 못 잡았다: {sample}"


@pytest.mark.parametrize("sample", [
    "socks5://127.0.0.1:1080", "http://10.20.20.1:8100", "192.168.0.10",
    "numpy==1.26.4.0", "version 2.0.0.1", "<바로 부르는 자리의 외부 IP>",
    "postgresql://postgres@127.0.0.1:5433/acop",
])
def test_private_loopback_and_version_like_strings_pass(sample):
    assert find_leaks(sample) == []


# ── 저장소 전체 ──────────────────────────────────────────────────
def test_no_tracked_text_file_leaks_infrastructure():
    files = _tracked_text_files()
    assert files, "추적 파일을 하나도 못 읽었다 — 검사가 헛돈다"
    problems = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        leaks = find_leaks(text)
        if leaks:
            problems[path.relative_to(REPO).as_posix()] = leaks[:3]
    assert not problems, (
        "추적 파일에 인프라·접속 정보가 있다. 실제 값은 `.env.apikeys`·~/.ssh/config 에만 둔다:\n"
        + "\n".join(f"  {name}: {items}" for name, items in sorted(problems.items())))
