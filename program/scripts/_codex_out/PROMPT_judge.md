# 작업 — 미판정 문서 24건을 판정한다

## 배경

문서 742건을 wiki 로 이관 중이다. 휴리스틱이 **"판정필요"** 로 넘긴 것들을
사람이 판정해야 한다. 이미 79건을 판정했고 나머지를 나눠 맡는다.

## 판정 규칙

### ① 먼저 묻는다 — 이 문서가 한 가지만 하는가?

아니면 **분할**이다. type 을 고르기 전에 이걸 먼저 본다.

### ② type 을 고른다 (12개 중 하나)

| type | 무엇 |
|---|---|
| `concept` | 개념·구조 설명 |
| `decision` | 무엇을 하기로/안 하기로 정했나. **결론과 이유가 있다** |
| `plan` | 무엇을 언제 하나. 순서·완료 기준 |
| `contract` | 지켜야 할 인터페이스·스키마 |
| `guide` | 어떻게 하나 (사용법) |
| `report` | **그 시점의 기록.** 날짜를 적어야 말이 된다 |
| `research` | 외부 조사·비교 |
| `policy` | 따라야 할 규칙 |
| `dataset` | 데이터가 무엇인가 |
| `evidence` | 재현 명령 + 실제 출력 + 판정 |
| `runbook` | 운영 절차 |
| `reference` | 원문·URL·목록 |

★**폴더 위치로 type 을 정하지 마라.** `program/research/` 아래 26건을 검증했더니
  24건이 `research` 가 아니었다. 실제로는 `report` 12 · `reference` 5 였다.

★**판정 기준 한 줄: 날짜를 적어야 말이 되면 `report` 다.**

### ③ 판정을 고른다

| 판정 | 언제 |
|---|---|
| **이관** | wiki 로 옮긴다 |
| **분할** | 여러 일을 한다. 나눠서 옮긴다 |
| **제외** | 옮기지 않는다 (완료된 작업 로그·폐기 기록·중간판) |
| **제자리** | 지금 위치가 맞다 (다른 문서가 그 경로를 참조한다) |
| **대조필요** | 이미 반영된 것 같은데 확인해야 한다 |

★**"제외" 로 찍기 전에 반드시 대조한다.** 지금까지 7번 대조에 7번 다 빠진 절이
  나왔다. "이미 반영됨" 은 세어 보기 전까지 믿을 수 없다.

★**"제자리" 를 놓치지 마라.** 루트 `CLAUDE.md` 나 다른 문서가 그 경로를 직접
  참조하면 옮길 때 링크가 깨진다. `grep` 으로 확인해라.

## 대상 24건

```
program/plan/A-COP_스프린트_에픽_설계.md
program/plan/A-COP_결제소유_경계.md
program/plan/A-COP_Composer_범위재검토.md
program/plan/A-COP_Composer_v3_불일치_해소안.md
program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md
program/plan/A-COP_Composer_소유권_정정.md
program/plan/A-COP_비전항목_검토.md
program/plan/A-COP_확장추천_검토.md
program/plan/A-COP_예제Team모듈_확충설계.md
program/plan/A-COP_남은작업_인수인계.md
program/research/_주말작업_요약_2026-08-29~30.md
program/research/_컴포저_UI배포구조_점검_2026-08-29.md
final_project_cs/docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md
final_project_cs/docs/plans/2026-08-12_1507_A-COP_실행계획서_v1.md
final_project_cs/docs/plans/2026-08-14_1546_A-COP_init_plan_6인팀_v1.md
final_project_cs/docs/plans/2026-08-17_코퍼스_25문서_배분안.md
final_project_cs/docs/release_checklist.md
final_project_cs/docs/handoff/09_Composer_GUI_계약.md
final_project_cs/docs/manuals/운영_unknown상태_대응절차.md
final_project_cs/docs/vision/TODO_VISION.md
program/plan/A-COP_문서구조_v1.md
program/plan/A-COP_문서표준_설계_codex초안.md
program/plan/A-COP_사업성_단위경제.md
program/plan/A-COP_페인포인트_페르소나_설계.md
```

★마지막 4건은 **이미 wiki 에 반영됐을 가능성이 높다.** 그래서 특히 대조가
  중요하다. `program/wiki/` 를 읽고 **절 단위로 세어라.**

## 출력 형식

TSV 한 장으로 낸다. 헤더 포함.

```
경로	type	판정	목표영역	근거
program/plan/A-COP_결제소유_경계.md	decision	이관	hub/decisions	결론과 이유가 명확. D-001 원형
```

- `목표영역` 은 `hub/decisions` · `hub/delivery` · `cs/teams` · `제자리` 처럼 적는다
- `근거` 는 한 문장. **왜 그 판정인지**를 적는다
- 분할이면 근거에 **무엇과 무엇으로 나뉘는지** 적는다

TSV 외에 다른 설명은 붙이지 마라.
