"""통합 검토용 읽기 전용 스냅샷. 담당 상태는 완료 판정을 대신하지 않는다."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
WORK = OUT.parents[1]
KST = timezone(timedelta(hours=9))
EXCLUDED = {"_backup", "records", "legacy", ".git", "node_modules", "__pycache__"}
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml", ".sql", ".toml", ".tsx", ".ts", ".css", ".txt"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fingerprint(path: Path):
    rel = path.relative_to(ROOT).as_posix()
    if not path.is_file():
        return {"path": rel, "exists": False, "sha256": None}
    raw = path.read_bytes()
    return {"path": rel, "exists": True, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def local_link(path: str, label: str | None = None):
    # 작업 보고는 폴더 안에서 엽니다. HTML 생성 때 상대 링크의 기준을 다시 맞춥니다.
    import os
    rel = os.path.relpath(ROOT / path, OUT).replace("\\", "/")
    return f"[{label or path}]({rel})"


def write(path: Path, value: str | dict | list, backup: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        dest = backup / path.relative_to(OUT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def capture():
    prior_table = OUT / "integration-table.json"
    if prior_table.exists():
        prior = read_json(prior_table)
        if any(row.get("acceptance") != "pending" or row.get("tests") or row.get("integration_findings") for row in prior.get("rows", [])):
            raise SystemExit("이미 검토한 통합표를 초기 스냅샷으로 덮어쓰지 않습니다. 별도 판본으로 수집하세요.")
    now = datetime.now(KST)
    stamp = now.strftime("%Y-%m-%d_%H%M%S_%f")
    backup = OUT / "_backup" / f"{stamp}_capture"
    base = read_json(ROOT / "program/research/review_status_2026-10-12/status.json")
    choices = read_json(ROOT / "program/research/wiki_review_2026-10-11/findings-v2.json")
    coordination = read_json(WORK / "coordination.json")
    findings = {row["id"]: row for row in choices["findings"]}
    sources = read_json(ROOT / "program/research/baseline_2026-10-10/source-manifest.json")
    statuses = {}
    dependency_rows = []
    for task in coordination["new_sessions"]:
        if task["key"] == "integration":
            continue
        path = WORK / "tasks" / task["key"] / "status.json"
        status = read_json(path) if path.exists() else None
        statuses[task["key"]] = status
        dependency_rows.append({"key": task["key"], "thread_id": task["thread_id"], "phase": status.get("phase") if status else "status_not_written", "status_file": fingerprint(path)})

    rows = []
    for source in base["items"]:
        wid = source["id"]
        finding = findings[wid]
        owners = [t["key"] for t in coordination["new_sessions"] if wid in t["w_ids"] and t["key"] != "integration"]
        evidence = []
        for prior in source["evidence"]:
            current = fingerprint(ROOT / prior["path"])
            current["input_sha256"] = prior.get("sha256")
            current["changed_since_input"] = current.get("sha256") != prior.get("sha256")
            evidence.append(current)
        rows.append({
            "id": wid, "requirement_id": f"TRP-REQ-{wid}", "subject": source["subject"],
            "decision": finding.get("decision", "[미확보] 원문 확인 필요"),
            "selection": finding.get("selected", source.get("selection")),
            "input_document_status": source["status"], "document_evidence": evidence,
            "owners": owners,
            "owner_phases": {key: statuses[key].get("phase") if statuses[key] else "status_not_written" for key in owners},
            "retained_document_only": wid in coordination["retained_completed_items"],
            "implementation_review": "not_applicable_document_item" if wid in coordination["retained_completed_items"] else "pending_evidence_review",
            "validation_review": "pending_independent_review",
            "deployment": "not_deployed_by_this_task",
            "remaining_from_input": source["remaining"], "acceptance": "pending",
            "tests": [], "integration_findings": [],
        })

    audits = []
    for entry in sources["sources"]:
        path = ROOT / "program/research/baseline_2026-10-10" / entry["file"]
        current = fingerprint(path)
        text_path = ROOT / "program/research/baseline_2026-10-10/source-text" / (entry["id"] + ".txt")
        audits.append({"id": entry["id"], "title": entry["title"], "url": entry["url"], "scope": entry["scope"], "download": current, "matches_download_manifest": current.get("sha256") == entry.get("sha256"), "extracted_text": fingerprint(text_path), "current_web_recheck": "not_performed", "content_claim_review": "pending"})

    manifest = []
    roots = ["wiki", "final_project_cs/wiki", "final_project_cs/app", "final_project_cs/config", "final_project_cs/tests", "final_project_cs/migrations", "final_project_cs/scripts", "final_project_cs/deploy", "final_project_cs/frontend/apps/web/src", "program/scripts"]
    for name in roots:
        directory = ROOT / name
        for current, directories, filenames in os.walk(directory):
            omitted = EXCLUDED | {"results", "sources", "source-text", "inputs", "outputs", ".pytest_cache", "screens", "renders"}
            directories[:] = sorted(d for d in directories if d not in omitted)
            for filename in sorted(filenames):
                path = Path(current) / filename
                allowed = {".py"} if name == "program/scripts" else EXTENSIONS
                if path.suffix in allowed:
                    manifest.append(fingerprint(path))
    for name in ["AGENTS.md", "final_project_cs/AGENTS.md", "final_project_cs/RULE.md", "final_project_cs/requirements.txt", "program/plan/A-COP_구현계획서_v11.md"]:
        manifest.append(fingerprint(ROOT / name))
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    metadata = {"captured_at_kst": now.isoformat(), "phase": "preparation_snapshot", "source_scope": roots, "excluded_directory_names": sorted(EXCLUDED | {"results", "sources", "source-text", "inputs", "outputs", ".pytest_cache", "screens", "renders"}), "program_scripts_scope": "Python 검사·생성 코드만. 연구 입력·출력은 담당 실측 근거를 별도로 연결", "source_manifest_sha256": digest, "warning": "파일 존재·해시 확인은 기능·시험·배포 완료 판정이 아닙니다."}
    checks = [
        {"name": "요구 ID 25개 일치", "passed": {r["id"] for r in rows} == {f"W{i:02}" for i in range(1, 26)}},
        {"name": "사용자 선택 보존", "passed": all(r["selection"] == choices["confirmed_choices"].get(r["id"], r["selection"]) for r in rows)},
        {"name": "출발점 근거 파일 존재", "passed": all(e["exists"] for r in rows for e in r["document_evidence"])},
        {"name": "다운로드 11개 무결성", "passed": len(audits) == 11 and all(a["matches_download_manifest"] for a in audits)},
        {"name": "출처 텍스트 11개 존재", "passed": len(audits) == 11 and all(a["extracted_text"]["exists"] for a in audits)},
        {"name": "완료 판정 자동 승격 없음", "passed": all(r["acceptance"] == "pending" for r in rows)},
    ]
    write(OUT / "integration-table.json", {**metadata, "dependencies": dependency_rows, "rows": rows}, backup)
    write(OUT / "source-audit.json", {**metadata, "sources": audits}, backup)
    write(OUT / "current-source-manifest.json", {**metadata, "files": manifest}, backup)
    write(OUT / "capture-checks.json", {**metadata, "checks": checks}, backup)
    lines = ["# 25개 항목 통합 검토표 — 준비 스냅샷", "", "담당 상태와 원본 파일 존재를 수집했습니다. 아래 표는 인수 시험 완료표가 아닙니다.", "", f"확인 시각: {now.isoformat()}", "", "| 항목 | 요구 | 담당 | 담당 상태 | 검토 판정 |", "|---|---|---|---|---|"]
    for row in rows:
        phases = ", ".join(f"{k}: {v}" for k, v in row["owner_phases"].items()) or "문서 근거 재확인 대기"
        lines.append(f"| {row['id']} | {row['subject']} | {', '.join(row['owners']) or 'integration'} | {phases} | 근거 검토 대기 |")
    lines.extend(["", "## 근거 파일", "", local_link((OUT / "integration-table.json").relative_to(ROOT).as_posix(), "해시·결정·구현·검증·환경 상태 상세") + " — 항목별 상태를 분리한 기계 판독 자료입니다.", "", "## 판정 제한", "", "- 담당 채팅의 완료 메시지와 상태 파일만으로 통과 처리하지 않습니다. 변경 파일·원본 시험 로그와 최종 해시를 대조합니다.", "- 기존 SQL·화면·채팅·이동·식당·RAG·경보 작업 중 이 요구와 관계있는 결과만 확인합니다.", "- 배포·실제 업무 DB 변경·커밋·푸시·고객 알림은 이번 작업에서 수행하지 않습니다.", ""])
    write(OUT / "integration-table.md", "\n".join(lines), backup)
    status = {
        "phase": "waiting_dependency", "updated_at_kst": now.isoformat(), "w_ids": ["W11"],
        "changed_files": [(OUT / name).relative_to(ROOT).as_posix() for name in ["capture.py", "integration-table.json", "integration-table.md", "source-audit.json", "current-source-manifest.json", "capture-checks.json"]],
        "tests": [], "checks": {"command": "python -B program/research/baseline_completion_2026-10-12/tasks/integration/capture.py", "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "total": len(checks), "evidence": (OUT / "capture-checks.json").relative_to(ROOT).as_posix()},
        "report": (OUT / "report.md").relative_to(ROOT).as_posix(),
        "dependencies_remaining": [d["key"] + ": " + str(d["phase"]) for d in dependency_rows] + ["existing: 관련 SQL·화면·채팅·이동·식당·RAG·경보의 실제 결과 검토"],
        "unresolved": ["담당 구현·검증 결과 대기. v12·최종 기준선 완료 선언 전 필수 요구·시험 판정 필요"],
        "deployment": "not_deployed", "ready_reason": "의존 결과를 기다리며 통합표·입력·출처 무결성 확인을 준비했습니다.",
        "source_manifest_sha256": digest,
        "backup": backup.relative_to(ROOT).as_posix() if backup.exists() else "신규 생성: 덮어쓴 파일 없음",
    }
    write(OUT / "status.json", status, backup)
    print(json.dumps({"captured_at_kst": now.isoformat(), "rows": len(rows), "source_files": len(manifest), "download_hashes_matched": sum(a["matches_download_manifest"] for a in audits), "checks_passed": sum(c["passed"] for c in checks), "checks_total": len(checks), "dependencies": dependency_rows, "source_manifest_sha256": digest}, ensure_ascii=False))
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(capture())
