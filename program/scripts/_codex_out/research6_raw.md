===== FILE: legal-basis.md =====
---
type: reference
title: A-COP 법적 근거 원문
description: 청약철회와 개인정보 처리에 적용되는 법조문 원문과 재현 가능한 조회 방법을 정리한다.
status: draft
tags: [contract, security, governance, documentation]
---

## 결론

[실측][외부] 법제처 Open API로 직접 조회한 전자상거래법 제17조와 개인정보 보호법 제2조·제15조·제17조 원문이다. 기존 `_법령사실_2026-08-15.md`는 웹 검색 기반 요약이므로 RAG 근거로는 이 원문을 우선한다.

[실측] `return_exchange`의 단순변심 7일과 하자 3개월·30일 판정은 조문과 일치한다. 다만 청약철회 불가 사유 6개는 Team 로직에 반영되지 않았다. `response_review.py`의 PII 정규식은 개인정보 정의 중 단일 필드 패턴만 다루며, 다른 정보와의 결합 위험은 다루지 않는다.

## 조회 방법

[실측][외부] 출처: `law.go.kr` Open API.

```text
GET http://www.law.go.kr/DRF/lawSearch.do?OC={OC}&target=law&type=XML&query={법령명}
    → 법령일련번호(MST) 확보
GET http://www.law.go.kr/DRF/lawService.do?OC={OC}&target=law&MST={MST}&type=XML
    → 조문 전체
```

`OC`는 Open API 이용자 식별자다. 원본 작성에 사용한 값은 문서에 남기지 않았다. [미확보] 재현에는 팀이 보유한 `OC`가 필요하다.

## 전자상거래 등에서의 소비자보호에 관한 법률 제17조

[실측][외부] 법령ID `009318`, 법령일련번호(MST) `282793`. 아래는 원본에 수록된 조회 원문이다. 출처 URL은 위 Open API 요청식과 같다.

> **제1항** 통신판매업자와 재화등의 구매에 관한 계약을 체결한 소비자는
> 다음 각 호의 기간(거래당사자가 다음 각 호의 기간보다 긴 기간으로
> 약정한 경우에는 그 기간을 말한다) 이내에 해당 계약에 관한
> 청약철회등을 할 수 있다.
>
> 1. 제13조제2항에 따른 계약내용에 관한 서면을 받은 날부터 7일. 다만,
>    그 서면을 받은 때보다 재화등의 공급이 늦게 이루어진 경우에는
>    재화등을 공급받거나 재화등의 공급이 시작된 날부터 7일
> 2. 제13조제2항에 따른 계약내용에 관한 서면을 받지 아니한 경우,
>    통신판매업자의 주소 등이 적혀 있지 아니한 서면을 받은 경우 또는
>    통신판매업자의 주소 변경 등의 사유로 제1호의 기간에 청약철회등을
>    할 수 없는 경우에는 통신판매업자의 주소를 안 날 또는 알 수 있었던
>    날부터 7일
> 3. 제21조제1항제1호 또는 제2호의 청약철회등에 대한 방해 행위가 있는
>    경우에는 그 방해 행위가 종료한 날부터 7일
>
> **제2항** 소비자는 다음 각 호의 어느 하나에 해당하는 경우에는
> 통신판매업자의 의사에 반하여 제1항에 따른 청약철회등을 할 수 없다.
> 다만, 통신판매업자가 제6항에 따른 조치를 하지 아니하는 경우에는
> 제2호부터 제5호까지의 규정에 해당하는 경우에도 청약철회등을 할 수 있다.
>
> 1. 소비자에게 책임이 있는 사유로 재화등이 멸실되거나 훼손된 경우.
>    다만, 재화등의 내용을 확인하기 위하여 포장 등을 훼손한 경우는 제외한다.
> 2. 소비자의 사용 또는 일부 소비로 재화등의 가치가 현저히 감소한 경우
> 3. 시간이 지나 다시 판매하기 곤란할 정도로 재화등의 가치가 현저히
>    감소한 경우
> 4. 복제가 가능한 재화등의 포장을 훼손한 경우
> 5. 용역 또는 「문화산업진흥 기본법」 제2조제5호의 디지털콘텐츠의
>    제공이 개시된 경우. 다만, 가분적 용역 또는 가분적 디지털콘텐츠로
>    구성된 계약의 경우에는 제공이 개시되지 아니한 부분에 대하여는
>    그러하지 아니하다.
> 6. 그 밖에 거래의 안전을 위하여 대통령령으로 정하는 경우
>
> **제3항** 소비자는 제1항 및 제2항에도 불구하고 재화등의 내용이
> 표시·광고의 내용과 다르거나 계약내용과 다르게 이행된 경우에는 그
> 재화등을 공급받은 날부터 3개월 이내, 그 사실을 안 날 또는 알 수
> 있었던 날부터 30일 이내에 청약철회등을 할 수 있다.
>
> **제4항** 제1항 또는 제3항에 따른 청약철회등을 서면으로 하는
> 경우에는 그 의사표시가 적힌 서면을 발송한 날에 그 효력이 발생한다.
>
> **제5항** 제1항부터 제3항까지의 규정을 적용할 때 재화등의 훼손에
> 대하여 소비자의 책임이 있는지 여부, 재화등의 구매에 관한 계약이
> 체결된 사실 및 그 시기, 재화등의 공급사실 및 그 시기 등에 관하여
> 다툼이 있는 경우에는 통신판매업자가 이를 증명하여야 한다.
>
> **제6항** 통신판매업자는 제2항제2호부터 제5호까지의 규정에 따라
> 청약철회등이 불가능한 재화등의 경우에는 그 사실을 재화등의 포장이나
> 그 밖에 소비자가 쉽게 알 수 있는 곳에 명확하게 표시하거나 시험 사용
> 상품을 제공하는 등의 방법으로 청약철회등의 권리 행사가 방해받지
> 아니하도록 조치하여야 한다. 다만, 제2항제5호 중 디지털콘텐츠에
> 대하여 소비자가 청약철회등을 할 수 없는 경우에는 청약철회등이
> 불가능하다는 사실의 표시와 함께 대통령령으로 정하는 바에 따라 시험
> 사용 상품을 제공하는 등의 방법으로 청약철회등의 권리 행사가
> 방해받지 아니하도록 하여야 한다.

### 적용 상태

- [실측] `return_exchange`는 제1항의 단순변심 7일과 제3항의 하자 3개월·30일을 반영한다.
- [실측] 제2항의 멸실·훼손, 가치 감소, 재판매 곤란, 복제물 포장 훼손, 디지털콘텐츠 제공 개시 등 청약철회 제한 사유는 Team 로직에 반영되지 않았다.
- [실측] 현재는 제안을 생성한 뒤 사람이 승인 전에 다시 확인한다.

## 개인정보 보호법 제2조·제15조·제17조

[실측][외부] 법령ID `011357`, 법령일련번호(MST) `270351`. 아래는 원본에 수록된 조회 원문이다. 출처 URL은 위 Open API 요청식과 같다.

> **제2조(정의)** "개인정보"란 살아 있는 개인에 관한 정보로서 다음
> 각 목의 어느 하나에 해당하는 정보를 말한다.
>
> 가. 성명, 주민등록번호 및 영상 등을 통하여 개인을 알아볼 수 있는 정보
> 나. 해당 정보만으로는 특정 개인을 알아볼 수 없더라도 다른 정보와
>    쉽게 결합하여 알아볼 수 있는 정보. 이 경우 쉽게 결합할 수 있는지
>    여부는 다른 정보의 입수 가능성 등 개인을 알아보는 데 소요되는
>    시간, 비용, 기술 등을 합리적으로 고려하여야 한다.
> 다. 가목 또는 나목을 가명처리함으로써 원래의 상태로 복원하기 위한
>    추가 정보의 사용·결합 없이는 특정 개인을 알아볼 수 없는 정보
>    (이하 "가명정보")
>
> "처리"란 개인정보의 수집, 생성, 연계, 연동, 기록, 저장, 보유, 가공,
> 편집, 검색, 출력, 정정(訂正), 복구, 이용, 제공, 공개, 파기, 그 밖에
> 이와 유사한 행위를 말한다.
>
> **제15조(개인정보의 수집·이용)** 개인정보처리자는 다음 각 호의
> 어느 하나에 해당하는 경우에는 개인정보를 수집할 수 있고 그 수집
> 목적의 범위에서 이용할 수 있다.
>
> 1. 정보주체의 동의를 받은 경우
> 2. 법률에 특별한 규정이 있거나 법령상 의무를 준수하기 위하여
>    불가피한 경우
> 3. 공공기관이 법령 등에서 정하는 소관 업무의 수행을 위하여
>    불가피한 경우
> 4. 정보주체와 체결한 계약을 이행하거나 계약을 체결하는 과정에서
>    필요한 경우
> 5. 정보주체 또는 그 법정대리인이 의사표시를 할 수 없는 상태에 있거나
>    주소불명 등으로 사전 동의를 받을 수 없는 경우로서 명백히
>    정보주체 또는 제3자의 급박한 생명, 신체, 재산의 이익을 위하여
>    필요하다고 인정되는 경우
> 6. 개인정보처리자의 정당한 이익을 달성하기 위하여 필요한 경우로서
>    명백하게 정보주체의 권리보다 우선하는 경우(개인정보처리자의
>    정당한 이익과 상당한 관련이 있고 합리적인 범위를 초과하지 아니하는
>    경우에 한한다)
> 7. 공중위생 등 공공의 안전과 안녕을 위하여 긴급히 필요한 경우
>
> **제17조(개인정보의 제공)** 개인정보처리자는 정보주체의 동의를
> 받거나 제15조제1항제2호·제3호·제5호·제7호의 어느 하나에 해당하는
> 경우 개인정보를 제3자에게 제공(공유를 포함한다)할 수 있다. 동의를
> 받을 때에는 개인정보를 제공받는 자, 개인정보의 이용 목적, 제공하는
> 개인정보의 항목, 개인정보의 보유·이용 기간, 동의를 거부할 권리가
> 있다는 사실 및 동의 거부에 따른 불이익이 있는 경우에는 그 불이익의
> 내용을 알려야 한다.

