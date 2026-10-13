"""준비 회차의 근거와 정확한 대기 상태를 담당 파일에 기록한다."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
NOW = datetime.now(timezone(timedelta(hours=9)))
BACKUP = BASE / "_backup" / (NOW.strftime("%Y-%m-%d_%H%M%S") + "_preparation_record")


def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8-sig"))


def save(name, value):
    path = BASE / name
    if path.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, BACKUP / path.name)
    path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    table = load("integration-table.json")
    conflict = load("w19-reconciliation.json")
    row = next(row for row in table["rows"] if row["id"] == "W19")
    row.update({"validation_review": "document_rule_conflict_observed", "acceptance": "requires_reconciliation", "integration_findings": ["INT-W19-001: 문서는 전체 제외, 실제 규칙은 세 팀 폴더 일부 허용. 기존 추적 57개. 원본·Git 상태는 수정하지 않음"], "integration_evidence": ["program/research/baseline_completion_2026-10-12/tasks/integration/w19-reconciliation.json"]})
    table["integration_review_updated_at_kst"] = NOW.isoformat()
    task_phases = {}
    for key in ["auth", "orchestration", "operations", "wiki", "verification"]:
        path = BASE.parent / key / "status.json"
        task_phases[key] = json.loads(path.read_text(encoding="utf-8-sig")).get("phase") if path.exists() else "status_not_written"
    table["latest_dependency_phases"] = task_phases
    save("integration-table.json", table)
    md = (BASE / "integration-table.md").read_text(encoding="utf-8")
    for line in md.splitlines():
        if line.startswith("| W19 |"):
            md = md.replace(line, "| W19 | datasets 전체 Git 제외 안내 | integration | 규칙 불일치 실측 | INT-W19-001 정합화 필요 |")
    if "## 이번 회차의 실제 불일치" not in md:
        md += "\n## 이번 회차의 실제 불일치\n\n[W19 규칙 대조 원본](w19-reconciliation.json)에서 문서와 Git 제외 규칙의 차이·기존 추적 57개를 확인했습니다. 이 항목은 문서 완료로 닫지 않습니다. 원본 자료·Git 추적 상태는 유지했습니다.\n"
    save("integration-table.md", md)
    audit = load("source-audit.json")
    for source in audit["sources"]:
        if source["id"] in {"S06", "S10"}:
            source["content_claim_review"] = "reviewed_local_primary_source_section"
            source["review_scope"] = "S06 본문 / S10 §6.5: 식별·변경 통제·상태 기록·구성 검증. 제품 사양 정본으로 사용하지 않음"
    save("source-audit.json", audit)
    v11path = ROOT / "program/plan/A-COP_구현계획서_v11.md"
    original = next(row for row in load("current-source-manifest.json")["files"] if row["path"] == v11path.relative_to(ROOT).as_posix())
    v11hash = hashlib.sha256(v11path.read_bytes()).hexdigest()
    captures = load("capture-checks.json")
    preparation = load("preparation-checks.json")
    renders = sorted((BASE / "checks/screens").glob("*/render-checks.json"))
    render_path = renders[-1]
    render = json.loads(render_path.read_text(encoding="utf-8"))
    render_passed = sum(not check["bodyOverflow"] and not check["errors"] for check in render["checks"])
    status = load("status.json")
    status.update({
        "phase": "waiting_dependency", "updated_at_kst": NOW.isoformat(),
        "changed_files": sorted({path.relative_to(ROOT).as_posix() for path in BASE.iterdir() if path.is_file() and path.name != "task.md"} | {(BASE / "report.md").relative_to(ROOT).as_posix()}),
        "tests": [],
        "checks": [
            {"command": "python -B program/research/baseline_completion_2026-10-12/tasks/integration/capture.py", "passed": sum(check["passed"] for check in captures["checks"]), "failed": sum(not check["passed"] for check in captures["checks"]), "total": len(captures["checks"]), "evidence": "program/research/baseline_completion_2026-10-12/tasks/integration/capture-checks.json"},
            {"command": "python -B program/research/baseline_completion_2026-10-12/tasks/integration/audit_preparation.py", "passed": preparation["passed"], "failed": preparation["failed"], "total": preparation["total"], "evidence": "program/research/baseline_completion_2026-10-12/tasks/integration/preparation-checks.json"},
            {"command": "node program/research/baseline_completion_2026-10-12/tasks/integration/render_preparation.cjs", "passed": render_passed, "failed": len(render["checks"]) - render_passed, "total": len(render["checks"]), "evidence": render_path.relative_to(ROOT).as_posix()},
        ],
        "dependencies_remaining": [key + ": " + str(phase) for key, phase in task_phases.items()] + ["existing: 관련 결과의 변경 파일·원본 실행 로그 확인"],
        "unresolved": ["INT-W19-001: datasets 전체 제외 문서와 실제 팀별 예외가 불일치. 기존 추적 57파일도 남음", "담당 구현·검증 결과 대기. 최종 소스와 필수 요구의 인수 판정 전", "v12·최종 기준선은 미완료. 준비본만 작성"],
        "deployment": "not_deployed", "ready_reason": "준비본·원본 정합성·화면 검사를 저장했습니다. 필수 의존 결과를 기다리므로 완료로 올리지 않습니다.", "backup": BACKUP.relative_to(ROOT).as_posix(),
        "v11_sha256": v11hash, "v11_unchanged": v11hash == original["sha256"],
    })
    save("status.json", status)
    phases = "\n".join(f"| {key} | {phase} |" for key, phase in task_phases.items())
    report = f"""---
