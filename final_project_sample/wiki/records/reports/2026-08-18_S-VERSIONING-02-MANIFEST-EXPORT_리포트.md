# S-VERSIONING-02-MANIFEST-EXPORT 실행 보고서

## 구현 결과

- `scripts/basement_manifest.py`: 5개 basement 컴포넌트를 명시적으로 선언하고 파일을 안정적인 상대 경로 순서로 수집한다.
- `scripts/export_basement.py`: 선언 파일을 `dist/basement/files/`로 복사하고 SHA-256 manifest를 생성한다.
- `tests/unit/scripts/test_export_basement.py`: 파일 일치·해시·제외 패턴·도메인 디렉터리 비수집을 검증한다.
- `wiki/records/handoff/15_basement_버전_배포_계약.md`: 경계, manifest 계약, export와 cs 적용 절차, SemVer 규칙을 문서화했다.

`dist/`는 기존 `.gitignore`의 build output 규칙으로 이미 제외되어 있으며, 생성 산출물은 커밋하지 않는다.

## 실행 명령과 결과

```powershell
python -m scripts.export_basement
# exported 60 files to ...\dist\basement\manifest.json

python -m pytest tests/unit/scripts/test_export_basement.py -q --basetemp .pytest-tmp/basement-tests
# 2 passed

python -m pytest -q --ignore=tests/integration/rag --basetemp .pytest-tmp/full-tests
# 352 passed, 1 failed, 1 deselected
```

전체 회귀의 유일한 실패는 기존 `examples/tests/test_team_scenarios.py::test_tool_allowlist_and_repetition_guard`이며,
`ReadToolbox`에서 `read.subscription`이 등록되지 않아 발생했다. 이번 export 변경과 무관하다.
기본 pytest 임시 디렉터리는 Windows 권한 오류가 있어 저장소 내부 basetemp로 실행했다.

## 실제 생성 manifest 발췌

```json
{
  "basement_version": "0.2.0",
  "source_commit": "be298c77b322a05dfe683d38f8fced88f6336448",
  "source_tag": null,
  "generated_at": "2026-08-18T08:21:35.642464Z",
  "components": ["app/core", "app/domain", "app/application", "app/infrastructure", "app/presentation"],
  "excluded": ["__pycache__", "*.pyc", "app/infrastructure/db/migrations/002_domain_*.sql"],
  "files": [
    {"path": "app/application/__init__.py", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
  ],
  "contract_version": "1.0",
  "export_tool_version": "1"
}
```

실제 manifest의 `files` 배열에는 60개 파일이 들어가며, 위 발췌의 파일 해시는 export된 파일과 대조했다.