### 적용 상태

- [실측] `response_review.py`의 이름·전화번호·주민번호 형태 정규식은 제2조 가목의 식별정보 판정을 겨냥한다.
- [실측] 제2조 나목의 다른 정보와 쉽게 결합할 때의 식별 위험은 다루지 않는다. 단일 필드 정규식 매칭은 결합 위험 평가가 아니다.

## 미확보·후속 범위

- [미확보] 소비자24 분쟁 사례 5~10건은 법령 Open API 대상이 아니므로 별도 수집 방식이 필요하다.
- [미확보] 국세청·관세청 등 공공데이터포털 기반 다른 기관 API는 조사하지 않았다.
- [실측] 청약철회 불가 사유처럼 원문만 확보되고 Team 코드에는 반영되지 않은 조항이 있다. RAG 수록과 로직 반영은 별도 작업이다.

## 관계

- 원본: program/research/_법령원문_2026-08-20.md

===== FILE: dispute-cases.md =====
---
type: reference
title: 전자상거래 분쟁조정 사례
description: 소비자24에서 수집한 청약철회 관련 분쟁 4건의 판단과 조정 결과를 정리한다.
status: draft
tags: [contract, evaluation, governance]
---

## 결론

[실측][외부] 소비자24의 청약철회 검색 결과 336건 가운데 배송 지연, 단순변심, 하자 배송비, 환불 산정이라는 서로 다른 쟁점을 보여 주는 4건을 선별했다. 대표 표본은 아니며, 분쟁조정위 재배포 정책은 [미확보]이므로 원문 학습 데이터가 아니라 요약·참고 인용 자료로만 사용한다.

4건의 핵심 조정 결과는 다음과 같다.

- `trublMdatCaseSn=13117`: 하자로 인정하기 어려우면 반품 배송비는 소비자 부담이지만, 환불은 3영업일 이내에 해야 하며 지연 시 연 24% 지연이자가 적용된다.
- `trublMdatCaseSn=12290`: 디자인이 고정되고 사이즈만 선택하는 상품은 개별 주문생산 재화가 아니므로 “커스텀 상품 환불 불가” 안내가 무효이며, 배송 지연 청약철회와 환급이 인정됐다.
- `trublMdatCaseSn=11916`: 청약철회 반복 이력 자체는 제한 사유가 아니며, 훼손 입증 책임은 판매자에게 있다.
- `trublMdatCaseSn=13182`: 환불은 이미 지급받은 대금을 기준으로 하고, 사전 고지·동의된 반환 비용은 소비자가 부담할 수 있으며, 계약해제 사안의 위자료성 손해배상은 인정되지 않았다.

## 수집과 재현

- [실측][외부] 게시판: https://www.consumer.go.kr/user/ftc/consumer/trublmdatcase/116/
- [실측] 로그인과 API 키가 필요 없는 공개 페이지로 조사했다.
- [실측] 내용에 “청약철회”를 포함한 336건에서 전자상거래·쇼핑몰과 직접 관련된 4건을 선별했다.
- [실측] 원본 조사에는 사건개요, 당사자 주장, 판단, 결정사항 전문이 포함됐다.
- [실측] 개별 접근식: `selectTrublMdatCaseView.do?trublMdatCaseSn={번호}`

## 사례 1: 물품 하자로 인한 환불 청구

- [실측][외부] 사건번호: `trublMdatCaseSn=13117`
- [외부] 출처: 전자거래분쟁조정위원회, 분류: 의류세탁
- [외부] 사건: 의류의 스크래치·주름을 하자로 주장해 반품했으나 판매자는 하자가 아니라고 다퉜고, 왕복배송비 부담이 쟁점이 됐다.
- [외부] 적용 조문: 표시·광고와 다르거나 하자로 보기 어려우면 전소법 제17조제3항에 해당하지 않는다.
- [외부] 조정 결과: 반품 배송비는 소비자 부담이다. 환불 자체는 전소법 제18조제2항에 따라 3영업일 이내에 해야 하며, 지연하면 연 24% 지연이자를 부담한다.
- [실측] 적용: `return_exchange`는 하자 여부와 별도로 환불 처리 기한을 검사해야 한다. 하자 판정과 환불 지연은 서로 다른 쟁점이다.

## 사례 2: 구두 및 레깅스 배송 지연 환급 요구

- [실측][외부] 사건번호: `trublMdatCaseSn=12290`
- [외부] 출처: 한국소비자원, 분류: 의류세탁
- [외부] 사건: 판매자는 1:1 오더메이드 상품이라 청약철회가 불가능하다고 안내했지만 실제로는 디자인이 고정되고 사이즈만 선택하는 상품이었다.
- [외부] 적용 조문: 전소법 제17조제2항제5호와 시행령 제21조의 “소비자 주문에 의한 개별 생산 재화”에 해당하지 않는다고 판단했다.
- [외부] 조정 결과: 판매자의 “커스텀이라 환불 불가” 안내는 무효였다. 약속한 날짜를 지키지 못한 배송 지연으로 청약철회를 인정하고, 3영업일 내 환급과 지연 시 연 24% 지연배상금을 적용했다.
- [실측] 적용: `order_shipping`은 배송 지연에 따른 청약철회 가능성을 판단해야 한다. 판매자 정책 문구만으로 `waiting_input`이나 `escalated`를 생략할 수 없다.

## 사례 3: 인터넷 쇼핑몰 의류대금 환급 요구

- [실측][외부] 사건번호: `trublMdatCaseSn=11916`
- [외부] 출처: 한국소비자원, 분류: 의류세탁
- [외부] 사건: 소비자가 단순변심으로 청약철회하자 판매자는 과거의 반복 청약철회 이력을 이유로 거절했다.
- [외부] 적용 조문: 반복 이력은 전소법 제17조제2항의 멸실·훼손, 가치 감소, 재판매 곤란, 포장 훼손 등의 제한 사유가 아니다.
- [외부] 조정 결과: 반복 이력만으로 청약철회를 거부할 수 없으며, 재화 훼손의 입증 책임은 판매자에게 있다.
- [실측] 적용: `voc_store_manager`의 `similar_cases >= 2`는 우선순위를 올리는 신호로만 사용해야 하며 청약철회 거절 근거로 사용하면 안 된다.

## 사례 4: 해외구매대행 물품 하자 환불 요청

- [실측][외부] 사건번호: `trublMdatCaseSn=13182`
- [외부] 출처: 전자거래분쟁조정위원회, 분류: 가전생활용품
- [외부] 사건: 냄비세트 하자로 환불에 합의한 뒤 환불액 기준과 해외 배송비 공제 여부를 두고 다시 분쟁했다.
- [외부] 적용 조문: 전소법 제18조제1항·제2항에 따라 환불은 이미 지급받은 대금을 기준으로 한다.
- [외부] 조정 결과: 반환 비용을 사전에 고지하고 소비자 동의를 받았다면 소비자 부담이 유효하다. 계약해제 사안에서는 시간적·정신적 손해배상인 위자료가 인정되지 않으며, 이행지체에 따른 손해가 아니면 별도 손해배상 청구가 기각된다.
- [실측] 적용: 해외구매대행의 배송비 정산과 위자료 요구에 대해 `escalated` 또는 정중한 안내 후 `completed` 중 어떤 상태를 선택할지 판단하는 근거다.