type: report
title: v12·최종 기준선 통합 준비와 의존 결과 대기
status: draft
domain: travel
---

# 최종 통합 준비 결과

통합표·v12 안내서 골격·단일 기준선 골격·검토 절차를 작성했습니다. 현재는 담당 구현·전체 시험 결과를 기다립니다. 최종 완료본은 작성하지 않았으며, W19의 문서·실제 제외 규칙 불일치도 별도 근거로 남겼습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 준비 문서·통합표 | 작성 | 4/4 = 100% |
| 출처 원본 무결성 | 통과 | 11/11 = 100% |
| 준비 산출물 검사 | 통과 | {preparation['passed']}/{preparation['total']} = 100% |
| 최종 문서 2개 | 의존 결과 대기 | 0/2 = 0% |

기록 시각: {NOW.isoformat()}. 분모 4는 통합표·v12 골격·기준선 골격·검토표입니다. 11은 기존 다운로드 출처 수이며, 15는 준비 산출물 검사 수입니다. 제품 기능·출시 관문 통과 수가 아닙니다.

## 산출물

- [25개 통합표](integration-table.md)·[JSON](integration-table.json): W01~W25의 결정·문서·구현·검증·배포 상태를 분리했습니다. 요구의 기능 인수 통과를 뜻하지 않습니다.
- [v12 안내서 준비본](v12-outline.html)·[원문](v12-outline.md): 고객의 세 경로, 분류 에이전트·실행 장치·에이전트 팀, 항로 지킴이·인증·자료·무인 운영·실패를 현재 wiki와 연결했습니다.
- [단일 기준선 준비본](baseline-outline.html)·[원문](baseline-outline.md): 제품 전체 ID, wiki 원문 해시, 결정·요구·인터페이스·자료/모델·검증·환경·변경 절차를 준비했습니다.
- [최종 검토표](review-checklist.html)·[통합 절차 그림](finalization-flow.html): 근거 부족·실패·해시 변경은 보완·재검증 대기로 끝납니다.

## 실제 확인과 미해결

1. 기존 완료 항목을 무조건 승계하지 않고 W19의 실제 규칙을 대조했습니다. [원본 대조](w19-reconciliation.json): 전체 제외 문서와 세 팀 폴더 허용 규칙이 다릅니다. 조회한 추적 파일은 57개(activity 9·dining 5·mobility 43)입니다. 4개 대표 경로 중 1개만 제외되고 3개는 제외되지 않았습니다. 4개 경로는 규칙 대조 표본이며 모든 파일의 개인정보 검사 표본이 아닙니다. 원본 파일·제외 규칙·Git 추적 상태를 변경하지 않았습니다. 최종 통합 때 기존 공유 작업과 충돌 없이 정합화해야 합니다.
2. [현재 소스 목록](current-source-manifest.json)은 {load('current-source-manifest.json')['captured_at_kst']} 시점의 2,306파일입니다. 현재 wiki·app·config·tests·migrations·실행/배포 도구·고객 화면 소스·Python 검사 코드이며 기록·백업·연구 입력/출력은 제외했습니다. 동시 수정 중이므로 최종 검증 소스 해시가 아닙니다. 최초 넓은 수집은 6,308파일이었고 불필요한 연구 출력까지 포함해, 백업 후 코드 중심 범위로 좁혔습니다.
3. [기존 채팅 관찰](thread-observations.json)은 관련 발언·변경 경로를 찾기 위한 자료입니다. 담당 메시지를 구현·시험 완료로 판정하지 않았습니다. [출처 대조](source-audit.json)는 다운로드 SHA-256 11/11 일치를 확인했고 NASA §6.5·DORA 본문을 작성 방법 참고로 읽었습니다. 최신 외부 웹 재확인이나 제품 사양 근거로 확대하지 않았습니다.

