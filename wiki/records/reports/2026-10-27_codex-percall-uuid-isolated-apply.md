---
type: report
title: codex_percall 동시 호출 파일명 겹침 수정(uuid) — 팀 role-manager 93c7ba8e 격리 사본 최소 반영
status: draft
domain: travel
---

# codex_percall uuid 수정 격리 반영 (2026-10-27)

[재분류 보고](2026-10-27_finalspace-unmerged-conflicts-reclassification.md) 「안전한 다음 통합 단위 1」을 실행했다. 원본 작업트리·인덱스·브랜치는 수정하지 않았고 커밋·push 0건이다(push 는 부모 세션 몫).

## 결론

- 팀 role-manager 최신을 다시 확인했다: `git ls-remote` team·origin 모두 `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b`(exit 0) — 재분류 때 pin 과 같다.
- 백업 판 전체를 덮지 않고 **uuid 부분 2곳만** 이식했다: `import uuid` 1줄, `uid = f'{os.getpid()}_{time.time_ns()}'` → 설명 주석 2줄 + `uid = uuid.uuid4().hex`. 결과는 백업 판(sha256 `f701e6adf55f…`)과 LF 정규화 내용이 같고, pin 의 CRLF 줄 끝을 유지했다(74/74 줄 CRLF).
- 원본 작업트리의 미추적 시험 `program/scripts/eval_kit/test_codex_percall.py`(sha256 `8ee738a1e410…`, blob `95620dc6`)를 그대로 넣었다.
- 시험: RED 1/1 실패(수정 전 pin) → GREEN 1/1 = 100%(수정 후), 반복 5/5 = 100%, eval_kit 회귀 15/15 = 100%.

## 실행 결과

| 단계 | 대상 | 결과 |
|---|---|---|
| RED | pin 판 `codex_percall.py` + 시험 | 1 failed, exit 1 — `0번 호출이 다른 문제의 프롬프트로 답했다: 문제 #4#` (같은 눈금 time_ns 로 12 스레드가 같은 파일명을 써 프롬프트가 섞임. 대역·수집 오류 아님) |
| GREEN | uuid 판 | 1 passed, exit 0 |
| 반복 | 같은 시험 5회 | 5/5 exit 0 |
| 회귀 | `program/scripts/eval_kit` 전체(test_stats 14 + test_codex_percall 1) | 15/15 passed, exit 0 |

실행기: Hermes scratch `date_risk_env_312` (Python 3.12.15, pytest 8.4.2, 읽기만 사용·설치 없음). 옵션 `-p no:cacheprovider -o addopts= --confcutdir=program/scripts/eval_kit`, `PYTHONDONTWRITEBYTECODE=1`. 실제 Codex CLI·모델·네트워크 호출 없음(시험이 `subprocess.run` 을 대역으로 바꿈).

## 검토

- 호출부 9곳(`plan_qa_bench/*`, `rag_gate/rag_improve/codex_rerank_run.py`, `final_project_cs/eval/intake_diverse/run_agent_proto.py`)은 `call(...)`·`CodexChat` 서명만 쓰고 임시 파일 이름 형식(`pid_time`)에 기대는 코드가 없다(`git grep` 확인). 서명·반환값 변화 없음.
- 보안: `uuid4` 는 OS 난수 기반, 이름은 같은 work 폴더 안 임시 파일에만 쓰인다. 셸 호출 없음(`subprocess.run` 목록 인자, `-s read-only` 유지). 두 파일에 비밀값 키워드 0건.
- 충돌: 다른 파일과 겹치지 않는다. 원본 작업트리의 `codex_percall.py` 는 pin 과 같은 blob(`39f18f9a`)이라 원본에 적용해도 덮어쓸 로컬 변경이 없다. 시험 파일은 원본 미추적 파일과 같은 blob.
- `git diff --cached --check` exit 0(공백 경고 없음). 깨끗한 pin 트리에 별도 인덱스로 `git apply --cached --check` exit 0, 적용 결과 tree `174497d5e4508f8555693bcfb2c31da4cd4874ca` = 격리 사본 tree.

## 산출물 (Hermes scratch `codex-percall-uuid-20261027/`, 24시간 미사용 시 정리될 수 있음)

| 파일 | 내용 |
|---|---|
| `codex_percall_uuid.patch` | `git diff --cached --binary`, sha256 `4faa633eec938aa794599989b12d712c799eedcb9e62a285be97a410f7070191`, 2 files / +55 −1 |
| 결과 blob | `codex_percall.py` `1d3d53c6aff7b7f9341c5ef73b7e6bc11c9235ad` · `test_codex_percall.py` `95620dc6d14d38b9ce8c5f1104aeb475a95cba58` |
| `evidence/` | `red.log`·`red.exit`, `green.log`·`green.exit`, `green_repeat.*`, `regress_evalkit.log`·`regress.exit`, `diffcheck.out`, `codex_percall.pin.py` |
| `repo/` | pin `93c7ba8e` sparse 격리 clone(`program/scripts/eval_kit` 만 의미 있음). 반영은 인덱스에 stage 만, 커밋 없음 |

## 원본 보존

원본 `C:/_proj/final_workspace` HEAD `efeb873a…`, `git status --porcelain` 1,158줄, `codex_percall.py` sha256 `a71bf1ba…`·시험 sha256 `8ee738a1…` — 작업 전후 같다(이 보고서·인계 2파일을 쓴 뒤 status 는 미추적 2줄이 늘어 1,160줄). 원본 `.git` 에 fetch·쓰기 없음(격리 clone 은 scratch `iso.git` 를 `--shared` 로 읽음).

## 남은 일

1. 부모: 팀·개인 role-manager 에 이 patch 를 커밋·push(규칙상 두 원격 함께, 각 해시 보고). push 직전 원격 끝이 `93c7ba8e` 에서 움직였으면 apply-check 를 다시 한다.
2. 원본 작업트리는 HEAD 가 pin 보다 1,062 커밋 뒤라 이번 patch 를 원본에 따로 적용하지 않았다. 원본 통합 때 함께 처리.
3. 한계: 단위 시험(대역)만 실행. 실제 Codex CLI 병렬 평가 재실행은 하지 않았다.
