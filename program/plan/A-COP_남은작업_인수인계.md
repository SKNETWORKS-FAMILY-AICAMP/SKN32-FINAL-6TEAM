# A-COP 남은 작업 인수인계

작성 2026-08-24. 데이터셋과 문서 정리를 마친 시점의 기록이다.

## 이 문서를 왜 쓰나

작업이 여러 세션에 나뉘어 진행된다. 다음 세션이 무엇을 이어받아야 하는지, 앞선
세션에서 무엇이 확인됐고 무엇이 미확인인지 적어둔다.

세션이 바뀌면 앞의 맥락이 사라진다. 그래서 "무엇을 해야 한다"만 적지 않고 "왜
그래야 하는지"와 "어디까지 확인됐는지"를 함께 적는다.

## 완료된 것

| 항목 | 결과 | 커밋 |
|---|---|---|
| 쿠팡 주문 수집 확장 | 외부에서 5.4.6 완성. 테스트 45개 통과 | `ba92831` |
| 개인정보 파일 정리 | 세션 파일·스크린샷·조사 산출물 삭제 | (git 미추적 파일이라 커밋 없음) |
| 데이터셋 문서 연결 | 루트 `CLAUDE.md`에 `datasets/` 절 추가 | `5601c7d` |
| 택배조회 REPORT | `datasets/commerce/courier_tracking/REPORT.md` | `5601c7d` |
| 네이버 주문 REPORT | `datasets/commerce/naver_order_history/REPORT.md` | `5601c7d` |
| Composer 범위 재검토 | 토글 전용으로는 요구 미충족. 카탈로그 기반 CRUD와 선언형 Team 권고 | `f2b2049` |
| Composer 소유권 정정 | sample이 만들고 UI가 가져다 쓴다 | `f2b2049` |
| 비전 항목 3건 등록 | VISION-10 3층, VISION-11, VISION-12 | `f250d07` |
| 확장 추천 등록 | VISION-13. 자기 관측 기반은 이미 신호가 있다 | `fe7fdad` |
| v3 문서·UI 원칙 정정 | 정정 안내 삽입, "대상"의 뜻 명시 | (이번 커밋) |

## 남은 작업

### 1. 원격 저장소 연결 (사람이 해야 함)

`workspace` 브랜치에 원격 추적이 설정돼 있지 않다.

```bash
git push -u origin workspace
```

AI 세션은 푸시를 실행하지 않는다. 사용자가 직접 실행한다.

### 2. VOC 데이터 전처리 (모델링 세션)

Core 1의 Context Broker가 쓸 RAG 지식 재료다. RAG는 질문에 답하기 전에 관련 자료를
찾아 읽는 방식을 말한다. 그 읽을 자료가 아직 원본 상태다.

| 데이터셋 | 원본 크기 | 전처리 |
|---|---|---|
| `voc/aihub_71844_llm_instruction_tuning` | 209M | 없음 |
| `voc/aihub_102_smb_order_qa` | 189M | 없음 |
| `voc/nikl_ne_2022` | 137M | 없음 |
| `voc/aihub_30716_callcenter_qa` | 83M | 없음 |
| `voc/aihub_71603_aspect_sentiment` | 63M | 없음 |

각 폴더의 `REPORT.md`에 데이터 성격이 적혀 있다. 전처리 결과는 `processed/`에 넣고
`datasets/README.md`의 폴더 규칙을 따른다.

**주의**: `commerce/courier_tracking`은 전처리 대상이 아니다. 학습 데이터가 아니라
실행 시점에 호출하는 도구다. `processed/`가 비어 있는 것이 정상이다.

### 3. 네이버 주문 4건 누락 수정 (코드 세션)

실제 주문 72건 중 68건만 수집됐다. 빠진 주문번호는 다음과 같다.

```
2022043085163701
2023051853027171
2023090698394101
2024032354706671
```

원인은 확인됐다. 목록 화면의 카드 하나에 주문이 여러 개 들어 있는 경우가 있는데,
크롤러가 카드마다 주문을 하나씩만 읽는다.

고치는 방향은 카드 단위가 아니라 주문 상세 링크 단위로 순회하는 것이다. 자세한
페이지별 수치는 `datasets/commerce/naver_order_history/REPORT.md`에 있다.

세션 파일을 지웠으므로 다시 수집하려면 로그인부터 해야 한다.

### 4. Composer 범위 재검토 (설계 세션)

운영 UI에서 팀 모듈과 GraphStore 같은 기능을 넣고 빼고, 인스턴스를 이름과 설정만
입력해 만들 수 있어야 한다는 요구가 있다.

기존 v3 설계 문서(`A-COP_Composer_v3_설계_토글전용_UI이관.md`)는 범위를 "켜고 끄기"로
좁혔는데, 이는 요구를 충족하지 못한다.

현재 `final_project_cs`에는 `/current`, `/validate`, `/apply`, `/toggle` 이 모두 있다.
v2(전체 선언 적용)와 v3(토글)가 공존하는 상태다.

재검토를 마쳤다. 결과는 `A-COP_Composer_범위재검토.md`에 있다.

남은 것은 구현이다. 순서는 다음과 같다.

1. 선언형 Team 실행기(`DeclarativeTeamRuntime`) 배포
2. Composer 인스턴스 CRUD 계약 확정
3. 카탈로그 HTTP 조회
4. UI 선택 생성 화면

앞의 것이 없으면 뒤의 것을 만들어도 동작하지 않는다. 근거는
`final_project_sample/docs/vision/VISION-10_예제_카탈로그_스캐폴딩_CLI.md` 3층이다.

## 확인하지 못한 것

정직하게 적는다. 아래는 미확인이거나 다른 세션의 결과를 봐야 하는 항목이다.

| 항목 | 상태 |
|---|---|
| 쿠팡 배송이력 5건 중 4건만 수집 | 5.4.6에서 해결됐는지 미확인. `normalize.py` 실행 결과는 배송 4행 |
| `implementation_ref` 의 allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용된다 |
| v2 계약 문서 | 다른 세션에서 작업 중이라 열지 않았다. endpoint 이름·`config_revision`·인증 scope·감사 필드를 최종 계약에서 하나로 맞춰야 한다 |

### 5. UI가 import할 패키지 이름 확정 (설계 세션)

`A-COP_Composer_소유권_정정.md`의 후속 조치 세 가지 중 둘은 끝냈다. v3 문서 정정과
UI 원칙 명시다.

남은 하나는 **UI가 import할 패키지의 이름과 경계 확정**이다. 정정 문서에서는
`acop_composer_ui`를 예시로 썼으나 실제 이름은 정해지지 않았다.

이것은 `A-COP_Composer_v3_설계_토글전용_UI이관.md` §8.1의 명명 확정 때 함께 정한다.
endpoint 이름, `config_revision`, 인증 scope, 감사 로그 필드도 같은 자리에서 하나로
맞춘다.

## 참고 문서

| 문서 | 내용 |
|---|---|
| `program/plan/A-COP_구현계획서_v8.md` | 전체 계획. Core 1/Core 2 구조는 §8 |
| `datasets/README.md` | 데이터 폴더 규칙 |
| 각 데이터셋의 `REPORT.md` | 그 데이터가 무엇이고 어디에 쓰이는지 |
| `CLAUDE.md` (루트) | 작업 기준선. 데이터 폴더 절 포함 |
