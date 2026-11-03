# 2026-10-26 루트 보조 폴더 이름 변경(`_` → `.`) · 원격 6개 브랜치 점검

## 결론

- 사용자 지시에 따라 지우지 않는 루트 보조 폴더 3개의 이름 앞을 `.`으로 바꿨다. 삭제한 파일은 없다.
- 원격 6개 브랜치(팀·개인 각각 `main`·`develop`·`role-manager`)에는 원래부터 이 폴더들이 없다. 지울 것이 없어서 원격에는 아무것도 푸시하지 않았다.

## 로컬 이동 (원본 작업 폴더)

| 전 | 후 | 파일 수 |
|---|---|---|
| `_backup/` (27개 항목, 4.5MB) | 기존 `.backup/`에 합침(이름 겹침 0) | 207 → `.backup/` 전체 213개(기존 3 + 이번 207 + 아래 백업 3) |
| `_experiments/` | `.experiments/` | 662 → 662 |
| `_explain/` | `.explain/` | 2 → 2 |

- 이동은 같은 드라이브 안에서 `mv -n`(덮어쓰지 않음)으로 했다. 빈 `_backup/` 폴더만 지웠다.
- 세 폴더는 이동 전에도 git 추적 파일이 0개였고 ignore 상태였다. 이동 후에도 ignore 상태다(`git status --ignored`로 확인).
- `.gitignore`에 `/.experiments/`, `/.explain/`를 추가했다. `.backup/`은 원래 제외돼 있었다. 옛 `/_backup/`·`/_experiments/`·`/_explain/` 줄은 다른 사본을 위해 남겼다.
- 루트 `AGENTS.md`·`CLAUDE.md`의 백업 경로 한 줄(`_backup/2026-10-12_claude-md-line-endings/` → `.backup/...`)을 두 파일 똑같이 고쳤다. 줄바꿈은 CRLF를 유지했다.
- 수정 전 `.gitignore`·`AGENTS.md`·`CLAUDE.md`는 `.backup/2026-10-26_dot-folder-rename/`에 백업했다.
- 하위 폴더의 `_backup/`(wiki, program 등)은 이번 범위가 아니라 그대로 두었다.

## 원격 점검 (`git ls-tree`, 2026-10-26)

| 저장소 | main | develop | role-manager |
|---|---|---|---|
| 팀 SKN | `144bcfff` 없음 | `d2ab93a6` 없음 | `08b99597` 없음 |
| 개인 A-COP | `b0485d05` 없음 | `d8366bbf` 없음 | `08b99597` 없음 |

- 6개 모두 루트 `_backup`·`_experiments`·`_explain`·`.backup`·`.experiments`·`.explain` 아래 파일이 0개다.
- 원격 `.gitignore`에는 `.backup/`·`/_experiments/`가 있고 `/.experiments/`·`/.explain/`는 없다(개인 `main`은 둘 다 없음). 원격에 추가할지는 사용자 결정 사항이다.
