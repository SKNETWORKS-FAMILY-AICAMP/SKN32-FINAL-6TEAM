# A-COP 공유 문서 관리 표준

문서 상태: 초안 0.1  
작성 기준일: 2026-08-31  
적용 대상: `program`, `final_project_cs`, `final_project_sample`, `acop_dojo`, `datasets`, `gPUteer`  
기준 규격: OKF v0.2, LangChain OpenWiki

## 0. 결정 요약

| 항목 | 결정 |
|---|---|
| 저장 모델 | 중앙 허브와 저장소별 로컬 wiki를 함께 쓰는 혼합형 |
| 중앙 허브 | `program/wiki/` |
| 로컬 wiki | 각 저장소 루트의 `wiki/` |
| 문서 단위 | 한 파일이 아니라 한 개념 |
| 저장소 내부 링크 | OKF 번들 절대경로 또는 상대경로 |
| 저장소 간 링크 | 영속 식별자 `acop://<repo>/<concept-id>` |
| 파일명 | 영어 소문자 kebab-case |
| 제목·본문 | 한국어 |
| 태그 | 통제된 영어 소문자 kebab-case |
| OKF 필수 필드 | `type` 하나 |
| 변경 이력 | 번들 루트와 주요 영역의 `log.md` |
| OpenWiki CLI | 최종 프로젝트 기간에는 공식 생성·갱신 도구로 채택하지 않음 |
| 이관 대상 추정 | 원본 약 311개, 합리적 범위 250~380개 |
| 1,466줄 계획서 | 17개 개념 문서로 분할하는 것을 1차 추정치로 사용 |

이 설계에서 저장 위치, 링크 방식, OKF 호환 규칙, 정본 우선순위는 확정할 수 있다. `type` 경계와 세부 하위 폴더는 실제 문서 표본을 대입한 뒤 한 번 교정해야 한다.

---

## 1. 저장 위치와 경계

### 1.1 저장 모델

혼합형으로 결정한다.

- 프로젝트 전체의 계획·결정·조사·평가 기준은 `program/wiki/`에 둔다.
- 코드·스키마·데이터·배포 설정과 같은 커밋에서 바뀌어야 하는 문서는 해당 저장소의 `wiki/`에 둔다.
- 각 저장소의 `wiki/`는 독립적인 OKF 번들이다.
- `program/wiki/`는 여섯 번들의 탐색 허브이지만 로컬 문서를 복제하지 않는다.

`program`의 기존 폴더 이름은 새 분류의 근거로 사용하지 않는다. `program/plan`, `research`, `briefing`을 정리해서 재사용하는 것이 아니라 새 경계인 `program/wiki/`를 만든다.

### 1.2 중앙과 로컬을 가르는 기준

문서의 주제보다 변경 원자성으로 판정한다.

| 질문 | 예 | 배치 |
|---|---|---|
| 문서를 틀리게 만드는 직접 원인이 한 저장소의 코드·스키마·설정 변경인가 | API 계약, 배포 절차, 모듈 경계 | 해당 저장소 |
| 코드와 문서를 같은 PR에서 리뷰해야 하는가 | `final_project_cs`의 계층 불변식 | 해당 저장소 |
| 둘 이상의 저장소가 동등한 당사자인가 | sample에서 검증한 계약을 cs로 이식하는 결정 | 중앙 |
| 특정 코드 커밋에 귀속되지 않는가 | 포지셔닝, 공통 일정, 평가 설계 | 중앙 |
| 특정 데이터셋과 함께 변해야 하는가 | 스키마, 품질 검사, 생성 REPORT | `datasets` |
| 개인적인 메모인가 | 개인 TODO, 정리 전 생각 | 공유 wiki에 넣지 않음 |

경계가 애매하면 다음 순서로 결정한다.

1. 문서를 틀리게 만드는 변경이 어느 저장소에서 발생하는지 찾는다.
2. 그 변경과 같은 PR로 고칠 수 있으면 해당 저장소에 둔다.
3. 원인이 둘 이상이면 중앙에 둔다.
4. 중앙 문서는 관계와 이유만 설명하고 로컬 세부사항은 링크한다.

### 1.3 정본 우선순위

사실이 충돌할 때 다음 순서로 판정한다.

1. 실행 가능한 계약과 테스트 결과
2. 해당 사실을 소유한 저장소의 `CLAUDE.md` 사실 표
3. 해당 저장소의 사람 검증된 `status: stable` 문서
4. 중앙 `program/wiki/`의 통합 문서
5. `status: draft` 문서
6. 보존된 과거 문서

하위 폴더 `CLAUDE.md`가 상위보다 우선하는 규칙은 유지한다. 단, 우선권은 그 하위 폴더의 범위 안에서만 성립한다.

OpenWiki의 Knowledge Router 원칙과 기존 `CLAUDE.md` 사실 표 사이에는 긴장이 있다. 다음과 같이 제한적으로 결합한다.

- `CLAUDE.md`는 기본적으로 읽기 순서와 wiki 위치를 알려주는 라우터이다.
- “사실 / 현재 값 / 정본 / 확인일” 4열 표는 검증된 관행이므로 유지한다.
- 이 표 외의 설명 지식은 `CLAUDE.md`에 넣지 않는다.
- 하나의 사실은 한 저장소의 한 표만 소유한다.
- 다른 저장소는 값을 복사하지 않고 소유 표의 URL이나 `acop://` ID를 가리킨다.
- 하위 `CLAUDE.md`가 상위 값을 재정의하면 재정의 범위와 이유를 `정본` 칸에 쓴다.

### 1.4 저장소 간 링크

저장소 내부에서는 OKF 번들 절대경로나 상대경로를 사용한다.

```markdown
[고객 케이스 API 계약](/contracts/customer-case-api.md)
```

저장소 간 상대경로는 금지한다. 개발자별 체크아웃 배치와 별도 워크스페이스의 `gPUteer` 때문에 안정적이지 않다.

저장소 간 관계는 영속 ID와 현재 URL을 함께 쓴다.

