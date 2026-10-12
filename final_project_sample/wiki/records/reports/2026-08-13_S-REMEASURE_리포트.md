# 2026-08-13 DoD 재측정 수집 리포트

## 수집 파일

- `wiki/records/evidence/_raw/DoD-04_v2.md`
- `wiki/records/evidence/_raw/DoD-05_v2.md`
- `wiki/records/evidence/_raw/DoD-07_v2.md`
- `wiki/records/evidence/_raw/DoD-09_v2.md`
- `wiki/records/evidence/_raw/DoD-10_v2.md`

각 파일에 실행 명령, 실제 출력, 숫자·행·키·파일경로 등의 관측 사실을 기록했다. 판정 문서는 생성하거나 수정하지 않았다.

## 완료 조건 명령 출력

작성 후 파일 수를 확인하는 명령을 실행했다.

```powershell
Get-ChildItem docs\evidence\_raw\*_v2.md | Measure-Object
```

실제 출력:

```text
Count    : 5
Average  : 
Sum      : 
Maximum  : 
Minimum  : 
Property : 
```

전체 테스트 명령:

```powershell
python -m pytest tests -q
```

실제 출력 집계:

```text
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[...]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[...]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
… traceback 및 warning 상세 800줄 생략
3 failed, 120 passed, 2 warnings in 22.44s
```

실패 traceback에는 `api.openai.com:443`, `WinError 10013`, `openai.APIConnectionError: Connection error.`가 포함되어 있었다. RAG 테스트의 외부 embedding 실호출은 fake 주입 없이 실행되었다.

```powershell
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"; & $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

```text
tenants=1
```

## 돌리지 못한 명령과 이유

- `python -m pytest tests -q`의 123개 전체 집계는 확인하지 못했다. RAG 통합 테스트 3건이 외부 OpenAI embedding 연결 차단으로 실패했으며, 외부 embedding을 임의 결과로 대체하지 않았다.
- 실데이터가 있는 날짜의 daily feedback 급증 alert는 해당 날짜의 `demo` 데이터가 없어 확인하지 못했다. 실행한 날짜의 출력은 DoD-10 원문에 기록했다.
