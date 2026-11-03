---
type: report
title: 기상 독립검토 P2 두 결함 최소 수정
status: draft
domain: travel
---

# 기상 P2 경계 수정 — 로컬 격리 검증

2026-10-24 23:36 KST. 실제 저장소는 `C:/_proj/final_workspace/final_project_cs`입니다. 요청의 `.../cs`는 존재하지 않아 discovery로 위치를 확인했습니다. 변경 담당은 기상 P2 child이며 독립 검토·최종 결합 재검증은 부모 담당입니다.

## 결과

| 범위 | 실제 결과 |
|---|---|
| 기존 지정 302 고유 node id | 302/302 = 100% 포함·통과 |
| 신규 P2 시험 | 33/33 = 100% 통과 |
| 최종 22파일 결합 실행 | 335/335 = 100%, exit 0, 실패·오류·skip 없음 |

기존 로그에서 `tests/` 접두 인자를 추출하고 원래 302 node id 전부가 최종 결과에 있는지 검산했습니다. 실행 직전/직후 travel 소스 및 지정 시험 해시 변화는 0개였습니다. 최종 `335 passed in 3.30s`; pytest warning은 없고 `git diff --check` exit 0이며 Git LF/CRLF 안내만 있습니다.

## 최소 수정

1. `app/domains/travel_ops/entry/trip_api.py`: agent `message` 안에 기존 tenant-scoped `_trip_or_404`를 인자 평가보다 먼저 실행하는 두 줄만 추가했습니다. 없는 여행·타 tenant는 provider factory 생성 없이 404입니다. 정상 허용의 router lazy factory 1회 재사용·완료 중복의 forecast 1회 수명을 검증했습니다.
2. `app/domains/travel_ops/ports/data_sources/open_meteo.py`: `hourly.time`의 문자열 list와 제공된 시간별 필드의 list/동일 길이를 검사합니다. malformed는 `malformed_hourly` miss·경고와 기존 `None`으로 정규화합니다. 선택 필드 누락의 `None`, 0 강수, 빈 hourly의 기존 실패는 유지합니다.
3. [weather-wiring 계약](../../external/weather-wiring.md): 코드 수정 전에 문제와 실패 reason·기존 fallback 보존 계약을 보완했습니다.
4. `tests/unit/travel/test_weather_p2_boundaries.py` 신규 33개 시험입니다.

`weather_chain.py`는 백업과 바이트 동일합니다. 새 broad catch·재시도·무음 fallback은 없습니다. 실제 Chain의 성공가능 2차 호출 1회, 사용 `source`·`confirmed_at`·`fell_back_from` 및 1차 miss/log 보존을 검증했습니다. 두 adapter 실패를 실제 `handle_trip_message` 읽기 경로로 전달하면 기존 `weather_sources_failed`, writer partial/failed이며 기존 `all_failed`가 기록됩니다. 프로그래밍 RuntimeError는 삼키지 않습니다. 기존 예산/cache·TTL 회귀도 포함됩니다.

## RED → GREEN 증거

[고유 evidence](../evidence/2026-10-24_weather-p2/):

- `red-actual-repros.log`: 4 failed, exit 1. 없는 여행·타 tenant·정상 수명에서 factory가 ownership보다 먼저 관찰되고, 실제 OpenMeteo→Chain에서 time dict가 AttributeError를 일으켰습니다. HTTP 호출 재현이 아닙니다.
- `green-actual-repros.log`: 두 최소 수정 뒤 4 passed, exit 0.
- `red-listshape.log`: 필드 list 모양/길이 16 failed, 나머지 17 passed, exit 1. 기존 adapter가 malformed 값을 성공으로 반환해 2차가 호출되지 않는 기능 RED입니다.
- `green-listshape.log`: shape 경계 보강 뒤 33 passed, exit 0.
- `regression-302-plus-new.log`: 최초 결합 335 passed, exit 0.
- `regression-final-335.log`: 최종 결합 335 passed, exit 0.
- `results.json`: 정확한 명령·22파일 목록·고유 수·누락 없음·실행 전후 해시.
- `isolated-runner.py`, `replay.py`: 실제 runner와 manifest 검산 코드.
- `scoped.diff`, `scope-check.json`: 시작 백업 대비 차이와 병렬 소유 구분.

실행은 기존 Python 3.12.15/pytest 8.4.2 scratch venv와 기존 isolation runner를 재사용했습니다. `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`; socket connect/connect_ex/create_connection·psycopg.connect 차단, 정확한 stdlib Windows socketpair만 허용합니다. 실제 앱 loopback 차단과 socketpair를 사전 검증합니다. DB fixture를 로드하는 root conftest는 실행하지 않습니다.

재실행(cwd cs):

```text
python C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/weather-p2/replay.py
```

원래 dirty 백업과 SHA256 manifest는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/weather-p2/backup/` 및 상위 `backup-manifest.json`입니다.

## 병렬 변경·검사 시도

최종 실행 후 AST 범위 검사에서 `message` 외에 sibling 소유 `web_notices` 변경도 시작 백업 대비 감지됐습니다. 첫 검사의 `changed == ['message']` 단정은 AssertionError로 종료됐습니다(시험 실패가 아닌 scope 검사 실패). 이를 숨기지 않고 `scope-check.json`에 분리했습니다. 이 child는 notices를 수정·되돌리지 않았으며 `_web_view`·intake·confirm·trip_messages·conversation·root wiki/index/handoff도 수정하지 않았습니다. `scoped.diff`에는 시작 이후 다른 child hunk가 포함될 수 있으므로 전체를 이 child 변경으로 적용하면 안 됩니다. 실제 own API 수정은 agent message 두 줄입니다.

## 미완료·부모 인계

외부 HTTP·모델·실 DB·ASGI 인증 전체·브라우저·전체 contract/security·운영 배포는 검증하지 않았습니다. 외부 연결, 앱/서비스 기동, 배포, 커밋·푸시는 하지 않았습니다. 합성 저장소의 tenant 접근 거절 시험이며 실 DB tenant SQL 검증 완료가 아닙니다. 기존 별도 DB 의존 확대 5건 오류를 이번 성공 분모에 넣지 않았고 해결로 주장하지 않습니다.

부모는 최신 sibling 변경이 모인 트리를 독립 재실행하고 root/cs index·log·handoff에 이 보고서를 연결해 주십시오. 본 보고서의 성공은 승인된 로컬 P2 수정·격리 시험 범위에 한정합니다.
