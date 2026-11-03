# 라우팅 A11 작업 폴더 10개 보관·삭제 (2026-10-31)

사용자 지시(2026-10-31, 텔레그램 경유: 「담당 세션들이 직접 작업을 마무리하고 전부 삭제하라」)에 따라 `C:/_proj/` 아래 라우팅 A11 작업 폴더 10개를 고유 자료만 보관한 뒤 지웠다. 삭제 10/10 = **100%**, 보관본 검증 11,015/11,015 = **100%**.

## 결론은 이미 인계 문서에 있다

각 폴더의 결론은 아래 인계 문서에 있다. 이 문서는 결론을 새로 쓰지 않고, 문서에 적힌 **옛 경로가 어디로 옮겨졌는지**만 적는다.

- [A11 실DB 기준판 대조](../../handoff/2026-10-29_routing-a11-real-db.md) — `routinga11base1029` · `routinga11verify1029` · `routingresume1029`
- [체크아웃만 있는 숙박](../../handoff/2026-10-29_routing-a11-checkout-only-lodging.md) · [독립 검토](../../handoff/2026-10-29_routing-a11-checkout-only-independent-review.md) — `routinga11fix1029_evidence` · `routinga11indep1029_evidence`
- [체크아웃 선택 검토 수정](../../handoff/2026-10-29_routing-a11-checkout-choice-review-fix.md) · [독립 확인](../../handoff/2026-10-29_routing-a11-checkout-choice-independent-verify.md) — `routinga11p2fix1029_evidence`
- [미답 종류 기본 화면 경로](../../handoff/2026-10-29_routing-a11-unanswered-kind-default-screen-path.md) — `routinga11kindpath1029_evidence`
- [종류 질문 다시 열기 · ready](../../handoff/2026-10-29_routing-a11-reopen-kind-question-ready.md) — `routinga11reopen1029_evidence`
- [ready 독립 보안 검토 재개](../../handoff/2026-10-29_a11-ready-independent-resume.md) — `routinga11readyreview1029_evidence` · `routingresume1029`

빠진 결론: 없음. 상태도 바뀌지 않았다. A11 후보는 **통합·push 보류(HOLD)**이고, 이번 작업으로 통합되지 않았다.

## 옛 경로 → 보관 위치

보관 루트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/<폴더>/`. 폴더마다 `<폴더>.tar.gz`, `manifest.tsv`(경로·크기·sha256), `excluded.txt`, `verify.json`이 있다.

| 옛 폴더 | 보관한 것 | 파일 | 지운 바이트 |
|---|---|---|---|
| routinga11base1029 (worktree, HEAD `d1b06357e`) | 미추적 시험 1개, `git/` (HEAD·status·빈 patch) | 1/1 | 378,672,491 |
| routingresume1029 (worktree, 브랜치 `routing-resume-1029` = `d1b06357e`) | 미추적 10개, `git/worktree-vs-HEAD.patch`(61,562 B, 수정 16개), 번들 2개 | 10/10 | 591,774,618 |
| routinga11verify1029 (증거 + PG16 pgdata) | 로그·XML·JSON·스크립트·`pgdata` 전체 | 8,566/8,566 | 222,098,297 |
| routingresume1029_evidence | 전체 | 36/36 | 1,783,169 |
| routinga11fix1029_evidence (pgdata 포함) | 전체 | 1,940/1,940 | 75,510,557 |
| routinga11indep1029_evidence | 전체 | 11/11 | 51,652 |
| routinga11kindpath1029_evidence | 전체 | 119/119 | 2,145,901 |
| routinga11p2fix1029_evidence | 전체 | 69/69 | 1,840,263 |
| routinga11readyreview1029_evidence | 전체 | 107/107 | 4,128,322 |
| routinga11reopen1029_evidence | 전체 | 156/156 | 5,368,215 |

합계: 지운 바이트 1,283,373,485, 보관본 53,965,090 B.

- **Git**: 커밋 `c644763da`·`3e72afa27`·`d1b06357e`는 허브 저장소의 원격 참조에 없다. 원본 `C:/_proj/final_workspace`에도 없다. 보관한 번들은 둘이다. `routingresume1029/git/d1b06357e.bundle`은 허브 기준이고 `fab3da50a`가 필요하다. `d1b06357e-vs-final_workspace.bundle`은 커밋 14개를 담는다. 필요 커밋은 `c714eecdb`이고, 원본에 이 커밋이 있어 `bundle verify`가 통과했다. 복원 순서: 번들을 fetch → `d1b06357e`를 체크아웃 → patch를 `git apply` → 미추적 파일 풀기.
- **허브**: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/routing-open-20261028/repo`. 이 저장소에서 `git worktree prune`으로 두 worktree 항목을 지웠고, 브랜치는 남아 있다. 원본 Git은 바꾸지 않았다.
- **PG**: PID 38472(`routinga11verify1029/pgdata`, 포트 63941)는 리슨만 하고 있었고 ESTABLISHED 연결은 0이었다. `pg_ctl stop -m fast`로 끈 뒤 보관했다. 이 PG의 로그는 `routinga11readyreview1029_evidence/pg.log`에 쌓이고 있었다.
- **링크**: `routingresume1029/.../apps/web/node_modules`는 원본 `node_modules`를 가리키는 junction이었다. 링크만 제거했다. 원본 `node_modules`는 그대로 있다(항목 304개). 바깥에서 10개 폴더를 가리키는 링크는 0개다(`C:/_proj`와 프로필 scratch에서 reparse point 761개를 검사).
- **제외**: 재생성 캐시(`__pycache__`·`.ruff_cache`·`.next`·`node_modules`·`tsconfig.tsbuildinfo`·`next-env.d.ts`)와 비밀 패턴 이름 파일 `routinga11verify1029/auth-diagnostic.log`는 보관하지 않았다. `excluded.txt`에 이름만 남겼다.
- **영향**: 위 인계 문서에 적힌 `C:/_proj/routinga11*` · `routingresume1029*` 경로는 이제 없다. 같은 상대 경로가 해당 tar.gz 안에 있다. 인계 문서 본문은 기록이라 고치지 않았다.

## 책임과 재확인 (2026-10-31 후속)

- 폴더를 만든 곳: 구구루트 총괄 Telegram 세션 `20261027_205452_5fbd35ab` — Codex exec 스레드(01a18661-7a1e, 01a1866b, 01a18784 등)와 Hermes 하위 세션(5b0e9f, 9b8d19, 5002f5, 7ae533, 20c7f7, f7610f, 44dcaf, A11 deleg_*).
- 정리·삭제 담당: 라우팅 세션 `20261024_213155_36cd5c`(하위 `deleg_bd131b61`).
- 보존본 재확인 결과: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/_routing_session_result.json` 의 `readback_20261031`.