## 조사 한계

- [실측] 4건은 대표 표본이 아니라 서로 다른 쟁점을 하나씩 보여 주도록 선별한 사례다.
- [미확보] 분쟁조정위 저작물의 재배포 정책을 확인하지 못했다.
- [미확보] 결제 오류, 개인정보 유출, 배송 중 분실 등 다른 쟁점 사례는 수집하지 않았다.
- [실측] 추가 검색에는 `searchCnd=3&searchWrd=` 내용 검색 방식을 사용할 수 있다.

## 관계

- 원본: program/research/_분쟁조정사례_2026-08-20.md

===== FILE: mt-methodology.md =====
---
type: research
title: 번역 모델 비교 검증 방법론
description: 번역 모델 순위 비교가 성립하는 조건과 검증된 표·한계를 정리한다.
status: draft
tags: [evaluation, data, documentation]
---

## 결론

[실측] 번역 모델 비교는 언어 부분집합, 테스트셋, 지표, 평가 방향, 보고 여부가 모두 같을 때만 성립한다. 특히 표 A의 WMT24++ 결과와 표 B의 FLORES-200 결과는 테스트셋과 지표가 다르므로 섞어 순위를 만들면 안 된다.

[실측] 외부에서 받은 TOP 15 표 2건 중 1건에는 논문에 없는 숫자가 다수 포함돼 있었다. MiLMMT-46-12B 영→한 XCOMET-XXL을 `97.85`로 적었지만 원문 값은 `89.07`이었다. 진짜 숫자와 부풀린 숫자가 섞인 표였다.

[외부] 공개 근거상 한국어에서는 Hunyuan 계열이 강하며 7B와 1.8B 모델 근거가 있다. Hy-MT2는 최신이지만 한국어 단독 근거는 [미확보]이므로 자체 데이터 평가 없이 도입을 판단하면 안 된다.

## 검증 절차

1. [실측] arXiv HTML 원문 5건을 로컬에 내려받았다.
2. [실측] 서브에이전트가 LaTeXML 표 마크업의 셀을 직접 파싱했다.
3. [실측] Codex가 같은 로컬 파일에서 독립적으로 다시 추출했다.
4. [실측] 두 추출본을 대조하고 영→한 핵심 표는 사람이 세 번째로 확인했다.
5. [실측] 불일치 항목은 원문을 다시 열어 판정했다.

[실측] 원문 HTML은 `.tmp/mt_papers/`에 있었으나 임시 폴더이므로 영구 보관은 전제하지 않는다.

## 검증 원문

원본에는 식별자만 있고 URL은 없다.

- [외부] arXiv `2602.11961` — Xiaomi, MiLMMT-46, `2026-02-12`; URL [미확보]
- [외부] arXiv `2605.22064` — Tencent, Hy-MT2, `2026-05-21`; URL [미확보]
- [외부] arXiv `2506.17080` — Unbabel, Tower+, `2025-06-20`; URL [미확보]
- [외부] arXiv `2511.07003` — NiuTrans, LMT-60, v1 `2025-11-10`, v2 `2026-04-24`; URL [미확보]
- [외부] Hugging Face 모델카드 `yanolja/YanoljaNEXT-Rosetta-12B-2510`; URL [미확보]

## 비교가 성립하는 조건 5가지

### 1. 언어 부분집합이 같아야 한다

[외부] MiLMMT-46 논문은 baseline을 MiLMMT와 겹치는 언어에서만 평가한다. `21`, `26`, `28`, `31`, `46`은 컬럼이 아니라 서로 다른 평가 집단이다.

[외부] Tower-Plus-9B의 `86.80`은 21개 언어, MiLMMT-46-12B의 `85.09`는 46개 언어 값이므로 직접 비교할 수 없다.

[외부] Tower+ Table 1도 7개·15개·24개 언어 컬럼으로 나뉜다. 72B의 15개 언어 `83.29`와 9B의 24개 언어 `84.38`을 비교하면 안 된다. 같은 컬럼에서는 7개 언어에서 72B `86.68`이 9B `86.25`보다 높고, 24개 언어에서는 9B `84.38`이 72B `83.74`보다 높다.

### 2. 지표 이름을 끝까지 확인해야 한다

[외부] XCOMET-XXL, COMETKiwi, COMET-22는 서로 다른 평가 모델이며 값의 범위도 다르다.

- MiLMMT-46: XCOMET는 XCOMET-XXL, COMETKiwi는 `wmt23-cometkiwi-da-xxl`, FLORES+ COMET은 `wmt22-comet-da`
- LMT-60: COMET-22와 SacreBLEU
- Hy-MT2: XCOMET-XXL, CometKiwi, GEMBA

### 3. 셀 안의 슬래시를 해석해야 한다

[외부] Hy-MT2의 `89.45 / 78.97 / 88.89`는 세 벤치마크가 아니라 FLORES-200 ZH⇔XX 셀 안의 XCOMET-XXL, CometKiwi, GEMBA 순 점수다.

### 4. 지표끼리 다른 결과를 낼 수 있다

[외부] Hunyuan-MT-7B는 영→한 XCOMET `92.21`로 1위지만 FLORES+ 영→한 spBLEU는 `24.57`로 하위권이고 같은 줄의 COMET은 `90.67`로 상위권이다. 출력 문체가 레퍼런스와 달라 생긴 것으로 보이며, 하나의 지표만으로 모델을 고르면 안 된다.

### 5. 논문이 보고하지 않은 값은 추정하지 않아야 한다

- [미확보] Hy-MT2 논문에는 부록과 언어별 표가 없어 한국어 단독 성능을 확인할 수 없다. 33개 언어 평균으로 추정하면 안 된다.
- [실측] TranslateGemma-27B는 MiLMMT 논문에 없으며 `27B`는 0회 등장한다.

## 표 A: WMT24++ 영→한

[실측][외부] 출처는 arXiv `2602.11961` 부록 Table 21과 Table 24이며 URL은 [미확보]이다. 같은 벤치마크·지표·방향이므로 직접 순위를 매길 수 있는 유일한 표다.

| 모델 | XCOMET-XXL | wmt23-cometkiwi-da-xxl |
|---|---:|---:|
| Hunyuan-MT-7B | 92.21 | 87.24 |
| HY-MT1.5-7B | 91.77 | 87.06 |
| Google Translate | 90.76 | 86.91 |
| HY-MT1.5-1.8B | 89.95 | 84.97 |
| TranslateGemma-12B | 89.88 | 85.85 |
| Gemini 3 Pro | 89.34 | 85.89 |
| MiLMMT-46-12B | 89.07 | 86.01 |
| GPT-5 | 88.85 | 86.06 |
| Gemini 2.5 Pro | 88.69 | 85.01 |
| MiLMMT-46-4B | 87.27 | 84.30 |
| Tower-PLUS-9B | 86.78 | 84.44 |
| TranslateGemma-4B | 85.97 | 82.51 |
| GemmaX2-28-9B | 84.69 | 81.87 |
| Seed-X-PPO-7B | 83.58 | 81.42 |
| Tower-PLUS-2B | 81.83 | 80.54 |
| MiLMMT-46-1B | 80.71 | 79.32 |
| GemmaX2-28-2B | 80.09 | 78.51 |
| Seed-X-Instruct-7B | 79.96 | 77.72 |

[외부] 이 조건에서 Hunyuan 계열 2개 모델은 GPT-5와 Gemini 3 Pro보다 한국어 XCOMET가 높다. HY-MT1.5-1.8B `89.95`는 TranslateGemma-12B `89.88`과 비슷하고 Tower-PLUS-9B `86.78`보다 높으므로 모델 규모만으로 성능을 판단할 수 없다.

## 표 B: FLORES-200 devtest 영→한

[실측][외부] 출처는 arXiv `2511.07003` 부록 Table 13이며 URL은 [미확보]이다.

| 모델 | COMET-22 | SacreBLEU |
|---|---:|---:|
| LMT-60-8B | 90.47 | 31.36 |
| LMT-60-4B | 90.47 | 29.38 |
| LMT-60-1.7B | 89.38 | 28.17 |
| LMT-60-0.6B | 87.55 | 26.61 |

[외부] 표 B는 표 A와 테스트셋과 지표가 모두 다르다. 두 표의 값을 나란히 놓고 모델 순위를 비교할 수 없다.

## 표 C: Hy-MT2 FLORES-200

