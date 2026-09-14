"""대상 프로젝트의 파일을 **데이터로** 읽는다.

★대상의 검증 모델을 가져오지 않는다 (`CLAUDE.md` §0.2).
  `project.yaml` 을 읽으려고 대상의 `ProjectConfig` 를 복사해 오면 그 순간 포크가 시작되고,
  대상이 스키마를 바꿀 때마다 여기도 따라 고쳐야 한다.

★**대시보드는 선언이 유효한지 판정하지 않는다.** 그건 대상의 일이다.
  여기서는 *무엇이 적혀 있는가* 를 보여주고, 못 읽으면 **못 읽었다고 적는다** —
  깨진 선언을 가진 프로젝트야말로 콘솔로 봐야 할 대상이다.

★못 읽은 것을 `0`·`{}` 로 바꾸지 않는다. `error` 를 채워 **모른다**고 말한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

#: ★판정 표기가 여러 형태다. 실제 관측된 것:
#:    `- 판정: **통과**` · `- 판정: 통과` · `- 판정: **통과 (기준선 기록)**`
#:    `- 판정: **부분 통과** — 설명` · `- 판정: 부분 통과`
#:    `- 판정: 통과 (★한계는 아래 참조)`
#:  괄호·설명이 뒤에 붙어도 **앞의 낱말**이 판정이다.
JUDGEMENT = re.compile(r"판정\s*:\s*\**\s*(통과|부분\s*통과|미통과|미착수)")


@dataclass
class Read:
    """읽기 결과 하나.

    ★`error` 가 있으면 `value` 를 믿지 않는다. 빈 값과 못 읽은 것을 구분하기 위해서다.
    """

    value: Any = None
    error: str | None = None
    source: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "error": self.error, "source": self.source}


# ── 조립 선언 ────────────────────────────────────────────────────────────────
def read_declaration(project: Path) -> Read:
    """`config/project.yaml` 을 **plain dict** 로 읽는다.

    ★검증하지 않는다. 스키마가 틀려도 **적힌 그대로** 보여준다 —
      "이 프로젝트는 선언이 이렇게 잘못돼 있다" 를 보는 것이 콘솔의 일이다.
    """
    path = Path(project) / "config" / "project.yaml"
    if not path.is_file():
        return Read(error="config/project.yaml 이 없다", source=str(path))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return Read(error=f"읽지 못했다: {exc}", source=str(path))
    if not isinstance(raw, dict):
        return Read(error="최상위가 매핑이 아니다", source=str(path))

    modules = raw.get("modules")
    teams = raw.get("teams")
    return Read(value={
        # ★`{"enabled": true}` 형태를 평평하게 편다. 형태가 다르면 None 으로 남긴다 —
        #   `False` 로 바꾸면 "꺼짐" 으로 읽혀 사실이 틀어진다.
        "modules": {name: (item.get("enabled") if isinstance(item, dict) else None)
                    for name, item in modules.items()} if isinstance(modules, dict) else {},
        "ports": raw.get("ports") if isinstance(raw.get("ports"), dict) else {},
        "teams": [t for t in teams if isinstance(t, dict)] if isinstance(teams, list) else [],
        "raw_keys": sorted(raw.keys()),
    }, source=str(path))


# ── DoD 판정 ─────────────────────────────────────────────────────────────────
def read_guardrails(project: Path) -> Read:
    """Read config/guardrails.yaml without inventing missing values."""
    path = Path(project) / "config" / "guardrails.yaml"
    if not path.is_file():
        return Read(error="config/guardrails.yaml missing", source=str(path))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return Read(error=f"could not read guardrails: {exc}", source=str(path))
    if not isinstance(raw, dict):
        return Read(error="guardrails root is not a mapping", source=str(path))
    context = raw.get("context")
    return Read(value={"context": context if isinstance(context, dict) else {}, "raw": raw},
                source=str(path))


@dataclass
class Judgement:
    id: str
    judgement: str
    title: str
    path: str
    has_reproduction: bool = False
    has_actual_output: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "judgement": self.judgement, "title": self.title,
                "path": self.path, "has_reproduction": self.has_reproduction,
                "has_actual_output": self.has_actual_output}


_OUTPUT_HINT = re.compile(r"실제\s*출력|실측\s*(?:결과|출력)|실제\s*결과", re.IGNORECASE)


def read_judgements(project: Path) -> Read:
    """`wiki/records/evidence/DoD-*.md` 의 판정을 모은다 (2026-09-08 전엔 `docs/evidence/`).

    ★재현 블록·실제 출력 유무를 함께 낸다. 판정만 보면
      "통과라고 적혀 있는데 근거가 없는" 문서를 구분할 수 없다.
    """
    folder = Path(project) / "wiki" / "records" / "evidence"
    if not folder.is_dir():
        return Read(value=[], error="wiki/records/evidence 가 없다", source=str(folder))

    items: list[Judgement] = []
    failures: list[str] = []
    for path in sorted(folder.glob("DoD-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            # ★조용히 건너뛰지 않는다. 못 읽은 것을 세어 보고한다.
            failures.append(f"{path.name}: {exc}")
            continue
        match = JUDGEMENT.search(text)
        judgement = re.sub(r"\s+", "", match.group(1)) if match else "판정 없음"
        stem = path.stem
        items.append(Judgement(
            id=stem.split("_")[0],
            judgement=judgement,
            title=stem.split("_", 1)[1].replace("_", " ") if "_" in stem else "",
            path=path.name,
            has_reproduction="```" in text,
            has_actual_output=bool(_OUTPUT_HINT.search(text)),
        ))

    error = f"{len(failures)}개 문서를 읽지 못했다: " + "; ".join(failures) if failures else None
    return Read(value=items, error=error, source=str(folder))


def judgement_counts(items: list[Judgement]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.judgement] = counts.get(item.judgement, 0) + 1
    return counts


# ── 평가 실행 ────────────────────────────────────────────────────────────────
@dataclass
class EvalRun:
    """평가 리포트 하나의 요약.

    ★비용·토큰은 **실측(observed)과 추정(estimated)을 섞지 않는다.**
      대상의 `config.estimated_cost_usd` 는 돌리기 전 추정이고,
      행별 `cost_usd` 합이 실측이다. 하나로 뭉치면 거짓이 된다.
    """

    file: str
    rows: int
    arm: str | None = None
    provider: str | None = None
    model: str | None = None
    dataset: str | None = None
    dataset_sha256: str | None = None
    prompt_snapshot: str | None = None
    ablations: list[str] = field(default_factory=list)
    observed_cost_usd: float | None = None
    estimated_cost_usd: float | None = None
    note: str | None = None

    @property
    def is_mock(self) -> bool:
        return str(self.provider).lower() == "mock"

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "is_mock": self.is_mock}


def read_eval_runs(project: Path, *, limit: int | None = None) -> Read:
    """`eval/reports/*.jsonl` 을 run 단위로 요약한다.

    ★`limit` 를 쓰면 **몇 개 중 몇 개인지** 함께 낸다. 말없이 자르면
      화면이 "이게 전부" 로 읽힌다.
    """
    folder = Path(project) / "eval" / "reports"
    if not folder.is_dir():
        return Read(value={"runs": [], "total": 0, "shown": 0},
                    error="eval/reports 가 없다", source=str(folder))

    paths = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    total = len(paths)
    selected = paths[:limit] if limit else paths

    runs: list[EvalRun] = []
    for path in selected:
        try:
            lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        except OSError as exc:
            runs.append(EvalRun(file=path.name, rows=0, note=f"읽지 못했다: {exc}"))
            continue
        if not lines:
            runs.append(EvalRun(file=path.name, rows=0, note="빈 파일"))
            continue
        try:
            first = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            runs.append(EvalRun(file=path.name, rows=len(lines), note=f"형식 불명: {exc}"))
            continue

        config = first.get("config") if isinstance(first.get("config"), dict) else {}
        observed = _sum_costs(lines)
        runs.append(EvalRun(
            file=path.name, rows=len(lines),
            arm=first.get("arm") or config.get("arm"),
            provider=config.get("provider") or first.get("provider"),
            model=config.get("model"),
            dataset=config.get("dataset"),
            dataset_sha256=config.get("dataset_sha256"),
            prompt_snapshot=config.get("prompt_snapshot") or config.get("prompt_version"),
            ablations=list(config.get("ablations") or []),
            observed_cost_usd=observed,
            estimated_cost_usd=config.get("estimated_cost_usd"),
        ))

    return Read(value={"runs": runs, "total": total, "shown": len(runs)}, source=str(folder))


def _sum_costs(lines: list[str]) -> float | None:
    """행별 실측 비용의 합. ★한 줄도 값이 없으면 `0.0` 이 아니라 `None`(모름)이다."""
    total = 0.0
    seen = False
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = row.get("cost_usd")
        if isinstance(value, (int, float)):
            total += float(value)
            seen = True
    return round(total, 4) if seen else None
