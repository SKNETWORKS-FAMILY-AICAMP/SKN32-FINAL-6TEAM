# A-COP 루트 작업 기준

아래 표는 여러 문서에 반복되는 현재 기준 사실이다.

| 사실 | 현재 값 | 정본 | 확인일 |
|---|---|---|---|
| 문서 기준선 | **v10** (v8 이하는 보존본 `program/plan/archive/`. **v9 는 아직 `program/plan/` 에 그대로 있다** — 옮길지 안 정해졌다). 계획서 = 범위·결정·일정, 세부 설계·운영 사실 = wiki | `program/plan/A-COP_구현계획서_v10.md` §0 | 2026-09-08 |
| **도메인** | **여행 CS** — 2026-09-08 팀 결정으로 커머스 CS 에서 교체. 코어 계약·생명주기·동시성·감사·평가 도구는 승계, Team 모듈과 도메인 데이터는 전량 신규 | `program/plan/A-COP_구현계획서_v10.md` §0 | 2026-09-08 |
| Team 목록 — v10 §5 | Activity · Dining · Mobility · **Booking Handoff** · Lodging/Flight(등록만). MVP 필수는 **Activity·Booking Handoff** 둘 | `program/plan/A-COP_구현계획서_v10.md` §5 | 2026-09-08 |
| 계획 생성 소유 | **우리 일이 아니다.** 외부 에이전트·LLM 이 만든 일정을 받아 검증하고 여행 종료까지 지켜본다 | 동 §4-A | 2026-09-08 |
| 인라인 분류 소유 | 코어 1 (진입·분류 층). **라벨이 교체됐다** — 일정 제출 / 사건 신고 / 확인 요청 / 조정 거부 / 그 외 | 동 §5-A | 2026-09-08 |
| DoD 항목 수 | **22** (v10 §12, 자동 17 · 아키텍처 테스트 3 · 측정 2). v9 의 29항목은 **쇼핑몰 대상**이라 그대로 쓰지 않는다 | 동 §12 | 2026-09-08 |
| 승계하는 코어 규칙 | 낙관적 동시성 · Idempotency · 이벤트 순서 · **`outbox UNIQUE(tenant_id, topic, dedupe_key)`** · Team 은 side effect 를 실행하지 않는다 · Core 는 도메인 어휘를 모른다 · 근거 없는 문장 금지 | 동 §6 | 2026-09-08 |
| Composer 소재 | **승계.** 소재를 영어 통지 문구 + 운영자용 한국어로 교체 | 동 §0-2, §5-A | 2026-09-08 |
| 프로젝트 일정 | 최종발표 **2026-10-26** 까지 **7주**(09-08 기준). MVP 는 구현 단계 1(계획과 검증)까지 | 동 §0, §9 | 2026-09-08 |
| `[미확보]` v10 이 말하지 않는 것 | **`A2A`·`MCP`·`Docker`·`AWS` 문자열이 v10 에 0회다.** v9 §3-A 의 부트캠프 요구사항 대응표도 없다. 빠진 것인지 뺀 것인지 안 정해졌다 | `program/plan/A-COP_여행Team모듈_구성안.md` §0 | 2026-09-08 |

★`[2026-09-08 판올림]` 이 표는 09-07 까지 **v9 쇼핑몰** 기준이었다. 도메인이 여행으로
바뀌었는데 **매 세션 자동으로 실리는 이 표만 안 바뀌어**, 모든 세션이 틀린 사실로 시작하고
있었다. v9 기준 표가 필요하면 `program/plan/A-COP_구현계획서_v9.md` §0 을 본다 — **v9 는 archive 가 아니라 `program/plan/` 에 있다.** archive 는 v5~v8 이고 2026-09-09 에 압축했다(`program/plan/archive/README.md`).

이 표가 오래됐으면 [`program/research/index.md`](program/research/index.md)의 「현재 기준 사실」 표가 정본이다. 둘은 같이 갱신한다. 세부 설계·운영 사실은 [`wiki/index.md`](wiki/index.md)와 각 저장소의 `wiki/`가 정본이다(2026-09-07 전환 완료). **읽는 순서는 wiki 먼저다.** 작업 기록(evidence·리포트)은 각 저장소의 `wiki/records/`에 있다(2026-09-08 `docs/`를 통합) — wiki가 인용한 근거를 확인할 때 연다. 두 곳이 다르면 wiki를 고치거나, 기록이 낡았다는 주석을 붙인다 — 기록 자체는 고치지 않는다.

세 코드 프로젝트 중 실제 작업 중인 폴더가 있으면 그 폴더의 `CLAUDE.md`가 이 파일보다 우선한다. 도메인 규칙과 프로젝트별 작업 경계는 각 폴더에 있다.

릴리스 대상은 [`final_project_cs/`](final_project_cs/)다. [`final_project_sample/`](final_project_sample/)은 Core/Team 계약과 Composer 쓰기채널 인프라를 먼저 검증하는 참고 구현체이며, sample에서 먼저 만든 Composer 쓰기채널을 cs로 이식하는 관계다. 따라서 sample의 예시 Team과 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.

