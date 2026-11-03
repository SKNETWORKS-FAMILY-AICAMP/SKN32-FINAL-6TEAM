---
type: report
title: 라이팅 1절 — 공통 응대 계약과 복합 문의 첫 slice
status: draft
domain: travel
---

# 라이팅 1절 결과

2026-10-24 22:29 KST. 변경 담당: 라이팅 1절 child. 통합·독립 검토: 부모(매니저) 인계 대기. 소비 기능 담당의 독립 승인·운영 반영 완료를 주장하지 않습니다.

## 결과·범위

[공통 계약 초안](../../external/travel-response.md)을 코드보다 먼저 작성했습니다. 결정론적 작성기가 실제 `trip_messages._run_decision → read_requests.reply` 복합 사실 문의의 문단·더보기를 작성하며, 질문마다 원래 요청·근거·확인시각·기준판·후속 대상을 보존합니다. 누락/중복/여분의 종결·공백 답·알 수 없는 상태는 실패로 드러냅니다. 미확인 질문은 `failed` 또는 `needs_input`으로 닫고 `completion=partial`을 기록합니다. 단순 미사용 stub은 아닙니다.

**완료 범위는 공통 계약+문의 첫 slice뿐입니다. 자율 라이팅 에이전트 전체 구현 완료가 아닙니다.** 조회·해석·실행은 기존 workflow 소유이며 새 LLM·도구·업무 엔진은 추가하지 않았습니다. 기존 외부 `status=answered`와 본문·더보기·focus는 호환 유지하고 `basis.response`만 추가했습니다.

| 로컬 확인 범위 | 결과 |
|---|---|
| 신규 단위 시험 | 8/8 = 100% |
| 관련 단위 회귀(신규 포함) | 105/105 = 100% |
| 수정 직전 백업 대비 본문·더보기·기존 근거·focus 정확 비교 | 18/18 = 100% |

전체 구현률·전체 suite·실모델 품질·실DB·운영 상태의 분모는 이 표에 포함하지 않습니다.

## 기존 호출·사본 비교와 변경 보존

- root/cs AGENTS·CLAUDE, cs RULE, 양쪽 wiki, 개발 역할, 기존 검토 및 독립 기준 6개를 확인했습니다. root RULE.md는 없습니다. 대상 코드·tests 상위 경로에 추가 AGENTS/CLAUDE/RULE은 없었습니다.
- 현재 C 사본과 `C:/_proj/파이널스페이스/final_project_cs`의 case_dispatch/read_requests/trip_messages를 직접 텍스트 대조했습니다. 후자에는 시간 기준 해석·고른 장소 보정·새 요청/대기 재개 분리·읽기 스냅샷 보정이 추가돼 있었습니다. 이를 현재 C에 임의 통째로 이식하거나 최신 사본을 덮지 않았습니다. 부모 기준선 통합이 남아 있습니다.
- 기존 공유 파일 변경은 read_requests의 결과 수집·최종 작성 자리와 trip_messages의 확인된 여행 scope 전달 한 호출에 한정했습니다. 최신 시간 기준/대상 보정 코드를 대체하는 패치가 아닙니다.
- case_dispatch의 실행 후 재조회, Controller, TeamResult, 승인 설정, 계획서·감시 파일은 변경하지 않았습니다. response_review를 켜거나 옛 커머스 경로를 연결하지 않았습니다.

## 변경 파일

cs 기준:

1. 신규 `wiki/external/travel-response.md`: 소유자·범위·의미·승인보존 및 미구현 경계.
2. 신규 `app/domains/travel_ops/components/response/writing.py`: 입력/질문/결과 계약, 실제 문단·더보기 작성, 종결 검증, 독립 스냅샷 복사.
3. 수정 `app/domains/travel_ops/components/conversation/read_requests.py`: 기존 조회 결과를 작성기에 전달, 질문별 상태와 공통 결과를 basis에 추가. 조회 분기는 유지.
4. 수정 `app/domains/travel_ops/components/conversation/trip_messages.py`: 위 실제 호출에 tenant 및 DB에서 읽은 customer/trip scope 전달. actor_id를 customer_id로 오인하지 않음.
5. 신규 `tests/unit/travel/test_travel_response_slice1.py`: 순수 작성·상태 보존·종결 검증·실제 복합 문의·실제 문의 reducer 연결 시험. DB/상태 전이/분류 경계는 격리 대역 사용.
6. 신규 본 보고서 및 [실행 증거 디렉터리](../evidence/2026-10-24_travel-writing-slice1/): 각 RED/GREEN 로그, 회귀, 호환 비교 JSON, 환경, 공유파일 한정 diff·해시.

