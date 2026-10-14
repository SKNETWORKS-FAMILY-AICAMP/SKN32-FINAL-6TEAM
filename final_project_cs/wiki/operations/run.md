---
type: guide
title: 현재 여행 코드 실행·검증
description: cs 프로젝트 폴더에서 앱·작업자·시험을 실행하는 명령 모음
status: draft
domain: travel
---

# 현재 여행 코드 실행·검증

아래 명령은 **cs 프로젝트 폴더**에서 실행합니다. 필요한 로컬 개발 DB·환경 설정은 [로컬 개발 안내](local-setup.md)를 먼저 확인합니다. 실행 명령의 존재와 실제 통과·배포 상태를 구분합니다.

## 회귀 시험

```powershell
python -m pytest tests/architecture tests/contract tests/security -q
python -m pytest tests/e2e/test_mcp_server.py tests/e2e/test_mcp_read_tools.py -q
python -m pytest tests/integration/db/test_migrations_rerun.py -q
```

DB·외부 서비스가 필요한 시험은 전제 조건을 확인합니다. 건너뜀은 통과가 아닙니다. 전체 제품 시험이 필요하면 `python -m pytest -q`를 실행하고 live 시험 포함 여부를 기록합니다.

## 여행 자료·관문

```powershell
python -m scripts.check_corpus
python -m pytest tests/unit/eval/test_travel_classification_eval.py tests/integration/rag/test_travel_corpus_retrieval.py -q
python -m scripts.verify_dod_v11
```

여행 분류 재생은 [현재 replay 구현](../../eval/travel_classification/replay.py)을 사용합니다. 실제 모델 호출·비용이 발생하므로 데이터·반복·출력 위치를 정한 뒤 실행합니다. 과거 `eval.runners.proposed`·`golden.jsonl`·`seed_demo_cases`는 현재 실행 안내에서 사용하지 않습니다.

## SQL·지속 실행

SQL 입력·역사 보존·보류 파일은 [SQL 적용 안내](../data/migrations.md)가 소유합니다. 문서 정리로 기존 DB를 삭제하거나 적용 완료로 표시하지 않습니다. 장기 실행의 프로세스·환경별 상태는 [지속 운영 안내](always-on.md)에서 확인합니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--operations--run.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="실행"></a>
<a id="테스트"></a>
<a id="dod-검증"></a>
<a id="코퍼스-게이트"></a>
<a id="평가"></a>
<a id="시연-데이터"></a>
<a id="개발-서버"></a>
<a id="멈춘-case-되잡기"></a>
<a id="-백엔드-통과만으로-완료라고-하지-않는다"></a>
<a id="관계"></a>