문서 병합 때는 [`program/research/_prompts/문서병합_지침.md`](program/research/_prompts/문서병합_지침.md)의 보완·중복·모순 분류 절차를 따른다. `program/research/index.md`의 [`문서 정합성 점검 캘린더`](program/research/index.md#문서-정합성-점검-캘린더)에서는 `§숫자` 참조, Team 목록, DoD 항목 수를 기준선과 대조한다.

## 작업 지시 약어

★**이 표는 폴더별 `CLAUDE.md`·`RULE.md`보다 앞선다.** 세 코드 프로젝트 어디서
작업하든 같은 뜻으로 읽는다.

| 사용자가 친 것 | 뜻 |
|---|---|
| `ㄱㄱ` · `ㄱ` · `rr` | **계속 진행해.** 직전에 정리한 남은 작업을 이어서 한다. 무엇을 할지 되묻지 않는다 |

`rr` 은 `ㄱㄱ`을 영문 자판에서 친 것이다(ㄱ = r). 같은 기능이다.

## 보고 형식

★**이 표도 폴더별 `CLAUDE.md`·`RULE.md`보다 앞선다.**

| 규칙 | |
|---|---|
| **남은 작업·상태를 보고할 때는 `%`를 함께 적는다** | "26 통과"가 아니라 "26/29 = **90%**". 분자·분모를 같이 적어 어디서 나온 수인지 보이게 한다 |
| 분모가 없으면 `%`를 만들지 않는다 | 모르는 것을 비율로 적으면 지어낸 수가 된다. 그때는 "분모 모름"이라 적는다 |
| `%`는 **세어서** 낸다 | 문서가 아니라 디스크·DB·테스트 실행 결과를 센다(§5 상태표 규칙과 같다) |

2026-09-07 사용자 지시로 신설. 그전까지 어디에도 적혀 있지 않아 세션마다 빠졌다.

## 학습 도장 (acop_dojo)

[`acop_dojo/`](acop_dojo/)는 `final_project_cs` 의 구조와 동작을 실행 증거로 배우는
학습 프로그램이다. 정답은 pytest 와 실측 실행 트레이스가 판정한다.
원본 저장소는 건드리지 않고 임시 사본에서만 결함을 적용한다.

결함 카탈로그의 등록 게이트가 부산물로 **테스트 사각지대**를 찾아낸다.
불변식을 어겼는데 테스트가 울지 않는 지점의 목록은
[`program/research/테스트_사각지대_실측.md`](program/research/테스트_사각지대_실측.md)에 있고,
루트에서 `python dojo.py report` 로 다시 생성한다. 손으로 고치지 않는다.

## 데이터 폴더

실제 데이터 파일은 [`datasets/`](datasets/)에 둔다. [`program/research/`](program/research/)는 조사 문서를 두는 곳이고, 데이터 파일 자체는 여기가 아니다.

폴더 규칙과 각 데이터셋의 상태는 [`datasets/README.md`](datasets/README.md)가 정본이다. 새 데이터셋을 만들기 전에 먼저 읽는다.

| 데이터셋 | 무엇인가 | A-COP에서 쓰는 곳 |
|---|---|---|
| [`commerce/coupang_order_history`](datasets/commerce/coupang_order_history/) | 쿠팡 주문·배송 기록 | Core 1 Context Broker의 주문 정보 |
| [`commerce/naver_order_history`](datasets/commerce/naver_order_history/) | 네이버 주문 기록 | 동. 쇼핑몰 두 곳으로 구조 편향을 막는다 |
| [`commerce/courier_tracking`](datasets/commerce/courier_tracking/) | 택배 배송 이력 조회 도구 | Core 2의 배송조회 Action 실행부 |
| [`voc/*`](datasets/voc/) | 고객 문의·응대 공개 데이터 | Core 1의 RAG 지식 재료 |
| [`mt/*`](datasets/mt/) | 번역 성능 비교 | 다국어 응대 검토용 |

`raw/`와 `processed/`는 본인의 실제 구매 기록을 담고 있어 git에 올리지 않는다. 스크립트와 스키마와 `REPORT.md`만 올린다.

각 데이터셋 폴더의 `REPORT.md`가 그 데이터가 무엇이고 어디에 쓰이는지 설명한다. 데이터 관련 작업 전에 해당 `REPORT.md`를 읽는다.

## TeamFlow (이슈 트래커)

스프린트와 에픽은 TeamFlow(https://jira-for-me.vercel.app)의 `SKN32_FINAL_TEAM4` 프로젝트에서 관리한다.
프로젝트 이름은 TEAM4지만 **우리 팀은 6팀이다.** 부트캠프 조직 저장소가
[`SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM`](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM)인 것으로
2026-08-31에 확인했다. TeamFlow 쪽 이름이 잘못 붙은 것이며 프로젝트 id 84는 그대로 쓴다.
API 주소와 토큰과 사용법은 [`.env.teamflow`](.env.teamflow)에 있다. 이 파일은 커밋하지 않으므로
형식은 [`.env.teamflow.example`](.env.teamflow.example)을 본다.

토큰으로는 이슈 생성만 된다. 조회와 수정과 스프린트 생성은 화면에서 사람이 한다.
등록할 스프린트와 에픽의 정본은 [`program/plan/A-COP_스프린트_에픽_설계.md`](program/plan/A-COP_스프린트_에픽_설계.md)다.