기존 미커밋 변경을 덮지 않았으며, 수정 직전 사본은 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-backup/`에 있습니다. 원래 공유 파일 둘과 최초 신규 테스트/작성기 및 계약 갱신 직전 사본·manifest를 보존했습니다. root/cs index/log는 부모와 충돌을 피하려 수정하지 않았습니다.

## TDD와 실행 근거

[증거 폴더](../evidence/2026-10-24_travel-writing-slice1/):

- `red1.log`: 1 fail — 공통 작성기 부재를 실제 관측. `green1.log`: 1 pass.
- `red2.log`: 5 fail/1 pass — 질문 누락·중복·여분·공백·잘못된 종결을 거부하지 않음. `green2.log`: 6 pass.
- `red3.log`: 1 fail/6 pass — 실제 복합 읽기가 작성기를 호출하지 않음. 실제 연결 후 `green3.log`는 28 pass/1 fail: 기존 시험의 tiktoken 미설치로 실패한 환경 기록이며 GREEN 완료 증거로 쓰지 않습니다.
- `red4.log`: 1 fail/7 pass — 실제 문의 reducer에서 scope가 None으로 전달됨. 한 호출 연결 후 `green4.log`: 30 pass.
- `regression.log`: 105 pass, skip/실패 없음. 네트워크·DB 연결 차단 상태.
- `compatibility.json`: 기존 백업과 18개 입력의 본문·더보기·기존 basis·focus 정확 일치(새 response만 제외). 최초 비교 fixture의 booking_id 누락은 도구에서 AttributeError로 드러났고 fixture를 보완한 뒤 실제 18개 비교를 완료했습니다.
- `git diff --check` 대상 두 공유 파일: exit 0. trip_messages 줄바꿈은 Git의 LF→CRLF 경고가 있었으며 내용 오류는 없었습니다.

### 환경·재실행

기본 Python은 3.14.7 ARM64이며 pytest/pydantic 미설치였습니다. 실제 존재한 `C:/Users/kcxsz/.local/bin/python3.12.exe` 3.12.15로 현재 프로필 scratch의 `travel-writing-s1-venv`에 격리 환경을 만들었습니다. 프로젝트 requirements의 직접 사용 버전 pytest 8.4.2, pydantic 2.13.4 등 필요한 subset을 설치했습니다. 전체 requirements 설치·전체 앱 가동은 하지 않았습니다. 처음 회귀에서 openai, 이어 tiktoken import가 막혔고 해당 고정 의존성을 격리 venv에 추가해 해결했습니다. 설치된 SDK를 이용한 외부 LLM 호출은 없습니다.

실행 cwd는 `C:/_proj/final_workspace/final_project_cs`입니다. 실제 명령의 공통 prefix:

```
C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-run.py
```

뒤에 로그 경로와 아래 시험 파일을 지정했습니다(각 로그 첫 줄에 실제 전체 인자 보존).

```
wiki/records/evidence/2026-10-24_travel-writing-slice1/regression.log
tests/unit/travel/test_travel_response_slice1.py
tests/unit/travel/test_read_requests.py
tests/unit/travel/test_fact_context.py
tests/unit/travel/test_fact_read_recovery.py
tests/unit/travel/test_trip_facts_move.py
tests/unit/travel/test_decision_target_guard.py
```

runner는 pytest 전에 socket.connect/create_connection와 psycopg.connect를 실패 함수로 차단하고 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`를 사용했습니다. 루트 DB fixture를 실행하지 않았습니다. 환경은 `environment.txt`, 비교 probe는 scratch `travel-writing-s1-compat.py`입니다.

## 독립 기준 6개: 보존 범위와 다음 절

| 기준·소유 | 이번 확인 | 남은 한계 |
|---|---|---|
| 질문 완결 / 기존 해석기+작성기 | 해석된 reads 전부의 종결 추적·검증 | 원문에서 질문 추출 누락을 검출하는 새 모델/분석기는 없음 |
| 조회 책임 / 기존 read_requests·fact_context | 기존 조회 분기·도구 경계 유지, 근거/시각/누락 원값 보존 | 소스 최신성·실제 네트워크 조회는 이번에 시험하지 않음 |
| 실행 확인 / 기존 workflow | 첫 slice는 read_only로 명시 | 저장/unknown/timeout/업체 거래 결과 연결·문장 claim 검사 미구현 |
| 상태 불변 / 기존 Controller·TeamResult | TeamResult 경로 무변경. 공통 workflow 스냅샷의 제안/승인/스키마/token 깊은 복사 보존 unit 검증 | 실행 변경 응답을 새 작성기에 연결한 증거는 없음 |
| 안내 비용 / 기존 문구틀 | 새 LLM·Case 생성 없음, 감시·정기안내 무변경 | 계획서·감시 공통 계약 연결은 다음 절 |
| 후속 연결 / 기존 focus | 실제 대상·판·시각 focus 복사 보존 | 알림 원인 이력·권한 재확인·오래된 선택·순서 역전·중복 처리는 새 구현하지 않음 |

writer는 임의 자연어의 참/거짓을 판정하지 않으며, 입력 evidence와 문장의 의미 일치를 완전 검증하지 않습니다. 기존 helper 직접 호출은 scope=None을 명시적으로 결과에 보존합니다. 실제 문의 입구는 DB의 scope를 전달하지만 인증 체계 자체를 새로 시험한 것은 아닙니다. 후속 source 연결 전 계약 소비자 검토가 필요합니다.

앱/서비스 실행·재시작, DB 변경, 외부 LLM, 운영 배포, 커밋·푸시는 하지 않았습니다. 전체 contract/security/suite 관문은 이번 승인된 격리 unit 범위가 아니므로 실행하지 않았습니다.