[실측][외부] 출처는 arXiv `2605.22064` Table 2이며 URL은 [미확보]이다. 값은 33개 언어 XX⇔XX 전체 방향 평균이고 한국어 단독 점수는 [미확보]이다.

| 모델 | XCOMET-XXL / CometKiwi / GEMBA |
|---|---|
| Hy-MT2-30B-A3B | 87.47 / 76.34 / 88.79 |
| Hy-MT2-7B | 86.89 / 76.03 / 87.23 |
| Hy-MT2-1.8B | 79.77 / 73.41 / 78.64 |

[외부] 같은 표에서 Tower-Plus-72B는 `70.02 / 65.53 / 67.85`다. Tower+는 24개 언어만 지원하므로 33개 언어 평가는 지원 범위를 벗어나 불리하다.

## 표 D: Tower+ WMT24++

[실측][외부] 출처는 arXiv `2506.17080` Table 1이며 URL은 [미확보]이다. 지표는 xCOMET-XXL이다.

| 모델 | 7개 언어 | 15개 언어 | 24개 언어 |
|---|---:|---:|---:|
| Tower+ 2B | 81.88 | 78.42 | 79.13 |
| Tower+ 9B | 86.25 | 83.57 | 84.38 |
| Tower+ 72B | 86.68 | 83.29 | 83.74 |

[외부] 72B의 15개 언어 값과 9B의 24개 언어 값을 비교하면 안 된다. 같은 컬럼끼리만 비교해야 한다.

## 표 E: YanoljaNEXT-Rosetta WMT24++

[실측][외부] 출처는 Hugging Face 모델카드 `yanolja/YanoljaNEXT-Rosetta-12B-2510`이며 URL은 [미확보]이다. 베이스는 `google/gemma-3-12b-pt`, 규모는 12B이고 지표는 CHrF++ 하나뿐이다.

| 모델 | CHrF++ |
|---|---:|
| yanolja/YanoljaNEXT-Rosetta-12B-2510 | 37.36 |
| openai/gpt-4o | 36.08 |
| google/gemini-2.5-flash | 35.25 |
| yanolja/YanoljaNEXT-Rosetta-12B | 34.75 |
| yanolja/YanoljaNEXT-Rosetta-20B | 33.87 |
| google/gemini-2.0-flash-001 | 33.81 |
| openai/gpt-oss-120b | 31.51 |
| google/gemma-3-27b-it | 30.05 |
| google/gemma-3-12b-pt | 29.31 |

[외부] 모델카드에서는 Rosetta-12B-2510이 GPT-4o보다 높다. CHrF++는 문자 n-gram 겹침 기반이며 의미 정확도를 직접 측정하는 지표는 아니다.

## WMT25 자기 보고와 공식 사람 평가

- [외부] Tencent 논문 arXiv `2509.05209` 초록은 Hunyuan-MT가 WMT25의 31개 중 30개 카테고리에서 1위라고 자체 보고한다. URL [미확보].
- [외부] WMT25 공식 findings `ACL Anthology 2025.wmt-1.22`는 30개 언어쌍과 60개 시스템을 다뤘다. 공식 ESA 사람 평가는 15개 언어쌍에서 수행됐다. URL [미확보].
- [외부] 전체 최고인 Google Gemini 2.5 Pro는 15개 중 14개에서 승자군에 들었다.
- [외부] Tencent 출전작 Shy-hunyuan-MT는 constrained 부문 최고였고 15개 중 11개에서 승자군이었다.
- 자기 보고와 제3자 평가를 구분해야 한다.

## Tencent 모델 계보

[외부] `Hunyuan-MT(2025-09, WMT25 출전) → HY-MT1.5(2025-12-30) → Hy-MT2(2026-05-21)` 순이다. 이름이 비슷해도 서로 다른 세대다. 출처 URL은 [미확보]이다.

## 로컬 벤치마크 라벨 오류

- [실측] 대상은 `datasets/mt/olist_reviews_mt_bench/REPORT.md`이며 작성 당시 경로는 `program/research/archive/2026-08-20/mt_bench_results/`였다.
- [실측] Olist 리뷰 300쌍, PT→EN, GGUF Q4_K_M 모델 15개를 대상으로 sacrebleu BLEU와 chrF2를 측정했다.
- [실측] 이후 추가된 PT→KO 결과는 `hangul_ratio` 기반이므로 이 지적의 대상이 아니다.
- [실측] 마지막 두 열의 `원 리더보드 COMET-22`는 XCOMET-XXL, `원 리더보드 BLEU`는 COMETKiwi로 고쳐 읽어야 한다.
- [실측] 두 열은 영→한 값인데 나머지는 PT→EN 값이다. `92.21 / 87.24`, `86.78 / 84.44`, `89.07 / 86.01`이 표 A와 각각 일치한다.
- [실측] 잘못된 라벨은 Hunyuan-MT-7B가 리더보드 BLEU `87.24`에서 로컬 BLEU `26.53`으로 폭락한 것처럼 보이게 한다.
- [외부] 실제 FLORES+ 영→한 spBLEU는 `24.57`이다. 영→한 `24.57`과 PT→EN `26.53`은 직접 비교할 수 없다.
- [실측] REPORT는 깨진 출력 3건의 원인을 확인했고 LMT-60-8B의 thinking 문제를 `think:false`로 해결했다.
- [실측] 양자화 방식과 언어쌍이 달라 논문·리더보드와 직접 비교할 수 없다는 한계를 REPORT도 명시한다.
- [실측] 원본 REPORT는 수정하지 않았다.

## 한계

- [미확보] TranslateGemma 기술보고서 arXiv `2601.09012`에는 HTML 판이 없어 표를 추출하지 못했다. 이 문서의 TranslateGemma 값은 Xiaomi 논문의 재평가 값이다.
- [실측] LMT-60의 0.6B와 1.7B는 본문 집계표가 아니라 부록 언어별 표에서 확인했다.
- [실측] 수치 기준일은 `2026-08-19`다.

## 실무 결론

- [외부] 현재 공개된 한국어 근거에서는 Hunyuan 계열이 가장 강하며 7B와 1.8B 근거가 있다.
- [미확보] 최신 Hy-MT2의 한국어 단독 성능은 공개되지 않았다.
- 도입 전 자체 데이터로 다시 평가해야 하며 논문 수치는 해당 논문의 테스트셋 안에서만 해석해야 한다.

## 관계

- 원본: program/research/_번역모델_조사.md

===== FILE: stack-sources.md =====
---
type: reference
title: A-COP 기술 스택 공식 문서
description: 활용 기술의 공식 URL과 HTTP 200 확인 결과 및 링크 제외 사유를 정리한다.
status: draft
tags: [architecture, api, documentation]
---

## 결론

[실측] 아래 18개 공식 URL은 `2026-08-17`에 `curl`로 요청해 모두 HTTP `200`을 확인했다. RAG·GraphRAG 등 5개 항목에는 공식 사이트가 없거나 A-COP 내부 설계·구성요소이므로 링크를 걸지 않았다.

## 공식 문서

| 기술 | 역할 | 공식 URL과 확인 결과 |
|---|---|---|
| Python | 코어 1 · MVP | [실측][외부] https://www.python.org/ — HTTP 200, 2026-08-17 |
| LangGraph | 코어 1 · MVP | [실측][외부] https://langchain-ai.github.io/langgraph/ — HTTP 200, 2026-08-17 |
| PostgreSQL | 코어 1 · MVP | [실측][외부] https://www.postgresql.org/ — HTTP 200, 2026-08-17 |
| Redis | 코어 1 · Phase 2 | [실측][외부] https://redis.io/ — HTTP 200, 2026-08-17 |
| RabbitMQ | 코어 1 · Phase 2 | [실측][외부] https://www.rabbitmq.com/ — HTTP 200, 2026-08-17 |
| Apache AGE | 코어 1 · Phase 2 | [실측][외부] https://age.apache.org/ — HTTP 200, 2026-08-17 |
| Neo4j | 코어 1 · Phase 2 | [실측][외부] https://neo4j.com/ — HTTP 200, 2026-08-17 |
| FastAPI | 코어 2 · MVP | [실측][외부] https://fastapi.tiangolo.com/ — HTTP 200, 2026-08-17 |
| OpenAPI | 코어 2 · MVP | [실측][외부] https://www.openapis.org/ — HTTP 200, 2026-08-17 |
| MCP | 코어 2 · MVP | [실측][외부] https://modelcontextprotocol.io/ — HTTP 200, 2026-08-17 |
| A2A | 코어 2 · MVP | [실측][외부] https://a2a-protocol.org/ — HTTP 200, 2026-08-17 |
| OAuth 2.0 | 코어 2 · Phase 2 | [실측][외부] https://oauth.net/2/ — HTTP 200, 2026-08-17 |
| OpenID Connect | 코어 2 · Phase 2 | [실측][외부] https://openid.net/developers/how-connect-works/ — HTTP 200, 2026-08-17 |
| pgvector | 모델 · MVP | [실측][외부] https://github.com/pgvector/pgvector — HTTP 200, 2026-08-17 |
| pytest | 검증 & 프론트 · MVP | [실측][외부] https://docs.pytest.org/ — HTTP 200, 2026-08-17 |
| AWS | 배포 · Phase 2 | [실측][외부] https://aws.amazon.com/ — HTTP 200, 2026-08-17 |
| Docker | 배포 · Phase 2 | [실측][외부] https://www.docker.com/ — HTTP 200, 2026-08-17 |
| React | 검증 & 프론트 · MVP | [실측][외부] https://react.dev/ — HTTP 200, 2026-08-17 |

