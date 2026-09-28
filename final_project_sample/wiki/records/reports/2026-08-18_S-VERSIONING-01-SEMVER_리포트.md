# S-VERSIONING-01 — basement SemVer 도입 보고서

## 결론

`basement` 버전을 `0.1.0`에서 `0.2.0`으로 올렸다. 기존 계약을 깨지 않는
Composer v2/JWT, Response Generation & Review Team(DoD-29), `examples/` 분리,
버그 수정이 누적된 호환 기능·구조 변경이므로 minor 버전으로 판정했다.

## 변경 사항

- `pyproject.toml`: `project.version = "0.2.0"`
- `CHANGELOG.md`: Keep a Changelog 형식으로 `0.2.0` 변경 내역과 `0.1.0` 역사적 기준을 기록
- `wiki/records/handoff/10_도메인_교체_가이드.md`: patch/minor/major 기준과 `basement_version`·domain/data revision 분리 원칙 추가

## 근거 커밋

실제 저장소 이력에서 다음 커밋을 확인해 CHANGELOG를 작성했다.

| 커밋 | 요약 | 분류 |
|---|---|---|
| `c1b1a4a` | Composer 쓰기채널 v2(JWT)와 Response Generation & Review Team(DoD-29) 추가 | Added |
| `17253ff` | 톤 결정 규칙 및 JWT 만료·위조 회귀 테스트 보강 | Added/Fixed |
| `807bd2c` | Billing/Technical Team을 `examples/`로 분리 | Changed |
| `be298c7` | `CLASSIFIED` 전이 실패가 `classification_failed`로 뭉개지던 버그 수정 | Fixed |

이전 `0.1.0` 상세 내역은 기존 CHANGELOG 또는 release tag가 없어 복원하지 않고,
최초 기록이라는 사실만 명시했다.

## 범위 제외

manifest/export 스크립트, `app/tools`와 basement/domain 경계 분리, 코드 가이드,
Git tag 생성은 이번 작업에서 수행하지 않았다.

## 검증

```powershell
python -m pytest -q --ignore=tests/integration/rag
```