```markdown
- 관계: `validated-by`
- 대상: `acop://sample/contracts/validated/customer-case-api`
- 보기: [sample 선검증 계약](https://github.com/ORG/final_project_sample/blob/main/wiki/contracts/validated/customer-case-api.md)
```

식별자 문법은 다음과 같다.

```text
acop://<repo-alias>/<concept-id>
```

| 저장소 | 별칭 |
|---|---|
| `program` | `hub` |
| `final_project_cs` | `cs` |
| `final_project_sample` | `sample` |
| `acop_dojo` | `dojo` |
| `datasets` | `data` |
| `gPUteer` | `gpu` |

`concept-id`는 wiki 루트 기준 경로에서 `.md`를 뺀 값이다.

```text
final_project_cs/wiki/contracts/customer-case-api.md
→ acop://cs/contracts/customer-case-api
```

파일을 이동하면 `aliases`에 이전 ID를 남긴다. URL은 사람이 클릭하는 현재 위치이고, 관계의 정본은 `acop://` ID이다.

### 1.5 버린 대안

| 대안 | 버린 이유 |
|---|---|
| 중앙 wiki 한 벌만 사용 | 코드와 문서가 같은 PR·태그로 움직이지 않아 계약과 runbook이 어긋남 |
| 저장소마다 완전히 독립 | 제품 결정, 일정, 평가 기준, 교차 저장소 계약이 중복됨 |
| 7번째 지식 저장소 신설 | 고정된 여섯 저장소 외 운영·권한·CI 대상이 늘어남 |
| 기존 폴더를 정리해 계속 사용 | 현재의 목적·생명주기 혼합을 그대로 보존함 |
| 저장소 간 상대경로 | 체크아웃 배치에 의존함 |
| GitHub URL만 사용 | 이동과 브랜치 변경에 취약하고 문서 정체성을 추적하기 어려움 |
| 모든 지식을 `CLAUDE.md`에 저장 | 라우터가 다시 거대 문서가 되고 계층 탐색이 무너짐 |

---

## 2. 디렉터리 구조

### 2.1 중앙 허브의 최상위 영역

중앙 허브는 6개 영역으로 고정한다. 숫자 접두사는 쓰지 않는다. 읽기 순서는 `index.md`가 담당한다.

| 영역 | 포함하는 내용 |
|---|---|
| `product` | 비전, 포지셔닝, 사용자, 문제, 범위, 용어 |
| `architecture` | 전체 시스템 경계, 저장소 관계, 공통 계약, 데이터 흐름, 교차 저장소 결정 |
| `delivery` | 마일스톤, 작업 패키지, DoD, 발표·릴리스 준비, 인수인계 |
| `evaluation` | 성공 지표, 평가 설계, 실험 프로토콜, 증거 기준 |
| `research` | 외부 조사, 경쟁·기술 비교, 선택지 분석 |
| `governance` | 문서 표준, 정본 규칙, 역할, 리뷰·보안 정책 |

결정이 끝난 기술 선택은 `research`가 아니라 `architecture/decisions`에 둔다. 조사 자료는 `research`에 남기고 결정 문서가 source로 참조한다.

### 2.2 로컬 코드 wiki의 영역

코드 저장소는 다음 5개 영역 중 필요한 것만 만든다.

| 영역 | 내용 |
|---|---|
| `architecture` | 저장소 내부 책임, 경계, 구성요소 관계, 데이터 모델 |
| `contracts` | API, 이벤트, 스키마, 외부 연동, 호환성 조건 |
| `operations` | 배포, 실행, 장애 대응, 환경, 복구 |
| `quality` | 테스트 전략, 실행 가능한 불변식, 품질 기준 |
| `decisions` | 해당 저장소에만 영향을 주는 결정과 이유 |

빈 폴더는 만들지 않는다. 데이터 저장소는 `catalog`, `quality`, `generation`, 도장 저장소는 `guide`, `generation`을 사용한다.

### 2.3 실제 적용 트리

```text
program/
├─ CLAUDE.md                         # 라우터 + 전역 사실 표
└─ wiki/                             # 중앙 번들, 초기 100~160개 개념
   ├─ index.md
   ├─ log.md
   ├─ product/                       # 15~25
   │  ├─ index.md
   │  ├─ vision.md
   │  ├─ positioning.md
   │  ├─ scope.md
   │  ├─ users/index.md
   │  └─ glossary/index.md
   ├─ architecture/                  # 25~40
   │  ├─ index.md
   │  ├─ system-context.md
   │  ├─ repository-map.md
   │  ├─ components/index.md
   │  ├─ interfaces/index.md
   │  ├─ data/index.md
   │  └─ decisions/
   │     ├─ index.md
   │     └─ log.md
   ├─ delivery/                      # 20~35
   │  ├─ index.md
   │  ├─ milestones/
   │  │  ├─ index.md
   │  │  ├─ midterm-2026-09-15.md
   │  │  └─ final-2026-10-26.md
   │  ├─ work-packages/index.md
   │  ├─ release/index.md
   │  └─ handoffs/index.md
   ├─ evaluation/                    # 15~25
   │  ├─ index.md
   │  ├─ success-metrics.md
   │  ├─ protocols/index.md
   │  ├─ datasets/index.md
   │  └─ evidence/index.md
   ├─ research/                      # 20~30
   │  ├─ index.md
   │  ├─ market/index.md
   │  ├─ technology/index.md
   │  └─ comparisons/index.md
   └─ governance/                    # 8~15
      ├─ index.md
      ├─ document-standard.md
      ├─ source-of-truth.md
      ├─ review-policy.md
      ├─ repository-registry.md
      └─ templates/index.md

final_project_cs/
├─ CLAUDE.md
└─ wiki/                             # 초기 100~160개
   ├─ index.md
   ├─ log.md
   ├─ architecture/
   │  ├─ index.md
   │  ├─ responsibilities.md
   │  ├─ boundaries.md
   │  └─ components/index.md
   ├─ contracts/
   │  ├─ index.md
   │  ├─ api/index.md
   │  ├─ events/index.md
   │  └─ schemas/index.md
   ├─ operations/
   │  ├─ index.md
   │  ├─ deployment/index.md
   │  └─ incidents/index.md
   ├─ quality/
   │  ├─ index.md
   │  ├─ invariants.md
   │  ├─ test-strategy.md
   │  └─ evidence/index.md
   └─ decisions/
      ├─ index.md
      └─ log.md

final_project_sample/
├─ CLAUDE.md
└─ wiki/                             # 계약 선검증 지식 20~40개
   ├─ index.md
   ├─ log.md
   ├─ contracts/
   │  ├─ index.md
   │  └─ validated/index.md
   ├─ quality/
   │  ├─ index.md
   │  └─ contract-tests.md
   └─ decisions/index.md

acop_dojo/
├─ CLAUDE.md
└─ wiki/
   ├─ index.md
   ├─ log.md
   ├─ guide/
   │  ├─ index.md
   │  └─ training-dojo.md
   └─ generation/
      ├─ index.md
      └─ report.md                   # python dojo.py report가 소유

datasets/
├─ CLAUDE.md
└─ wiki/
   ├─ index.md
   ├─ log.md
   ├─ catalog/
   │  ├─ index.md
   │  └─ <dataset-id>.md
   ├─ quality/
   │  ├─ index.md
   │  └─ checks.md
   └─ generation/
      ├─ index.md
      └─ reports/
         ├─ index.md
         └─ <dataset-id>-report.md   # 생성기가 소유

gPUteer/
├─ CLAUDE.md
└─ wiki/                             # 초기 60~100개
   ├─ index.md
   ├─ log.md
   ├─ architecture/
   │  ├─ index.md
   │  └─ components/index.md
   ├─ contracts/
   │  ├─ index.md
   │  └─ api/index.md
   ├─ operations/
   │  ├─ index.md
   │  ├─ pool-management/index.md
   │  └─ incidents/index.md
   ├─ quality/index.md
   └─ decisions/
      ├─ index.md
      └─ log.md
```

폴더 하나의 직접 개념 문서가 15개를 넘으면 하위 개념군을 만든다. 하위 폴더는 최소 3개 문서가 생길 때만 만든다.

---

## 3. front matter 스펙

### 3.1 필수와 선택 필드

OKF v0.2의 항상 필수인 필드는 `type` 하나뿐이다. A-COP 운영 요구는 별도 게시 프로필로 분리한다.

| 계층 | 필드 | 검증 |
|---|---|---|
| OKF 필수 | `type` | 없거나 빈 값이면 CI 실패 |
| OKF 선택 | `title`, `description`, `resource`, `tags`, `sources`, `usage_window`, `generated`, `verified`, `status`, `stale_after` | 존재할 때 형식 검증 |
| A-COP stable 게시 요구 | `title`, `description`, `owners`, `status`, `generated` | stable 문서에서 없으면 CI 실패 |
| A-COP 확장 | `aliases`, `relationships`, `claim_policy`, `automation` | 존재할 때 스키마 검증 |

`index.md`와 `log.md`는 예약 파일이므로 일반 concept front matter를 넣지 않는다. 번들 루트 `index.md`만 다음 예외를 허용한다.

```yaml
---
okf_version: "0.2"
---
```

### 3.2 type 목록

초기 통제 목록은 13개이다.

| type | 용도 |
|---|---|
| `concept` | 비전, 용어, 책임 모델, 하나의 설명 개념 |
| `decision` | 선택지, 결정, 이유, 결과 |
| `plan` | 미래 작업, 일정, 마일스톤, DoD |
| `contract` | API, 이벤트, 스키마, 저장소 간 약속 |
| `research` | 외부·내부 조사와 비교 분석 |
| `report` | 특정 시점의 결과·브리핑·상태 스냅숏 |
| `evidence` | 평가 입력, 테스트 결과, 측정 근거의 설명 |
| `runbook` | 배포·실행·장애 대응 절차 |
| `guide` | 온보딩, 사용법, 개발 안내 |
| `policy` | 문서·리뷰·보안·품질 규칙 |
| `template` | 산출물 양식과 작성 지침 |
| `handoff` | 작업 인계, 현재 상태, 수락 조건 |
| `dataset` | 데이터셋 의미, 범위, 스키마, 제약 |

`index`와 `log`는 type이 아니다.

OKF의 `Attested Computation`은 초기 목록에 넣지 않는다. 평가 수치에 공인 계산, executor, receipt, deterministic attester가 실제로 존재하는지 확인되지 않았기 때문이다. 필요성이 확인되면 OKF 명칭 그대로 추가한다.

### 3.3 주요 필드 규칙

| 필드 | 규칙 |
|---|---|
| `title` | 한국어 표시명 |
| `description` | index가 재사용할 수 있는 한 문장 요약 |
| `resource` | 설명 대상 코드·API·데이터 자산의 정본 URI |
| `tags` | 통제된 영어 소문자 kebab-case |
| `sources` | 문서가 파생된 자료. 각 항목의 `resource`는 필수 |
| `generated` | 현재 내용을 만든 사람·프로세스와 시각 |
| `verified` | source나 resource와 실제로 대조한 사건 |
| `status` | `draft`, `stable`, `deprecated` |
| `stale_after` | 해당 시각부터 재확인이 필요한 절대 ISO 8601 시각 |
| `owners` | 유지 책임자 1명, 공동 책임자는 최대 2명 |
| `aliases` | 이동 전 ID나 구 티켓형 이름 |
| `relationships` | 관계 종류, 대상 ID, 현재 URL |
| `automation` | 생성 명령, 소유 프로세스, 수동 편집 가능 여부 |

사람 actor는 `human:<id>`, 자동 프로세스는 `process:<id>`를 사용한다. 시각에는 명시적 UTC 오프셋을 넣는다.

### 3.4 근거 등급 연결

`[실측]`, `[외부]`, `[추정]`, `[미확보]`는 주장 단위이므로 front matter만으로 대체하지 않는다.

```markdown
[실측:S1] Markdown 문서는 1,285개이다.[^S1]
[외부:S2] OKF v0.2의 항상 필수인 필드는 `type` 하나이다.[^S2]
[추정] 1차 이관 대상은 약 311개이다.
[미확보] gPUteer 문서별 최근 열람 빈도는 확보하지 못했다.

[^S1]: 2026-08-31 문서 실측
[^S2]: Google OKF v0.2 SPEC §4.1, §11
```

front matter는 source 레지스트리와 적용 정책을 제공한다.

```yaml
claim_policy:
  required: true
  allowed: [실측, 외부, 추정, 미확보]
  default: 미확보
sources:
  - id: S1
    resource: acop://hub/governance/document-inventory-2026-08-31
    title: 2026-08-31 문서 실측
    author: process:document-inventory
    last_modified: 2026-08-31T00:00:00+09:00
```

적용 규칙은 다음과 같다.

- `실측`과 `외부`는 source ID와 footnote를 필수로 연결한다.
- `추정`은 계산 근거가 있으면 source ID를 붙인다. 없으면 가정을 바로 적는다.
- `미확보`는 source를 요구하지 않지만 무엇을 확인해야 해소되는지 쓴다.
- 표도 주장이다. 같은 등급이 열 전체에 적용되면 열 머리글에 등급을 쓸 수 있다.
- `verified`는 문서 정의의 검증이지 특정 실행의 attestation이 아니다.

### 3.5 태그 언어

태그는 영어 소문자 kebab-case로 결정한다.

코드 식별자와 저장소 이름이 영어이고, CI·검색·필터에서 조사·띄어쓰기 변형이 없는 안정된 키가 필요하기 때문이다. 제목과 본문은 한국어이므로 사람 가독성은 유지된다.

초기 허용 태그는 다음으로 제한한다.

```text
agent
api
architecture
contract
customer-operations
data
evaluation
gpu
release
security
testing
ui
```

영역명이나 type을 태그로 반복하지 않는다.

### 3.6 완전한 예시 1: decision

```markdown
---
type: decision
title: 계약 선검증 저장소와 릴리스 저장소의 역할 분리
description: sample에서 계약을 검증한 뒤 cs로 이식하는 경계와 이유를 정한다.
tags: [architecture, contract, testing]
owners: [human:architecture-owner]
status: stable
generated: { by: human:architecture-owner, at: 2026-08-31T18:00:00+09:00 }
verified:
  - { by: human:release-owner, at: 2026-09-01T10:00:00+09:00 }
stale_after: 2026-10-27T00:00:00+09:00
sources:
  - id: S1
    resource: acop://sample/contracts/index
    title: sample 검증 계약 색인
    author: team:sample
    last_modified: 2026-08-31T17:00:00+09:00
relationships:
  - kind: governs
    target: acop://sample/contracts/index
    href: https://github.com/ORG/final_project_sample/blob/main/wiki/contracts/index.md
  - kind: governs
    target: acop://cs/contracts/index
    href: https://github.com/ORG/final_project_cs/blob/main/wiki/contracts/index.md
claim_policy:
  required: true
  allowed: [실측, 외부, 추정, 미확보]
  default: 미확보
---

# 맥락

[실측:S1] `final_project_sample`은 계약을 먼저 검증하는 참고 구현체이고
`final_project_cs`가 릴리스 대상이다.[^S1]

# 결정

계약의 실험과 실패 기록은 sample에 두고, 채택된 계약과 릴리스 호환성
조건은 cs에 둔다. 같은 설명을 두 저장소에 복사하지 않는다.

# 선택지와 이유

| 선택지 | 판정 | 이유 |
|---|---|---|
| sample 문서를 cs에 복사 | 기각 | 두 정본이 생김 |
| sample만 계약 정본으로 사용 | 기각 | 릴리스 코드와 계약 버전이 분리됨 |
| 검증 증거와 채택 계약을 분리 | 채택 | 각 저장소의 책임과 변경 원자성이 맞음 |

# 결과

cs 계약은 source로 sample의 선검증 계약과 테스트 증거를 가리킨다.

[^S1]: sample 검증 계약 색인
```

### 3.7 완전한 예시 2: contract

```markdown
---
type: contract
title: 고객 케이스 생성 API 계약
description: 고객 케이스 생성 요청·응답과 실패 조건의 릴리스 계약이다.
resource: /src/api/customer_cases.py
tags: [api, contract, customer-operations]
owners: [human:backend-owner]
status: stable
generated: { by: human:backend-owner, at: 2026-09-02T14:30:00+09:00 }
verified:
  - { by: process:contract-test, at: 2026-09-02T14:42:00+09:00 }
  - { by: human:integration-owner, at: 2026-09-02T16:00:00+09:00 }
stale_after: 2026-09-16T00:00:00+09:00
sources:
  - id: S1
    resource: /tests/contracts/test_customer_case_api.py
    title: 고객 케이스 API 계약 테스트
    author: team:backend
    last_modified: 2026-09-02T14:40:00+09:00
  - id: S2
    resource: https://github.com/ORG/final_project_sample/blob/main/wiki/contracts/validated/customer-case-api.md
    title: sample 선검증 계약
    author: team:sample
relationships:
  - kind: validated-by
    target: acop://sample/contracts/validated/customer-case-api
    href: https://github.com/ORG/final_project_sample/blob/main/wiki/contracts/validated/customer-case-api.md
claim_policy:
  required: true
  allowed: [실측, 외부, 추정, 미확보]
  default: 미확보
---

# Responsibility

인증된 요청을 고객 케이스로 수락하고 영속 식별자를 반환한다.

# Boundary

- 입력 경계: HTTP 요청 스키마까지 담당한다.
- 제외: 에이전트의 후속 응답 생성은 담당하지 않는다.

# Contract

[실측:S1] 필수 입력은 `customer_id`, `channel`, `message`이다.[^S1]

| 결과 | 조건 | 응답 |
|---|---|---|
| 생성 | 입력과 인증이 유효함 | `201`, `case_id` |
| 거부 | 스키마 불일치 | `422` |
| 거부 | 인증 실패 | `401` |

# Invariants

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-API-001` | 성공 응답의 `case_id`는 영속 레코드를 가리킨다 | automated | `tests/contracts/test_customer_case_api.py::test_created_case_is_persisted` |
| `INV-CS-API-002` | 인증 없는 요청은 케이스를 만들지 않는다 | automated | `tests/contracts/test_customer_case_api.py::test_unauthorized_request_has_no_side_effect` |

# Relationships

- 선검증 계약: `acop://sample/contracts/validated/customer-case-api`

# Source

- 구현: `/src/api/customer_cases.py`
- 테스트: `/tests/contracts/test_customer_case_api.py`

[^S1]: 고객 케이스 API 계약 테스트
```

### 3.8 완전한 예시 3: report

```markdown
---
type: report
title: 2026-09-15 중간발표 준비 상태
description: 발표 범위, 증거 확보 상태, 차단 요소를 2026-09-10 기준으로 요약한다.
tags: [release, evaluation]
owners: [human:delivery-owner]
status: draft
generated: { by: human:delivery-owner, at: 2026-09-10T21:00:00+09:00 }
sources:
  - id: S1
    resource: acop://hub/delivery/milestones/midterm-2026-09-15
    title: 중간발표 마일스톤
    author: team:delivery
  - id: S2
    resource: acop://hub/evaluation/evidence/index
    title: 평가 증거 색인
    author: team:evaluation
claim_policy:
  required: true
  allowed: [실측, 외부, 추정, 미확보]
  default: 미확보
---

# 기준 시점

2026-09-10 21:00 KST의 스냅숏이다. 과거 결과 보고서이므로
`stale_after`를 두지 않는다.

# 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 발표 시나리오 | 완료 | [실측:S1] 수락 조건 5개 충족[^S1] |
| 종단 간 데모 | 진행 중 | [실측:S2] 증거 4개 중 3개 확보[^S2] |
| GPU 장애 대체 경로 | 미확보 | [미확보] 실패 주입 결과가 없음 |

# 판단

[추정] 실패 주입을 9월 12일까지 완료하면 발표 전 재실행 1회가
가능하다. 담당자 2명이 각각 2시간을 확보한다는 가정이다.

# 다음 결정

9월 12일 18:00까지 증거가 없으면 GPU 장애 대체 경로를 발표 범위에서
제외할지 결정한다.

[^S1]: 중간발표 마일스톤
[^S2]: 평가 증거 색인
```

---

## 4. index.md 규약

### 4.1 역할

`index.md`는 파일 목록이 아니라 해당 범위의 라우팅 계약이다. 하나의 index만 읽고 다음을 판단할 수 있어야 한다.

- 이 범위가 책임지는 것과 책임지지 않는 것
- 처음 읽을 문서와 작업별 읽기 순서
- 정본, 초안, 폐기 문서의 구분
- 현재 중요한 기한과 미결정 사항
- 관련 저장소와 상위·하위 영역

index에는 본문 지식을 복사하지 않는다. 한 항목에는 링크, 한 문장 설명, 상태·owner·신선도만 넣는다. 직접 자식만 나열하고 손자 문서까지 펼치지 않는다.

### 4.2 루트 index와 영역 index

| 항목 | 번들 루트 | 영역 index |
|---|---|---|
| 답하는 질문 | 이 저장소에서 어디로 가야 하는가 | 이 영역에서 무엇이 정본이고 어떤 순서로 읽는가 |
| 범위 | 전체 번들과 다른 번들 | 해당 디렉터리의 직접 자식 |
| 필수 내용 | 번들 목적, 저장소 역할, 영역, 정본 우선순위, 외부 번들, 경보 | 책임·비책임, 읽기 순서, 개념 목록, 결정·미결정, 관련 코드 |
| front matter | `okf_version`만 허용 | 없음 |
| 갱신 책임 | 저장소 문서 관리자 | 영역 steward |

### 4.3 실제 예시 1: 중앙 루트 index

```markdown
---
okf_version: "0.2"
---

# A-COP 지식 허브

6개 저장소에 걸친 제품, 통합 아키텍처, 일정, 평가, 조사, 문서 운영의
시작점이다. 코드와 같은 커밋에서 바뀌어야 하는 지식은 각 저장소
wiki에서 읽는다.

## 지금 먼저 볼 것

- [중간발표 마일스톤](delivery/milestones/midterm-2026-09-15.md)
  - 2026-09-15 발표 범위와 수락 조건. `stable`
- [전체 시스템 맥락](architecture/system-context.md)
  - 저장소별 책임과 연결. `stable`, stale: 2026-09-07
- [미결정 목록](delivery/open-questions.md)
  - 일정에 영향을 주는 미결정 사항. `draft`

## 영역

- [제품](product/) - 비전, 포지셔닝, 사용자, 범위와 용어
- [아키텍처](architecture/) - 전체 경계, 저장소 관계, 공통 계약과 결정
- [전달](delivery/) - 마일스톤, 작업 패키지, DoD와 인수인계
- [평가](evaluation/) - 성공 지표, 평가 프로토콜과 증거
- [조사](research/) - 외부 조사와 선택지 비교
- [거버넌스](governance/) - 문서 표준, 정본과 리뷰 정책

## 코드·데이터 번들

- `acop://cs/index` — [릴리스 코드 wiki](https://github.com/ORG/final_project_cs/blob/main/wiki/index.md)
- `acop://sample/index` — [계약 선검증 wiki](https://github.com/ORG/final_project_sample/blob/main/wiki/index.md)
- `acop://dojo/index` — [학습 도장 wiki](https://github.com/ORG/acop_dojo/blob/main/wiki/index.md)
- `acop://data/index` — [데이터셋 wiki](https://github.com/ORG/datasets/blob/main/wiki/index.md)
- `acop://gpu/index` — [GPU 풀 wiki](https://github.com/ORG/gPUteer/blob/main/wiki/index.md)

## 정본과 충돌

실행 가능한 계약·테스트, 소유 저장소의 CLAUDE.md 사실 표, 검증된
로컬 wiki, 중앙 wiki 순으로 판정한다.

## 최근 변경

[log.md](log.md)에서 번들 수준 변경만 확인한다.
```

### 4.4 실제 예시 2: 아키텍처 영역 index

```markdown
# 통합 아키텍처

## 책임

여러 저장소에 걸친 시스템 경계, 공통 계약, 데이터 흐름, 채택된 기술
결정을 설명한다. cs 내부 클래스 구조와 gPUteer 운영 절차는 범위가 아니다.

## 읽기 순서

1. [전체 시스템 맥락](system-context.md)
2. [저장소 책임 지도](repository-map.md)
3. 변경 대상에 따라 [인터페이스](interfaces/) 또는 [데이터](data/)
4. 이유가 필요하면 [결정](decisions/)

## 정본 개념

| 문서 | 설명 | 상태 | owner | 신선도 |
|---|---|---|---|---|
| [전체 시스템 맥락](system-context.md) | 외부 시스템과의 경계 | stable | architecture-owner | 2026-09-07 |
| [저장소 책임 지도](repository-map.md) | 여섯 저장소의 책임 | stable | architecture-owner | 2026-09-07 |
| [공통 인터페이스](interfaces/) | 교차 저장소 계약 | mixed | integration-owner | 문서별 |
| [데이터 흐름](data/) | 수집·저장·평가 경계 | draft | data-owner | 미검증 |

## 채택된 결정

- [계약 선검증과 릴리스 역할 분리](decisions/sample-validation-boundary.md)

## 미결정

- [미확보] GPU 장애 대체 경로의 최종 책임 저장소는 정해지지 않았다.
  gPUteer 배포 토폴로지와 cs 호출 실패 정책을 확인해야 한다.

## 관련 로컬 번들

- `acop://cs/architecture/index`
- `acop://gpu/architecture/index`
- `acop://sample/contracts/index`
```

---

## 5. 문서 본문 템플릿

### 5.1 공통 골격과 type별 골격

하나의 만능 템플릿으로 통일하지 않는다. 조사 보고서에 빈 Invariant 절을 강제하거나 계약 문서를 자유 형식으로 방치하지 않는다.

모든 문서는 다음 공통 머리를 사용한다.

```markdown
# 요약

이 문서가 답하는 질문과 결론을 3~5문장으로 쓴다.

# 범위

- 포함:
- 제외:
```

type별 필수 절은 다음과 같다.

| type | 필수 본문 절 |
|---|---|
| `concept` | 요약, 범위, Responsibility, Boundary, Relationships, Source |
| `decision` | 맥락, 결정, 선택지와 이유, 결과 |
| `plan` | 목표, 범위, 작업·일정, 수락 조건 |
| `contract` | Responsibility, Boundary, Contract, Invariants, Relationships, Source |
| `research` | 질문, 조사 범위, 관찰, 비교, 한계 |
| `report` | 기준 시점, 결과, 판단 |
| `evidence` | 주장, 수집 방법, 원본 위치, 재현 방법 |
| `runbook` | 발동 조건, 사전 조건, 절차, 성공 판정, 롤백 |
| `guide` | 대상 독자, 목표, 절차, 확인 |
| `policy` | 목적, 적용 범위, 규칙, 예외, 강제 수단 |
| `template` | 사용 조건, 복사할 골격, 완료 기준 |
| `handoff` | 배경, 넘기는 것, 현재 상태, 수락 조건, 담당자 |
| `dataset` | 의미, 범위, 스키마, 품질 조건, Source |

`Responsibility`, `Boundary`, `Invariants`, `Relationships`, `Source`는 에이전트 라우팅과 코드 식별의 일관성을 위해 영어 제목으로 고정한다. 내용은 한국어로 쓴다.

Source에는 코드를 복사하지 않는다. 구현, 테스트, 스키마, 외부 근거의 위치를 적는다.

### 5.2 불변식과 테스트 연결

불변식은 안정된 ID, 판정 방식, 실행 위치를 함께 기록한다.

```markdown
## Invariants

| ID | 불변식 | 판정 | 실행 위치 | 실패 의미 |
|---|---|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated | `tests/architecture/test_basement_is_domain_free.py` | 계층 경계 침범 |
| `INV-CS-API-002` | 인증 실패 요청은 케이스를 생성하지 않는다 | automated | `tests/contracts/test_customer_case_api.py::test_unauthorized_request_has_no_side_effect` | 보안·원자성 위반 |
| `INV-HUB-PROD-001` | 발표 문구는 승인된 포지셔닝을 사용한다 | review | `acop://hub/product/positioning` | 메시지 불일치 |
| `INV-GPU-OPS-003` | 노드 손실 후 대체 경로가 동작한다 | manual | `acop://gpu/operations/pool-management/failover-check` | 복구 불능 |
```

ID 문법은 다음과 같다.

```text
INV-<repo>-<scope>-<NNN>
```

`repo`는 `HUB`, `CS`, `SAMPLE`, `DOJO`, `DATA`, `GPU` 중 하나이다. 번호는 재사용하지 않는다.

| 판정 | 의미 |
|---|---|
| `automated` | CI나 테스트가 통과·실패를 판정 |
| `manual` | 재현 가능한 절차로 사람이 판정 |
| `review` | 정책·의미 판단이 필요 |

테스트 코드에는 역방향 표식을 둔다.

```python
# invariant: INV-CS-ARCH-001
def test_basement_is_domain_free():
    ...
```

CI는 다음을 검사한다.

1. 문서의 `automated` 테스트 경로가 존재한다.
2. 테스트에 같은 `invariant:` 표식이 있다.
3. 테스트에 있는 ID가 문서 카탈로그에 존재한다.
4. 불변식 ID가 중복되지 않는다.

테스트 통과와 attestation은 구분한다. 테스트가 불변식 정의와 맞는지는 `verified`로 기록한다. 특정 실행이 실제로 통과했다는 사실은 CI 실행 로그에 속한다.

---

## 6. 마이그레이션 범위 산정

### 6.1 이관 대상 수

1,285개를 모두 옮기지 않는다.

수동 선별·개념화 대상의 점추정은 원본 311개이고 합리적 범위는 250~380개이다. 복합 문서를 나누면 새 개념 문서는 약 350~480개가 될 가능성이 있다.

| 저장소 | 원본 md | 수동 선별 추정 | 근거 |
|---|---:|---:|---|
| `program` | 142 | 95 | 현재 계획·조사·브리핑에서 결정과 일정 지식의 비율이 높음 |
| `final_project_cs` | 485 | 120 | 릴리스 계약·운영·품질만 유지하고 TODO·history·코드 반복 설명 제외 |
| `final_project_sample` | 430 | 25 | 선검증 계약과 재현 증거만 승격 |
| `acop_dojo` | 1 | 1 | 사용·생성 규칙 유지 |
| `datasets` | 44 | 0 | REPORT를 수동 이관하지 않고 새 위치에서 재생성 |
| `gPUteer` | 183 | 70 | A-COP 통합 경계와 GPU 운영에 필요한 문서 선별 |
| 합계 | 1,285 | 311 | 목록 검토 전 점추정 |

이 수량은 파일명 분포와 저장소 성격으로 산출한 추정이다. 중복률과 최신성을 실측하지 않았으므로 ±20%보다 좁은 오차를 주장할 수 없다.

### 6.2 옮길 문서의 기준

다음 중 하나 이상을 만족하고 현재 유효한 문서만 옮긴다.

- 현재 제품·아키텍처·계약·평가·일정 결정의 이유를 보존한다.
- 코드만 읽어서는 알 수 없는 책임, 경계, 불변식, 관계를 설명한다.
- 2026-10-26 릴리스 또는 이후 운영에 필요하다.
- 다른 저장소가 의존하는 계약이나 증거이다.
- 평가·제출 증거처럼 보존 필요성이 있다.

### 6.3 옮기지 말아야 할 것

| 대상 | 처리 |
|---|---|
| `python dojo.py report`와 데이터셋 REPORT | 생성 명령과 입력만 이관하고 재생성 |
| sample의 일반 내부 설명 | 릴리스 계약 검증에 필요한 것만 승격 |
| Git으로 복원 가능한 history·일지 | 핵심 결정만 `decision`으로 추출 |
| 완료된 개인 TODO와 임시 메모 | 결정·증거가 없으면 제외 |
| 코드를 문장으로 다시 쓴 문서 | 책임·경계·불변식·이유가 없으면 제외 |
| 구버전 계획과 중복 브리핑 | 최신 정본의 source로 필요할 때만 보존 |
| 대형 로그와 바이너리 | wiki에는 설명과 원본 위치만 기록 |

여기서 제외는 삭제를 뜻하지 않는다. 새 구조의 이관 집합에 포함하지 않는다는 뜻이다.

### 6.4 1,466줄 계획서 분할

`A-COP_구현계획서_v8.md`의 28개 절을 그대로 28개 파일로 만들지 않는다. 17개 개념으로 분할하는 것을 1차 산정치로 한다.

| 영역 | 개념 | 수 |
|---|---|---:|
| product | 비전·포지셔닝, 사용자·문제, 범위·비범위 | 3 |
| architecture | 시스템 맥락, 구성요소 책임, 데이터 모델·DDL, 에이전트 오케스트레이션, 저장소 통합 경계 | 5 |
| architecture/interfaces | API 계약, 이벤트·메시지 계약, sample→cs 계약 이식 | 3 |
| evaluation | 성공 지표, 평가 프로토콜·증거 기준 | 2 |
| delivery | 전체 일정, 중간발표, 최종 릴리스, DoD 29항목 | 4 |
| 합계 |  | 17 |

다음 중 하나가 달라지면 별도 문서로 자른다.

- 책임자 또는 리뷰어
- 변경 주기와 `stale_after`
- 독립적으로 링크할 필요
- type
- 정본 source 또는 소유 저장소
- 독립적인 승인·폐기 가능성

DDL 전문은 Markdown에 복사하지 않는다. 실제 스키마 파일을 `resource`로 가리키고 문서에는 책임, 경계, 불변식, 결정 이유만 남긴다.

### 6.5 일괄 이관 위험

| 위험 | 영향 | 먼저 확인할 것 |
|---|---|---|
| 잘못된 type·영역을 수백 번 반복 | 대규모 재이동 | 층화 표본 36~48개 시험 분류 |
| 중복 정본 생성 | 에이전트가 다른 값을 소비 | 사실·계약별 소유 저장소 |
| 생성물 수동 수정 | 다음 생성 때 변경 소실 | 생성 명령·입력·출력·소유 프로세스 |
| 낡은 문서의 권위 상승 | 오래된 내용이 stable처럼 보임 | 코드·테스트·담당자와 대조 |
| 저장소 간 링크 파손 | 탐색 실패 | alias, ID 해석기, 전역 catalog |
| 6명의 동시 충돌 | 중복·누락 | 원본별 단일 판정 담당자 |
| 예상보다 큰 작업량 | 발표 일정 잠식 | 고가치 20개 실제 처리시간 |

일괄 작업 전 다음 열을 가진 범위 목록이 필요하다.

```text
원본 경로
추정 type
목표 영역
정본 여부
자동 생성 여부
최신성
담당자
유지 / 추출 / 재생성 / 제외 판정
```

---

## 6-1. “완벽한 구조 후 일괄 이관”에 대한 판정

그 계획에는 그대로 동의하지 않는다.

저장 원칙과 최소 규격을 먼저 정하는 것은 맞다. 그러나 실제 문서를 하나도 대입하지 않고 type과 세부 영역을 완벽하게 확정하는 것은 불가능하다.

분류 체계가 실제 이관 때 맞지 않을 위험은 높다. 1,285개가 계획, 연구, 코드 문서, 생성 보고서, 참고 구현, 별도 운영 플랫폼에 걸쳐 있기 때문이다. 특히 다음 경계에서 오분류가 예상된다.

- `report`와 `evidence`
- `concept`와 `policy`
- `guide`와 `runbook`
- 중앙 `architecture`와 로컬 `architecture`
- 보존할 sample 계약과 폐기할 sample 내부 설명

설계 확정 전에 전체 이관을 시작할 필요는 없지만 분류 적합성 시험은 해야 한다. 이 시험은 마이그레이션이 아니라 설계 검증이다.

1. 여섯 저장소에서 크기·최근성·파일명·폴더를 층화해 36~48개를 뽑는다.
2. README, REPORT, CLAUDE, index, 티켓형 핸드오프를 각각 최소 3개 포함한다.
3. 두 사람이 독립적으로 type, 영역, 유지·제외를 판정한다.
4. 판정 일치율과 애매 비율을 기록한다.
5. 일치율이 80% 미만이거나 애매 비율이 15%를 넘으면 정의를 수정한다.
6. 1,466줄 계획서를 17개 개념에 실제로 매핑해 누락과 중복을 확인한다.

설계 단계에서 확정 가능한 것은 다음이다.

- 중앙과 로컬의 배치 원칙
- 저장소별 wiki와 탐색 시작점
- `type` 단독 필수와 예약 파일 규칙
- 영속 ID와 저장소 별칭
- 정본 우선순위
- 생성물 소유 규칙
- 불변식 ID와 테스트 연결 방식

사용하면서 정해야 하는 것은 다음이다.

- 13개 type 사이의 예외
- 폴더당 15개 기준의 적정성
- type별 적정 `stale_after`
- 실제 이관량과 문서당 처리시간
- `Attested Computation` 도입 여부

따라서 권고안은 다음과 같다.

```text
변하지 않을 골격 확정
→ 대표 표본으로 1회 교정
→ v1 동결
→ 범위가 확정된 일괄 이관
```

---

## 7. 6명 동시 운영 규칙

### 7.1 역할

실명이 제공되지 않았으므로 역할만 정한다. 킥오프 때 한 사람씩 배정한다.

| 역할 | 쓰고 유지하는 범위 |
|---|---|
| product owner | 제품 범위, 포지셔닝, 사용자 |
| architecture owner | 통합 아키텍처, 교차 저장소 결정 |
| backend/contract owner | cs·sample의 API·이벤트·스키마 계약 |
| data/evaluation owner | datasets, 평가 기준과 증거 |
| integration/UI owner | UI 연동 계약, 종단 간 흐름, 인수 조건 |
| infrastructure/operations owner | gPUteer, 배포·장애·복구 |

프로젝트 리드가 `delivery`, 지정된 문서 steward가 `governance`를 겸임한다. 각 문서의 유지 owner는 한 명을 기본으로 하고 공동 owner는 최대 두 명이다.

### 7.2 충돌 방지

- 작업 하나당 브랜치 하나, 개념 하나당 파일 하나를 원칙으로 한다.
- PR 설명에 변경할 concept ID를 먼저 선언한다.
- 같은 concept ID를 수정하는 열린 PR이 있으면 별도 PR을 만들지 않는다.
- `CODEOWNERS`를 영역 폴더에 연결한다.
- 문서 owner와 코드 owner가 다르면 둘 다 리뷰한다.
- index와 log는 개념 PR에서 마지막에 갱신한다.
- 여러 사람이 한 거대 문서를 동시에 편집하지 않는다.
- 티켓형 핸드오프는 `handoff`로 유지한다.
- 새 파일명은 `s-versioning-01.md`처럼 정규화하고 구 표기는 `aliases`에 남긴다.

### 7.3 리뷰 정책

| 변경 | 요구 |
|---|---|
| `decision`, `contract`, `policy`를 stable로 전환 | 저자 외 1명 승인 |
| API·DDL·보안·삭제·릴리스 계약 | 도메인 owner와 소비자 또는 구현자 확인 |
| 마일스톤·DoD·평가 프로토콜 | 결과 수락 owner 승인 |
| draft research·초기 concept | 리뷰 없이 병합 가능, `verified`는 쓰지 않음 |
| handoff | 수신자가 수락 조건 확인 |
| 자동 생성 report | 생성기 의미 변경만 리뷰 |
| 기계적인 index·log 변경 | 부모 PR 리뷰에 포함 |
| 오탈자·링크 수정 | CI 통과만 요구 |

### 7.4 신선도

`stale_after`를 사용한다. 모든 문서에 강제하지는 않는다. 도달했다고 빌드를 실패시키지 않고 경고와 owner 이슈를 만든다.

| type | 초기 기준 |
|---|---|
| `contract` | 14일 또는 다음 통합 마일스톤 중 빠른 시각 |
| 활성 `plan`, `handoff` | 7일 또는 마감 시각 |
| `runbook` | 14일, 실제 실행 검증 후 30일 |
| `concept`, `policy`, `dataset` | 30일 |
| `research` | 30일 또는 결정을 내릴 시각 |
| `decision`, `report`, `evidence`, `template` | 기본 생략 |

`stale_after`는 거짓이라는 뜻이 아니라 재확인이 필요하다는 뜻이다. owner는 다시 검증해 `verified`와 새 `stale_after`를 기록하거나 `deprecated`로 전환한다.

### 7.5 log.md

`log.md`를 두되 모든 폴더에 만들지 않는다.

- 여섯 번들 루트
- 중앙의 6개 최상위 영역
- 변경 이유 추적이 중요한 `decisions/`
- 그 밖의 하위 폴더에는 두지 않음

```markdown
# Architecture Update Log

## 2026-09-02

- **Decision**: [계약 선검증과 릴리스 역할 분리](sample-validation-boundary.md)를 stable로 전환했다.
- **Deprecation**: 구 통합 API 초안을 폐기하고 새 계약으로 연결했다.
```

---

## 8. 자동화

### 8.1 지금 사람이 할 것

| 작업 | 이유 |
|---|---|
| type과 중앙·로컬 배치 판정 | 의미와 책임 판단이 필요함 |
| decision의 선택지와 이유 작성 | 코드에서 복원할 수 없음 |
| `[추정]`, `[미확보]` 판정 | 불확실성에 대한 사람의 책임이 필요함 |
| stable 전환과 사람 검증 | 검토 행위 자체는 자동화할 수 없음 |
| 표본 분류와 계획서 개념 매핑 | 분류 체계 검증이 필요함 |

### 8.2 처음부터 자동화할 것

| 검사 | 동작 |
|---|---|
| front matter lint | YAML, `type`, status, 시간, source 형식 |
| stable 게시 프로필 | title, description, owners, generated |
| 내부 링크 | Markdown 링크, 앵커, 로컬 resource |
| 불변식 | 문서 ID와 테스트 표식의 양방향 연결 |
| 생성물 보호 | 지정 프로세스 외 변경 거부 |
| index | 직접 자식 누락, 예약 파일 규칙 |

권위 있는 강제점은 CI로 결정한다. pre-commit은 같은 검사를 빠르게 실행하는 선택형 도구로 제공한다.

| CI 실패 | 경고 |
|---|---|
| YAML 파싱 실패, 빈 type | draft의 게시 프로필 누락 |
| 잘못된 status·시간 | `stale_after` 도달 |
| source 내부 resource 누락 | 미등록 tag |
| 저장소 내부 링크 파손 | 알 수 없는 type |
| ID 중복 | 아직 작성되지 않은 cross-repo 대상 |
| automated 테스트 경로 없음 | draft index 설명 누락 |
| 생성물 수동 수정 | 사람 검증 없는 문서 안내 |

### 8.3 저장소 간 링크 검사

1. 각 번들에서 ID, 현재 경로, title, status를 `catalog.json`으로 생성한다.
2. 중앙 야간 CI가 여섯 저장소를 checkout한다.
3. 여섯 catalog를 합쳐 전역 catalog를 만든다.
4. `relationships.target`과 본문의 `acop://` ID를 검사한다.
5. 누락은 첫날 경고, 3일 연속이면 owner 이슈를 만든다.
6. `aliases`가 있으면 새 ID로 해석하고 이전 ID 사용 경고를 낸다.

저장소의 실제 GitHub 조직명과 기본 브랜치는 확보되지 않았다. 도입 전에 여섯 remote URL과 접근 권한을 확인해야 한다.

### 8.4 나중에 자동화할 것

- index 목록과 catalog 자동 생성
- `resource` 코드 변경 시 stale 알림
- 주간 freshness 대시보드
- 생성 REPORT의 새 경로 출력
- Mermaid 구문 검사와 정적 사이트 렌더링
- 고립 문서와 중복 문서 탐지

자동 갱신은 위치, 색인, 서명, 기계 판정 가능한 상태에 한정한다. 결정 이유와 미결정 사항을 코드에서 추론해 자동으로 확정하지 않는다.

### 8.5 OpenWiki CLI 판정

OpenWiki CLI는 2026-10-26까지 공식 작성·갱신 도구로 채택하지 않는다.

이유는 다음과 같다.

- A-COP 문서의 핵심 가치인 미결정 사항과 결정 이유는 코드에서 추출할 수 없다.
- 현재 OpenWiki 설명은 OKF v0.1 번들을 생성한다고 밝히지만 이 표준은 v0.2를 사용한다.
- 자동 갱신이 근거 등급과 미확보 표현을 그럴듯한 확정문으로 바꿀 위험이 있다.
- 기본 단일 저장소 방식만으로 여섯 저장소의 소유권과 전역 관계를 해결하지 못한다.
- 10주 프로젝트에서는 생성 결과 검수 비용이 절감 효과보다 클 가능성이 있다.

다만 다음 방식은 채택한다.

```text
AGENTS.md / CLAUDE.md
→ wiki/index.md
→ 영역/index.md
→ 개념 문서
→ 소스코드
```

한 문서 한 개념, Knowledge Router, `log.md`, agent-first but not agent-only 원칙도 채택한다.

9월 15일 이후 격리 브랜치에서 로컬 코드 인벤토리 생성 실험은 가능하다. v0.2 메타데이터와 사람 작성 영역을 보존하고 리뷰 시간을 줄인다는 실측이 있어야 재검토한다.

---

## 9. 도입 순서

사람·시간은 실제 작업시간의 합이며 회의 대기와 PR 대기는 제외한다.

### 9.1 오늘부터 2일 이내

| 작업 | 사람·시간 |
|---|---:|
| repo alias, 역할, 중앙·로컬 경계 결정 회의 | 6 |
| 여섯 wiki 골격과 root index 생성 | 4 |
| CLAUDE 라우터와 사실 표 범위 정리 | 3 |
| type, front matter, 본문 템플릿 고정 | 5 |
| YAML·type·status·내부 링크 CI | 6~8 |
| 합계 | 24~26 |

첫날부터 새 문서는 새 위치와 템플릿으로만 작성한다. 기존 1,285개는 아직 움직이지 않는다.

### 9.2 중간발표 2026-09-15 전

| 작업 | 완료 기준 | 사람·시간 |
|---|---|---:|
| 36~48개 표본 분류 | 일치율과 애매 비율 기록 | 14~18 |
| 거대 계획서 매핑 | 28절→17개 검토 | 5~7 |
| 발표 핵심 문서 작성 | 비전, 시스템 맥락, 마일스톤, 평가, 핵심 계약 | 24~32 |
| 전역 ID catalog 시제품 | 여섯 alias와 링크 검사 | 8~12 |
| 불변식 양방향 검사 | 기존 architecture 테스트 연결 | 5~7 |
| 실제 PR 운영 리허설 | 코드 PR 2개에서 문서 동시 변경 | 6~8 |
| 합계 | 62~84 |

목표는 전체 이관이 아니라 20~30개 고가치 개념이 실제로 작동하게 하는 것이다.

### 9.3 9월 15일 이후

| 작업 | 사람·시간 |
|---|---:|
| 1,285개 범위 목록화 | 28~40 |
| 약 311개 선별 이관 | 120~200 |
| dojo·datasets 생성물 재배치 | 12~20 |
| freshness·전역 링크 자동화 | 12~18 |
| 정적 렌더링·다이어그램 검사 | 8~12 |
| OpenWiki 격리 실험 | 6~10 |
| 합계 | 186~300 |

선별 이관 추정은 문서당 평균 23~39분이다. 표본 20개를 실제 처리한 중앙값으로 다시 산정해야 한다.

### 9.4 최종발표 이후로 미룰 것

- 검색 UI와 그래프 뷰
- 자동 의미 중복 탐지
- 모든 문서의 자동 freshness PR
- Attested Computation 런타임
- 별도 지식 서비스나 벡터 DB
- OpenWiki 공식 도입 재평가

---

## 10. 이 설계의 약점

### 10.1 실패할 수 있는 부분

| 약점 | 실패 모습 | 완화 |
|---|---|---|
| 혼합형의 인지 비용 | 중앙과 로컬 위치를 매번 고민 | 변경 원자성 질문을 PR 템플릿에 넣음 |
| `acop://`의 비표준성 | GitHub에서 직접 클릭 불가 | `href` 병기와 catalog 렌더링 |
| 근거 등급의 작성 부담 | 모든 문장에 붙이다 포기 | 사실 주장에만 적용 |
| 13개 type | report/evidence, guide/runbook 혼동 | 표본 교정과 애매 사례 기록 |
| stale 알림 피로 | 문서가 한꺼번에 stale | 스냅숏에는 생략하고 경고로 시작 |
| index와 log 이중 관리 | PR마다 누락 | CI 경고 후 목록 부분 자동화 |
| CLAUDE 사실 표 예외 | CLAUDE가 다시 지식 창고가 됨 | 라우터와 4열 표 외 내용 거부 |
| 전역 catalog 의존 | gPUteer checkout 실패 | 로컬 검사 분리, 마지막 성공 manifest 사용 |
| 새 구조의 권위 착시 | 낡은 이관 문서가 stable로 보임 | 이관 문서는 기본 draft |

### 10.2 규약이 무너지기 쉬운 지점

첫째는 front matter 선택 필드이다. 일정이 급하면 본문만 쓰고 owner, source, freshness를 빼게 된다. 따라서 초안은 빨리 쓸 수 있게 하고 stable 전환 시 게시 프로필을 강제한다.

둘째는 한 문서 한 개념이다. 계획, 회의, 결정, TODO를 한 파일에 계속 붙이기 쉽다. 줄 수보다 owner, type, 변경 주기, 승인 단위가 달라지는지를 리뷰한다.

셋째는 자동 생성 문서의 수동 수정이다. 문서 경고만으로 부족하다. 다음 메타데이터와 CI 검사가 필요하다.

```yaml
automation:
  command: python dojo.py report
  owner: process:dojo-report
  manual_edit: false
```

넷째는 `verified`의 남용이다. 단순히 읽었다는 뜻으로 쓰지 않는다. source나 resource와 실제로 대조한 경우에만 기록한다.

### 10.3 과설계 가능성

`acop://` 전역 ID와 불변식 양방향 검사는 6명·10주 팀에 과설계일 수 있다. 다음 최소 범위로 제한한다.

- `acop://`는 저장소 간 stable 계약과 결정에만 필수
- 불변식 검사는 기존 architecture 테스트와 핵심 계약 테스트부터 적용
- 전역 catalog는 ID, title, URL, status 네 필드만 생성

그래프 DB, 전체 corpus 자동 추출, 모든 문서의 의미 검증은 최종발표 전에 하지 않는다.

### 10.4 아직 못 정한 것

| 항목 | 현재 판정 | 필요한 정보 |
|---|---|---|
| 실제 이관 수 | 311개, 범위 250~380개 추정 | 파일별 중복·최신성·생성 여부 |
| 최종 개념 수 | 350~480개 추정 | 복합 문서 분할 결과 |
| Attested Computation | 못 정함 | 공인 계산, receipt, attester 존재 여부 |
| GitHub 조직명·기본 브랜치 | 못 정함 | 여섯 remote URL |
| 역할별 실제 담당자 | 못 정함 | 팀원 이름·GitHub ID |
| type의 최종 경계 | v1 후보만 결정 | 36~48개 표본 분류 |
| OpenWiki의 향후 도입 | 최종발표 전 미채택 | 격리 실험의 정확도와 리뷰 시간 |

---

## 11. 배포 전 체크리스트

- [ ] 여섯 저장소 alias와 remote URL을 확인했다.
- [ ] 여섯 역할과 `delivery`, `governance` 겸임자를 정했다.
- [ ] 각 저장소에 `wiki/index.md`와 필요한 영역 index가 있다.
- [ ] `CLAUDE.md`에는 라우터와 범위가 겹치지 않는 사실 표만 있다.
- [ ] CI가 YAML, type, status, 시간, 내부 링크를 검사한다.
- [ ] 표본 분류 일치율이 80% 이상이고 애매 비율이 15% 이하이다.
- [ ] 1,466줄 계획서의 17개 개념 매핑을 두 사람이 검토했다.
- [ ] 기존 architecture 불변식 하나가 문서와 테스트에 양방향 연결됐다.
- [ ] 중간발표 핵심 문서의 source와 owner가 지정됐다.
- [ ] 자동 생성 문서의 명령과 수동 편집 금지 규칙이 확인된다.

## 12. 기준 자료

- [Google Open Knowledge Format v0.2 SPEC](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
- [LangChain OpenWiki](https://github.com/langchain-ai/openwiki)

OKF 필드와 예약 파일 규칙은 원문 규격을 따랐다. 영역, type 목록, `acop://` ID, 리뷰와 운영 규칙은 A-COP 전용 결정이다.