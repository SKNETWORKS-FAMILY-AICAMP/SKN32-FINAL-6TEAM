# A-COP 루트 작업 기준

아래 표는 여러 문서에 반복되는 현재 기준 사실이다.

| 사실 | 현재 값 | 정본 | 확인일 |
|---|---|---|---|
| 문서 기준선 | v8 (v7·v7.1은 보존본, `program/plan/archive/`) | `program/plan/A-COP_구현계획서_v8.md` §0 | 2026-08-17 |
| Team 목록 — CS Pack 확정(10주 착수) | VOC & Store Manager, Response Generation & Review | `program/plan/A-COP_구현계획서_v8.md` §8-B, §16 | 2026-08-17 |
| Team 목록 — 검증 쇼핑몰 연계(일정 따라 조정) | Procurement + Order & Payment, Fulfillment & Logistics, Return & Refund(Mock), Catalog & Verification(A2A Remote) | 동 | 2026-08-17 |
| DoD 항목 수 | 1~29 (1~28은 v5/v7 번호 보존, 29는 Response Generation & Review 검증 신규) | `program/plan/A-COP_구현계획서_v8.md` §27 | 2026-08-17 |
| Docker·AWS | Phase 2 (로컬 개발 환경엔 Docker 없음, 실제 배포 단계에서 컨테이너화) | `program/plan/A-COP_구현계획서_v8.md` §12, §28 | 2026-08-17 |
| 프로젝트 일정 구조 | 선행 2026-08-17~08-27(11일) + 공식 1W~9W, 중간발표 09-15, 최종발표 10-26 | `program/research/_WBS원본_2026-08-17.md` | 2026-08-17 |

이 표가 오래됐으면 [`program/research/index.md`](program/research/index.md)가 정본이다. `index.md`가 갱신되면 이 파일의 표도 함께 갱신한다.

세 코드 프로젝트 중 실제 작업 중인 폴더가 있으면 그 폴더의 `CLAUDE.md`가 이 파일보다 우선한다. 도메인 규칙과 프로젝트별 작업 경계는 각 폴더에 있다.

릴리스 대상은 [`final_project_cs/`](final_project_cs/)다. [`final_project_sample/`](final_project_sample/)은 Core/Team 계약과 Composer 쓰기채널 인프라를 먼저 검증하는 참고 구현체이며, sample에서 먼저 만든 Composer 쓰기채널을 cs로 이식하는 관계다. 따라서 sample의 예시 Team과 검증 상태를 cs의 릴리스 완료로 간주하지 않는다.

문서 병합 때는 [`program/research/_prompts/문서병합_지침.md`](program/research/_prompts/문서병합_지침.md)의 보완·중복·모순 분류 절차를 따른다. `program/research/index.md`의 [`문서 정합성 점검 캘린더`](program/research/index.md#문서-정합성-점검-캘린더)에서는 `§숫자` 참조, Team 목록, DoD 항목 수를 기준선과 대조한다.

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