## 링크를 걸지 않은 항목

| 항목 | 이유 |
|---|---|
| RAG · GraphRAG | [실측] 특정 제품이 아니라 검색 증강 방식의 이름이므로 공식 사이트가 없다. |
| API Key + Scope | [실측] A-COP Gateway의 권한 설계이며 외부 표준이 아니다. |
| golden / holdout harness | [실측] 내부 평가 하네스이며 `final_project_sample/eval/`에 있다. |
| bootstrap · McNemar | [실측] 통계 검정 방법이며 제품이 아니다. |
| Registry · Adapter | [실측] 내부 설계의 구성요소 이름이며 v7 §21 계약을 따른다. |

## 근거 문서 구분

[실측] 이 문서는 공식 문서를 어디에서 보는지 기록한다. 프로토콜의 사실 근거는 `_출처검증_2026-08-17.md`의 H 그룹인 H1 A2A, H2 AP2, H3·H4 UCP, H5 MCP에 별도로 있다.

## 관계

- 원본: program/research/_기술스택_공식문서_2026-08-17.md

===== FILE: learning-methodology.md =====
---
type: research
title: 대규모 코드베이스 학습 게임 방법론
description: acop_dojo에 적용할 교수법·게임 설계·자동화 원칙과 근거의 한계를 정리한다.
status: draft
tags: [architecture, evaluation, testing, documentation]
---

## 결론

적합한 형태는 강의에 점수와 배지를 붙이는 방식이 아니라 작은 실제 시스템 실행부터 실제 저장소 변경까지 이어지는 검증 가능한 임무의 연쇄다. 핵심 루프는 `관찰 → 예측 → 실행/추적 → 설명 → 수정 → 회고`다.

지도는 디렉터리 트리가 아니라 실행·데이터·상태·도구·권한·평가 경로를 겹쳐 보여 주는 지식 지도여야 한다. [외부] 2025~2026년에는 저장소 기반 위키·코드 투어·이해 문항 자동 생성 기술이 등장했다. [미확보] 임의의 대규모 저장소를 검증된 게임형 코스로 완전 자동 변환한 성숙 사례는 확인하지 못했다.

현실적인 방식은 정적·동적 분석으로 구조를 잡고 LLM이 후보 퀘스트를 만들며 테스트·원본 링크·전문가 검토로 정답과 난이도를 보증하는 반자동 파이프라인이다.

## 핵심 교수법 10가지

### 1. Karpathy식 직접 구축