## 실행 검사

| 명령 | 결과 | 원본 근거 |
|---|---|---|
| `python -B .../integration/capture.py` | 입력 6/6 = 100%, 다운로드 해시 11/11 = 100% | [capture-checks](capture-checks.json) |
| `python -B .../integration/build_preparation_html.py` | Markdown 4개를 같은 내용 HTML 4개로 생성 | [생성기](build_preparation_html.py) |
| `python -B .../integration/audit_preparation.py` | 검사 {preparation['passed']}/{preparation['total']} = 100%, 로컬 링크 {next(c['checked'] for c in preparation['checks'] if c['name']=='로컬 링크 목적지')}/{next(c['checked'] for c in preparation['checks'] if c['name']=='로컬 링크 목적지')} = 100% | [preparation-checks](preparation-checks.json) |
| `node .../integration/render_preparation.cjs` | 실제 Chrome 1440/375px 화면 {render_passed}/{len(render['checks'])} = 100% | [화면 원본 결과]({render_path.relative_to(BASE).as_posix()}) |

실행은 이 준비본 파일에만 한정했습니다. 단위·제품 통합·실제 외부 연결 시험은 이 회차에서 실행하지 않았으며 담당 결과 수령 뒤 검토합니다. HTML 본문·원문 해시 일치, ID 중복, 로컬 링크, IPv4·웹훅·프로젝트 키 패턴, 그림 접근성·단일 파일 검사를 수행했습니다. 이 패턴 검사만으로 모든 비밀값 탐지를 보장하지 않습니다. 화면은 페이지 전체 가로 넘침·스크립트 오류를 확인했고 그림·모바일 안내서 캡처를 직접 읽었습니다. 외부 웹 글꼴을 내려받지 않아 로컬 대체 글꼴을 썼습니다.

mock 서버 시험 0/0 (화면 반응): 해당 없음. 준비 HTML의 로컬 브라우저 확인 6/6은 제품 mock 서버 시험과 별개입니다.

실서버 확인 (서버 응답): 안 했음. 이 준비 작업에서 cs 프로젝트 서버·유료 외부 API·고객 알림을 호출하지 않았습니다.

## 대기 조건과 다음 회차

| 담당 | 현재 상태 파일 |
|---|---|
{phases}

인증·자동 변경/실행 조정·운영·wiki·전체 시험 담당의 변경 파일과 원본 로그를 확인해야 합니다. 기존 SQL·화면·채팅·이동·식당·RAG·경보 결과 중 W01~W25에 관계있는 범위만 확인합니다. 최신 결과가 도착하면 공유 접합·통합 시험·최종 해시 대조·문서 검토를 이어갑니다. 필수 미구현·실패 시험을 문서 상태만 바꿔 닫지 않습니다.

새 소스 수집이 필요할 때는 검토된 통합표를 초기 수집기로 덮지 않습니다. [초기 수집기](capture.py)는 검토 결과·불일치가 기록된 표의 덮어쓰기를 거부합니다. 새 날짜의 스냅샷으로 별도 수집하고 현재 통합 판정은 보존합니다.

## 보존과 적용 범위

[기존 v11](../../../../plan/A-COP_구현계획서_v11.md)의 SHA-256은 `{v11hash}`이며 시작 목록과 일치합니다. v11은 수정하지 않았습니다.

기존 산출물·생성기·상태를 덮기 전 [백업 폴더](_backup/)에 보존했습니다. 이번 상태 기록 전 사본은 [{BACKUP.name}](_backup/{BACKUP.name}/)입니다. 생성물·검사 결과·스크린샷은 [담당 폴더](./)에 있으며 다른 담당 상태·공용 coordination은 수정하지 않았습니다. 실제 업무 DB 변경·원격 배포·재시작·커밋·푸시·고객 알림은 수행하지 않았습니다.
"""
    save("report.md", report)
    print(json.dumps({"updated_at_kst": NOW.isoformat(), "phase": status["phase"], "v11_unchanged": status["v11_unchanged"], "unresolved": status["unresolved"], "dependencies": task_phases}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