- 핵심: 작지만 작동하는 모델을 직접 만들고 내부를 층별로 확장한다.
- [외부] 출처: [Zero to Hero](https://karpathy.ai/zero-to-hero.html), [nanoGPT](https://github.com/karpathy/nanoGPT), 2025년 [nanochat](https://github.com/karpathy/nanochat), [Eureka Labs](https://eurekalabs.ai/)
- 적용: `요청 → 오케스트레이터 → 도구 → 관찰 → 응답 → 평가` 미니 에이전트를 먼저 실행하고 구성요소를 실제 구현으로 교체한다.
- [미확보] LLM101n 완성 코스의 효과 평가는 확인하지 못했다.

### 2. fast.ai의 top-down whole game

- 핵심: 유용한 전체 작업을 먼저 경험하고 같은 전체를 반복하면서 고수준 API에서 저수준 구현으로 내려간다.
- [외부] 출처: [fast.ai teaching philosophy](https://www.fast.ai/posts/2016-10-08-teaching-philosophy.html), [Deep Learning from the Foundations](https://www.fast.ai/posts/2019-06-28-course-p2v3.html)
- 적용: 대표 사용자 시나리오를 먼저 성공시키고 호출 그래프, 상태·복구, 비용·보안을 같은 시나리오에 겹친다.

### 3. Making Learning Whole 7원칙

- 핵심: 초보자용 전체 게임, 가치, 어려운 부분, 전이, 숨은 구조, 협업, 자기조절을 함께 설계한다.
- [외부] 출처: [Making Learning Whole](https://pz.harvard.edu/resources/making-learning-whole-how-seven-principles-of-teaching-can-transform-education), [Education at Bat](https://www.gse.harvard.edu/ideas/usable-knowledge/09/01/education-bat-seven-principles-educators)
- 적용: 전체 제품 흐름을 초보자 리그로 삼고 비결정성·동시성·도구 실패를 보스전으로 분리한다.

### 4. 실패·평가 중심 AI 엔지니어링 교육

- 핵심: 실제 실패를 관찰하고 평가 단위를 만들며 개선한다.
- [외부] 출처: [LLM applications for production](https://huyenchip.com/2023/04/11/llm-engineering.html), [AI Evals](https://hamel.dev/notes/llm/evals/index.html), [LLM systems patterns](https://eugeneyan.com/writing/llm-patterns/), [How coding agents work](https://simonwillison.net/guides/agentic-engineering-patterns/how-coding-agents-work/)
- 적용: 트레이스 분류, 실패 가설, 평가 케이스, 수정, 회귀 방지 순으로 진행하고 재현 가능성·근거·평가 오류·회귀 방지를 채점한다.

### 5. 단순 에이전트 패턴부터 확장

- 핵심: 증강 LLM에서 시작해 체이닝·라우팅·병렬화·오케스트레이션을 필요할 때만 추가한다.
- [외부] 출처: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), [Agents SDK quickstart](https://openai.github.io/openai-agents-python/quickstart/), [orchestration](https://openai.github.io/openai-agents-python/multi_agent/), [Google ADK 튜토리얼](https://google.github.io/agents-cli/guide/hands-on-tutorial/)
- 적용: 단일 호출을 이해한 뒤 멀티에이전트를 해금하고 비용·지연·정확도로 복잡성을 정당화한다.

### 6. 인지적 도제와 스캐폴딩 페이딩

- 핵심: 전문가 사고를 보여 주고 발판을 제공한 뒤 도움을 제거한다.
- [외부] 출처: [Cognitive Apprenticeship](https://www.ideals.illinois.edu/items/18043), [Making Thinking Visible](https://www.aft.org/ae/winter1991/collins_brown_holum)
- 적용: 전문가 고스트에서 시작해 시작 파일·부분 그래프만 남기고 마지막에는 탐색 계획과 근거를 제출하게 한다.

### 7. 가설 주도 프로그램 이해

- 핵심: 질문과 가설을 만들고 도메인 모델과 실제 제어 흐름 사이를 오간다.
- [외부] 출처: [Cognitive processes](https://doi.org/10.1016/0164-1212(87)90032-X), [Program comprehension](https://doi.org/10.1109/2.402076), [large-scale 연구](https://doi.org/10.1109/32.508315)
- 적용: 원인 가설을 먼저 쓰고 검색·로그·실행으로 지지하거나 폐기한다.

### 8. 능동적 코드 읽기와 코드 투어

- 핵심: 코드 읽기를 질문, 경로 선택, 요약, 실행 확인이 결합된 과업으로 만든다.
- [외부] 출처: 2025년 [data-enhanced active reading](https://doi.org/10.1186/s41039-025-00299-2), [Linear walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/)
- 적용: 파일 읽기 대신 입력이 모델 인자로 바뀌는 지점을 찾게 하고 파일·심볼·실행 증거·요약을 요구한다.

### 9. notional machine과 실행 추적

- 핵심: 문법보다 시스템의 단계별 상태 변화를 명시한다.
- [외부] 출처: [Some Difficulties of Learning to Program](https://doi.org/10.2190/3LFX-9RRF-67T8-UVK9), [학생 코드 추적 전략 연구](https://cseweb.ucsd.edu/~bsimon/pubs/papers/icer2005_strats.pdf)
- 적용: 대화 상태, 컨텍스트, 큐, 도구, 권한, 재시도, 캐시, 비용의 다음 상태를 예측한 뒤 실제 트레이스를 공개한다.

### 10. Parsons 문제와 점진적 구성

- 핵심: 빈 편집기에서 작성하기 전에 코드 조각을 선택·배열해 생성 부담을 낮춘다.
- [외부] 출처: [Python Grids](https://doi.org/10.1007/s40593-018-0156-y), [Exercism FAQ](https://exercism.org/docs/using/faqs)
- 적용: 정답 조각 제공, distractor, 빈칸 완성, 독립 변경 순으로 지원을 줄인다.

## 추가 교수법과 게임 설계

### 11. 결함 주입과 mutation testing

[외부] 작은 의미 변화의 실패를 찾고 테스트를 쓰는 방식이다. 출처: [Mutation Testing for Teaching](https://doi.org/10.58459/icce.2014.413), [Decoding Debugging Instruction](https://doi.org/10.1145/3690652), 2025년 [교육용 mutation 연구](https://www.iris.unina.it/handle/11588/1005441). 권한 확인 순서, idempotency, 도구 결과 기록 오류를 변이로 만들고 실패 재현·가설·최소 테스트·수정 순으로 해결한다.

### 12. 작은 실제 과업과 buddy

[외부] 첫 주부터 좁은 실제 변경을 동료와 수행한다. 출처: Dropbox [Engineer onboarding](https://dropbox.tech/culture/a-day-in-the-life-engineer-onboarding-at-dropbox), Microsoft [온보딩 사례](https://arxiv.org/abs/2103.05055), Google SRE [온콜 학습 경로](https://sre.google/sre-book/accelerating-sre-on-call/). 최종 과제는 실제 backlog의 저위험 변경으로 한다. [미확보] 대형 회사가 코드베이스 온보딩 전체를 장기 게임화해 효과를 계량한 확실한 1차 사례는 없다.

### 13. 재미를 패턴 학습으로 보기

[외부] 외적 보상보다 시스템 패턴 발견과 변형 적용을 중심으로 한다. 출처: [Theory of Fun 강연](https://www.raphkoster.com/games/presentations/theory-of-fun/), [공식 사이트](https://www.theoryoffun.com/). 코드베이스 교육에 대한 직접 실험은 [미확보]이다.

### 14. desirable difficulties와 인출·간격·교차 연습

[외부] 인출, 간격 반복, 유사 문제 혼합은 장기 보존과 전이에 유리할 수 있다. 출처: [Bjork Lab](https://bjorklab.psych.ucla.edu/research/), [The Critical Importance of Retrieval](https://doi.org/10.1126/science.1152408). 1·3·7일 뒤 다른 모듈에서 원리를 다시 찾게 하되 실패율이 높으면 힌트를 복구한다.

### 15. mastery learning과 AI 튜터

[외부] 시간보다 수행으로 숙달을 확인한다. 출처: [2 Sigma Problem](https://doi.org/10.3102/0013189X013006004). 2시그마를 모든 환경의 보장치로 해석하면 안 된다. 레벨 해금은 정상·타임아웃·권한 거부 트레이스 설명과 테스트 통과로 판단한다.

### 16. roguelike·metroidvania 지식 구조

[외부] 반복 탐험과 능력 기반 재방문을 적용한다. 출처: [Metroidvania design](https://www.gamedeveloper.com/design/making-sense-of-metroidvania-game-design), [Vim Adventures](https://vim-adventures.com/). [미확보] 코드베이스 학습에서 우월하다는 직접 실증은 없다.

### 17. pointsification 피하기

[외부] 점수·배지·순위표만 붙이면 의미와 자율성을 약화할 수 있다. 출처: [Humanistic Design](https://doi.org/10.1177/1056492618790912), [Meaningful Play](https://talks.ui-patterns.com/videos/meaningful-play-getting-gamification-right), [교육 게임화 부정 효과](https://doi.org/10.1016/j.infsof.2022.107142). 능력 증거를 진행 표시로 사용하고 전역 순위표는 기본값에서 뺀다.

## 실제 개발자용 게임과 도구

### 18. Build Your Own X와 작은 퍼즐

[외부] 작은 호환 단계로 실제 시스템을 재구현하고 외부 테스트로 검증한다. 출처: [CodeCrafters](https://app.codecrafters.io/concepts/overview), [Redis 과정](https://github.com/codecrafters-io/build-your-own-redis), [Advent of Code 2025](https://adventofcode.com/2025/about). 2025년 Advent of Code는 전역 순위표를 제거했다.

### 19. Boot.dev와 Exercism

[외부] 짧은 과제, 자동 테스트, 해금, 개인화 복습, 답을 직접 주지 않는 도움을 결합한다. 출처: [Training Grounds](https://www.boot.dev/training), [Boots](https://www.boot.dev/lessons/e4fac74c-9d67-41ad-a85c-c579cb3ad76f), [Exercism Getting Started](https://exercism.org/docs/using/getting-started).

### 20. 실제 도구를 게임 입력으로 사용

[외부] 실제 조작을 게임 입력으로 만들어 연습과 전이를 분리하지 않는다. 출처: [Oh My Git!](https://ohmygit.org/), [Vim Adventures](https://vim-adventures.com/), [Regex Crossword](https://regexcrossword.com/), [TIS-100](https://zachtronics.com/tis-100/). 실제 git·테스트·검색·트레이스·디버거를 사용한다.

### 21. 코드로 플레이하는 지속 세계

[외부] 코드를 작성하고 장기 행동을 관찰해 설계·피드백·최적화를 반복한다. 출처: [Screeps](https://docs.screeps.com/introduction.html), [Robocode](https://robocode.dev/articles/intro). 에이전트 정책을 샌드박스에 배치하고 성공률·비용·지연·안전·복구를 관찰한다.

### 22. CTF·Game Day·장애 대응

[외부] 현실적 장애, 역할 분담, 실제 도구, 회고를 사용한다. 출처: AWS [chaos engineering](https://aws.amazon.com/blogs/security/how-to-use-chaos-engineering-in-incident-response/), Google SRE [Incident Response](https://sre.google/workbook/incident-response/), GitHub [Secure Code Game](https://securitylab.github.com/secure-code-game/). 모델 지연, 잘못된 도구 출력, prompt injection, 큐 적체를 주입한다.

### 23. CI 기반 품질 퀘스트

[외부] 실제 커밋과 CI 결과에서 개선 임무를 생성한다. 출처: Jenkins [Gamekins](https://github.com/jenkinsci/gamekins-plugin), [논문](https://arxiv.org/abs/2202.06562), [교육 적용 연구](https://arxiv.org/abs/2401.17740). 교육 연구는 결과 개선을 보고했지만 인과 일반화에는 추가 검증이 필요하다.

## AI 튜터와 저장소 기반 코스

### 24. 코드 인지형 단계적 AI 힌트

[외부] 과제·현재 코드·실패 테스트를 보고 다음 한 걸음을 제안한다. 출처: 2025년 [AI Hints](https://blog.jetbrains.com/education/2025/06/02/ai-hints-plugin/), [프로그래밍 교육 LLM 설문](https://aclanthology.org/2025.hcinlp-1.21/). 힌트는 `관찰 요청 → 부분 힌트 → 전략 힌트 → 제한 예시` 순으로 제공한다.

### 25. 코드 이해 문항 자동 생성

[외부] 실제 코드에서 개인화 문항을 만들 수 있지만 타당도와 정답 근거 검증이 필요하다. 출처: 2025년 [AutoMCQ](https://arxiv.org/abs/2505.16430), [Testing Code Comprehension using GenAI](https://doi.org/10.1145/3754508.3754532). 저장소 전체 코스 생성의 입증은 [미확보]이다.

### 26. 살아 있는 저장소 위키와 다이어그램

[외부] 저장소 위키·검색·코드 링크·채팅·다이어그램 자동화가 등장했다. 출처: 2025년 [DeepWiki](https://cognition.com/blog/deepwiki), 2025년 [Code Wiki](https://developers.googleblog.com/ko/introducing-code-wiki-accelerating-your-code-understanding/), 2026년 [CodeWiki 평가](https://aclanthology.org/2026.findings-acl.288/). 문서 생성과 학습 성취는 다르므로 코드·테스트·트레이스로 검증한 항목만 발견 처리한다.

### 27. 정적 그래프와 LLM 코드 투어

[외부] 호출·의존 그래프로 핵심 경로를 고른 뒤 LLM이 설명한다. 출처: [LLM-Generated Code Tours](https://xdevroey.be/publication/balfroid-2024/balfroid-2024.pdf), 2025년 [RepoMaster](https://arxiv.org/abs/2505.21577), 2025년 [Multi-agent Onboarding Assistant](https://doi.org/10.1145/3696630.3728611). 모든 투어 단계에 원본 심볼을 남긴다.

### 28. repo-to-course 반자동 파이프라인

[외부] 2026년 현재 가능한 것은 자동 초안이며 신뢰할 코스에는 분석·실행 검증·난이도 보정·전문가 승인이 필요하다. 출처: [Linear walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/), 2026년 [(Im)Paired Programming](https://arxiv.org/abs/2607.26375). 후자는 코딩 에이전트의 자동 수락 같은 저노력 상호작용이 낮은 이해와 연결됐다고 보고한다.

파이프라인은 `스냅샷 → 빌드/테스트 → 정적·동적 그래프 → 개념·선행 관계 → 퀘스트 후보 → 실행 oracle → 전문가 검수 → 파일럿 → 변경 감지`다.

## 채택 원칙 10개

1. 첫 30분 안에 축소된 전체 시스템을 실행시킨다.
2. 모든 퀘스트를 테스트·트레이스·재현 명령·코드 링크 같은 실행 증거로 끝낸다.
3. 관찰·예측·실행·설명·수정·회고를 핵심 루프로 고정한다.
4. 디렉터리보다 호출·데이터·상태·도구·권한·평가 관계로 지도를 만든다.
5. 전문가 사고를 보여 준 뒤 발판과 힌트를 점진적으로 제거한다.
6. 실제 장애·코드 리뷰·오개념에서 mutant와 보스전을 만든다.
7. 시간·XP가 아니라 다른 맥락으로 전이되는 수행으로 숙달을 판정한다.
8. 같은 개념을 1·3·7일 뒤 다른 문제 형식으로 인출하게 한다.
9. 게임성은 패턴 발견과 의미 있는 선택에서 만들고 PBL은 보조로만 쓴다.
10. LLM은 생성자·코치로 쓰고 정답은 분석·실행 oracle·전문가 검수로 승인한다.

## 확인 범위와 불확실성

- [미확보] Eureka Labs LLM101n의 완성 강의 전체와 학습 효과 평가
- [미확보] 대형 회사가 대규모 코드베이스 온보딩을 장기간 게임화해 효과를 계량한 공개 1차 사례
- [미확보] roguelike·metroidvania가 코드베이스 학습에 특별히 우월하다는 직접 실증
- [미확보] 임의 저장소를 완전하고 검증된 코스로 자동 변환했다는 근거
- [외부] 작은 실제 프로젝트, codelab, buddy, 재난 역할극과 자동 위키·질문·코드 투어의 개별 근거는 확인됐다.

## 관계

- 원본: program/research/학습게임_방법론_조사.md

===== FILE: design-review.md =====
---
type: report
title: acop_dojo 학습 게임 설계 검수
description: 현재 설계의 치명적 약점과 근거 수준 및 변경 권고를 정리한다.
status: draft
tags: [architecture, evaluation, testing]
---

## 결론

[실측] `2026-08-30` 기준 현재 설계는 그대로 구현할 단계가 아니다. 가장 치명적인 문제는 실행 성공, pytest 통과, 호출 순서 정답을 코드베이스 이해의 증거로 간주하는 구성타당도 오류다. 이 오라클들은 행동의 정오를 검증하지만 계약·상태·권한·변경 파급효과에 대한 정신모형 형성은 검증하지 않는다. 이는 원본 작성자의 추론이다.

[미확보] 현재 5단계 전체가 코드베이스 이해 교육법으로 검증된 사례는 찾지 못했다. 개별 부품에는 근거가 있지만 뮤테이션, 고정 1·3·7일 반복, 읽기 전용 의존 그래프는 주장하는 학습 효과보다 근거가 약하다.

## 치명적 약점 7가지

### 1. 초보자에게도 먼저 예측하게 하는 일괄 정책

- [외부] 2024년 실험에서는 코드 예측 집단이 일반 설명 후 코딩 집단보다 학습평가와 정서 반응에서 나았다. POE는 `예측 → 관찰 → 차이 설명` 구조다. 출처: [Prediction versus production](https://doi.org/10.1016/j.learninstruc.2023.101871)
- [외부] prequestion 메타분석에서 질문한 내용의 효과는 `g=0.54`, 묻지 않은 내용으로의 일반화는 `g=0.04`였다. 출처: [Guessing as a learning intervention](https://doi.org/10.3758/s13423-023-02353-8)
- [외부] 53개 연구·166개 비교 메타분석에서 문제 해결 후 수업은 개념·전이에 `g=0.36`의 이점이 있었지만 절차 지식에는 차이가 없었다. 출처: [Sinha & Kapur, 2021](https://doi.org/10.3102/00346543211019105), [How to make failure productive](https://www.sciencedirect.com/science/article/pii/S0959475218304997)
- [실측] 현재 설계에는 입문 진단, worked example, 단계적 fading이 없다. 56개 앱 모듈을 처음 보는 사람에게 즉시 예측을 요구하면 탐색 부하를 학습으로 오인할 수 있다.
- [외부] 초보자에게 worked example이 유리하고 숙련도가 높아지면 지도를 줄여야 한다. 출처: [Worked examples](https://www.sciencedirect.com/science/article/pii/S0361476X1000055X)
- 변경 방향: 완전 초보자는 해설 사례→completion→독립 예측, 경험자는 예측→즉시 트레이스→차이 설명, 고숙련자는 장애·변경 가설 과제로 분기한다.

### 2. 예측 후 공개가 정답 맞히기로 퇴화할 위험

- [미확보] A-COP과 정확히 같은 형식이 정답 맞히기로 퇴화한 직접 사례는 찾지 못했다.
- [외부] 2025년 Parsons 문제 검토는 성공해도 목표 개념에 주의하지 않는 selective-attention 위험을 지적한다. 출처: [Parsons problems](https://doi.org/10.1145/3769994.3770032)
- [실측] 호출 이름이나 반복 패턴 암기만으로 통과할 수 있다.
- 통과에 추가할 질문: 다른 후보 호출이 불가능한 이유, 간선을 활성화한 상태·권한, 입력 변경 시 분기, 보지 않은 모듈에서의 적용.
- [외부] 자기설명 프롬프트의 평균 효과는 약 `g=0.55`였고 개념 설명이 단순 수행 점검보다 강했다. 출처: [Self-explanation meta-analysis](https://www.clearinghouse.edu.tum.de/wp-content/uploads/2023/09/CHU-KR-25_ENG_Bisra_2018_Selbsterklaerungen.pdf), [source-code comprehension](https://cdn.aaai.org/ocs/18479/18479-79419-1-PB.pdf)
- [미확보] 자기설명과 예측 퀴즈를 코드베이스 규모에서 직접 비교한 연구는 없다. 예측은 자기설명의 입력으로 격하한다.

### 3. 뮤테이션이 구조 이해보다 테스트 설계를 가르칠 가능성

- [외부] 뮤테이션 교육 근거는 테스트 작성, mutation score, mutant-state propagation 이해에 집중된다.
- [외부] 2025년 FSE 연구 대상은 `52~1,010 LOC` 자기완결 Java 클래스였고 평가는 테스트 수, 커버리지, mutation score, equivalent mutant 설명이었다. `18k`줄 다중 모듈 이해 전이는 측정하지 않았다. 출처: [Potter et al., FSE 2025](https://doi.org/10.1145/3696630.3727240)
- [외부] 산업 자료도 테스트 품질 향상을 지지하지만 아키텍처 학습 근거는 아니다. 출처: [Long Term Effects of Mutation Testing](https://research.google/pubs/long-term-effects-of-mutation-testing/)
- 편법 위험: 테스트 이름·assertion에서 파일 추론, fixture·mock 암기, 실패 빈도의 통계적 연관 암기, 같은 실패 집합에서 임의 정답 선택.
- [미확보] 이 편법이 실제 A-COP에서 발생한다는 직접 근거는 없다. 원본 작성자의 추론이다.
- 변경 방향: 보지 않은 테스트, 다른 모듈, 새 입력에서 전이를 평가한다.

### 4. 테스트 60개만으로 뮤테이션 게임 성립을 판단할 수 없음

- [실측] `60개 / 18,165줄`은 약 `3.3개 테스트/KLOC`지만 테스트 개수는 커버리지나 오라클 강도를 나타내지 않는다.
- 유효한 실패 신호 조건: 변형 코드가 실행되고, 내부 상태가 감염되며, 차이가 assertion까지 전파돼야 한다.
- [외부] state propagation과 equivalent mutant 문제가 있다. 출처: [FSE 2025](https://doi.org/10.1145/3696630.3727240)
- [외부] `mutmut`은 covered line 옵션을 제공하며 공통 함수에 수백 테스트가 매달리면 느리고 해석하기 어렵다고 경고한다. 출처: [mutmut 문서](https://github.com/boxed/mutmut/blob/main/README.rst)
- [외부] 2024년 `3,302개` mutant 쌍 연구는 기존·LLM 기반 equivalent 탐지법의 일반화 한계를 보고했다. 출처: [ISSTA 2024](https://doi.org/10.1145/3650212.3680395)
- [외부] 수동 mutant의 equivalent 비율은 `10% 미만`이었지만 개발자의 정확한 판별은 어려웠다. 출처: [Code Defenders 연구](https://arxiv.org/abs/2404.09241)
- [미확보] 라인·분기 커버리지, 모듈별 reached/killed/survived/timeout, mutant 구분도, flaky·환경 실패, 전문가 2명의 equivalent 판정 일치도, mutant당 실행시간을 측정하지 않았다.
- 이 자료 없이는 정답 없는 문제, 테스트가 깨지지 않는 문제, 여러 정답 문제를 걸러낼 수 없다.

### 5. 고정 1·3·7일 반복의 재방문 효과 미입증

- [외부] 프로그래밍 교육의 spacing과 retrieval practice에는 근거가 있다. 출처: [ICER 2019](https://doi.org/10.1145/3291279.3339411), [Distributed practice](https://doi.org/10.1177/18344909211008264)
- [미확보] 자발적 CLI 사용자가 1·3·7일 뒤 실제로 돌아왔다는 사례는 찾지 못했다.
- [외부] 알림이 과의존을 만들 수 있다는 2024년 실험이 있다. 출처: [Study reminders](https://www.nature.com/articles/s41539-024-00253-7)
- [미확보] 모든 능력에 고정된 1·3·7일이 적합하다는 근거는 없다. 경로 추적·권한 판단·패치 작성의 회상 성공도에 따라 간격을 조정해야 한다.

### 6. 읽기 전용 의존 그래프가 장식으로 끝날 위험

- [외부] 실행 trace 시각화 통제실험에서는 IDE만 쓴 집단보다 시간이 `22%` 줄고 정답률이 `43%` 높았다. 출처: [Trace visualization](https://doi.org/10.1109/TSE.2010.47)
- [외부] 단순 viewing보다 응답·조작 같은 높은 engagement가 중요하다. 출처: [Program visualization](https://pmc.ncbi.nlm.nih.gov/articles/PMC6302837/)
- [외부] 2026년 CodeMap은 `15명` 소규모 관찰 연구로 정식 성능 비교가 아니며 초보자 1명은 정보량이 압도적이라고 평가했다. 출처: [CodeMap](https://doi.org/10.1145/3794763.3794822)
- [실측] AST 의존 그래프만으로 런타임 dispatch·플러그인 등록, 설정·환경변수·DB 결합, 상태전이·불변조건, 권한 의미, 호출 빈도·대표 경로, co-change 파일을 보장할 수 없다.
- 위 평가는 Python 정적 import 그래프의 표현력에 관한 원본 작성자의 추론이다. 지도에서 가설을 만들고 경로를 강조·수정·비교하지 않으면 네비게이션 보조물에 그친다.

### 7. 최종 보스전 하나로 전체 구조 이해를 인증할 수 없음

- [미확보] 저위험 backlog 1건과 테스트·리뷰 승인만으로 다른 모듈 전이를 증명한다는 직접 근거는 없다.
- 상태전이는 새 Case 유형의 전이표 역작성과 반례 찾기로, 변경 파급은 보지 않은 커밋의 영향 예측과 실제 diff 비교로 평가해야 한다.
- 학습에 사용하지 않은 모듈에서 지연 평가가 필요하다.

## 대안 과정

[미확보] 18k줄 코드베이스 전체에 대해 현재 5단 구성보다 우월하다고 직접 검증된 단일 형식은 없다. 상대적으로 근거가 나은 대안은 worked example에서 실제 유지보수 작업으로 fading하는 적응형 견습 과정이다.

1. 전문가가 실제 Case 하나를 실행하며 목표·상태·권한·호출 이유를 subgoal별로 설명한다.
2. 학습자가 일부가 빈 trace·상태표·계약표를 복원한다.
3. 결과를 예측하고 실제 trace와 비교한 뒤 불일치 원인을 자기설명한다.
4. 과거의 실제 회귀 버그를 재현하고 최소 원인을 찾는다.
5. 실제 수정 커밋을 가린 채 패치를 제안하고 원래 커밋과 비교한다.
6. 동료와 PR을 리뷰하며 변경 전후의 행동과 위험을 설명한다.
7. 보지 않은 모듈에서 지연 전이 평가를 한다.

## 대안의 근거와 한계

- [외부] Faded Parsons 문제는 `237명` 수업 연구에서 code tracing·code writing보다 패턴 습득과 일반 코드 작성에 효과적이었다. 출처: [Designing Exercises](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2022/EECS-2022-257.html)
- [외부] 2025년 `8주` 디버깅 연구에서 코드별 worked example 집단은 한 세션 뒤 `80%` 정확도에 도달하고 `3주` 뒤에도 유지했다. 소규모 코드 조각 연구라는 제한이 있다. 출처: [Context-Specific Instruction](https://arxiv.org/abs/2509.22420)
- [외부] 2024년 `79명` 통제실험에서 구조화된 peer code review 집단의 성적이 대조군보다 높았다. 출처: [Collaborative Peer Code Review](https://doi.org/10.55612/s-5002-063-007)
- [외부] Google 사례연구와 `324명` 설문에서는 근거를 설명하고 표준에 연결한 리뷰가 학습을 도왔으며 얕거나 맥락 없는 리뷰는 방해했다. 출처: [Effective Teaching through Code Reviews](https://doi.org/10.1145/3660764)
- [외부] 코드 change comprehension 연구에서는 학생이 두 버전의 행동적 유사성을 과대평가했다. 출처: [ICSE 2024](https://conf.researchr.org/details/icse-2024/icse-2024-research-track/227/Barriers-for-Students-During-Code-Change-Comprehension)
- [미확보] 명세 재구성, 문서 역작성, 커밋 히스토리 기반 학습이 이 코드베이스에서 다른 방식보다 우월하다는 직접 실험은 없다. 호출명 맞히기보다 목표 능력에 가까운 산출물이라는 판단은 원본 작성자의 추론이다.

## 설계 변경 권고 5가지

### 1. 고정 5단 코스를 적응형 코스로 변경

사전진단으로 모듈·테스트·도메인 경험을 측정한다. 초보자는 해설된 실제 Case, trace 일부 복원, 전체 예측, 실제 변경 순으로 진행한다. 예측은 최소 정신모형이 생긴 뒤 수행한다.

### 2. 통과 기준을 설명·반례·새 모듈 전이까지 확장

pytest는 행동 보존 오라클로만 쓴다. 호출 이유, 상태·권한 전제, 대안 경로가 불가능한 이유, 입력 변경 시 분기를 구조화해 답하게 한다. 보지 않은 모듈의 지연 전이를 통과해야 능력을 부여한다.

### 3. 자동 뮤테이션을 검증된 회귀 사례 중심으로 축소

git 히스토리의 실제 버그 수정 전 버전을 재현해 `실패 관찰 → 원인 가설 → 최소 패치 → 원래 커밋 비교`를 수행한다. 뮤테이션은 covered·killed·비등가이고 실패 집합이 구분되는 전문가 승인 문제만 사용한다. 모듈별 baseline과 실행시간 기준을 넘지 못하면 제공하지 않는다.

### 4. 읽기 전용 전체 그래프를 가설 검증 지도로 변경

처음부터 56개 노드와 135개 간선을 노출하지 않는다. 현재 Case 관련 노드만 보여 주고 학습자가 예상 간선·상태·권한 경계를 그린 뒤 정적 분석과 trace를 겹쳐 비교한다. import, 실제 호출, 상태 접근, 권한 검사, 역사적 co-change를 구분한다. 이후 지도 없이 경로와 변경 영향을 재구성하게 한다.

### 5. 고정 1·3·7일 복습을 업무 결합형 적응 과제로 변경

PR 리뷰, 주간 장애 훈련, 페어 세션에 복습을 넣는다. 정답, 자신감, 소요시간, 설명 완전도로 다음 간격과 난도를 정한다. 같은 호출이 아니라 다른 모듈에서 같은 계약·상태 원리를 회상하게 한다. 1·3·7일은 초기 기본값일 뿐이며 실제 재방문율과 지연 전이 성과 전에는 교육 효과를 주장하지 않는다.

## 관계

- 원본: program/research/학습게임_설계검수_2026-08-30.md