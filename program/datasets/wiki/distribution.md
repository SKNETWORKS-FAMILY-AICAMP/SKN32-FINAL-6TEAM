---
type: policy
title: 배포본을 만들 때 가리는 것
description: 팀 합본과 배포 ZIP에서 무엇을 빼고 무엇을 가리는가. 집 열쇠 위치가 51건 들어 있었다
status: draft
tags: [data, security]
---

# 배포본을 만들 때 가리는 것

`[실측]` 원본은 `datasets/commerce/DISTRIBUTION.md`.

**팀 안에서 도는 파일이라도 넘기지 않는다.** 이 문서가 존재하는 이유가 그것이다.

## ★ 실제로 새고 있던 것

`[실측]` 쿠팡 `DeliveryRequest` 의 **`기타사항 (…)` 안 자유입력**이 문제였다.

공동현관 비밀번호는 쿠팡이 `#****` 로 가려서 내보낸다. **그런데 이 자유입력은 안 가려진다.**

> 실측으로 `집앞우편함에열쇠로대문안에` 같은 **집 열쇠 위치가 51건** 들어 있었다.

같은 레코드에 `DeliveryRegion`(구 단위 배송지)이 있다. **둘을 합치면 그대로 쓸 수 있는 정보다.**

### 가린 것은 이름으로 남긴다

```
_masked 필드에 가린 항목 이름을 적는다
```

**조용히 지우지 않는다.** 원본이 필요하면 `build_team_merged.py --no-mask` 를 쓰거나 제출본 zip 을 본다.

`[실측]` **제출본 zip 은 가리지 않은 원본이다.** 그래서 그건 더 조심해야 한다.

## 저장소 밖으로 내보낼 때 지울 것

`[실측]` `_dist/` 는 `.gitignore` 의 `datasets/**/*.zip`·`*.jsonl` 로 막혀 커밋되지 않는다.

**손으로 내보낼 때는 둘을 더 지운다.**

| 필드 | 왜 |
|---|---|
| `DeliveryRegion` | 구 단위 배송지 |
| **`DeliveryRequest`** | **가려도 `문 앞`·`새벽 배송` 같은 생활 패턴이 남는다** |

**두 번째가 핵심이다.** 마스킹으로 안 되는 종류가 있다.

## 배포 ZIP 에서 빼는 것

인증 정보나 불필요한 실측 자료를 포함할 수 있는 것들.

```
쿠팡의 MHTML/HTML 캡처 · 실측 fixture · 과거 확장 백업
브라우저 프로필 · 세션 · 쿠키 · .env
```

**쿠팡 확장 출력은 수취인·전화번호·상세주소·우편번호를 수집 단계에서 이미 제거한다.** → [scraper-notes.md](scraper-notes.md)

## `_dist/` 에 세 종류가 있다

**섞어 쓰면 안 된다.**

| 파일 | 무엇 | 명령 |
|---|---|---|
| `commerce_datasets_*.zip` | 재현 코드·스키마·문서 + 쿠팡 산출물 | `build_distribution.py` |
| `team_submissions_*.zip` | **팀원 제출본 원본.** 바이트·이름 그대로 | `build_team_submissions.py` |
| `team_*_*.jsonl` | **제출본을 합친 파생본.** 넷 | `build_team_merged.py` |

### 합본에는 출처를 박는다

```
_submitter · _platform · _source_file
```

**합치고 나면 어느 파일에서 온 줄인지 알 방법이 없어지기 때문이다.**

### 택배를 쇼핑몰별로 나눈 이유

`[실측]` **레코드 모양이 다르다.**

| | 필드 |
|---|---|
| 네이버 | 택배 조회 API 응답 — `courier_code`·`level`·`estimate`·`error` |
| 쿠팡 | 자사 배송 데이터 — `shipment_box_id`·`order_id` |

**한 파일에 섞으면 읽는 쪽이 매번 `_platform` 으로 갈라야 하고, 없는 필드를 있는 줄 알고 쓴다.**

## 건수

`[실측]` 2026-08-31.

| 파일 | 줄 |
|---|---:|
| 네이버 주문 | 270 |
| 쿠팡 주문 | 3,483 |
| 네이버 택배 | 238 |
| 쿠팡 택배 | 1,782 |
| **합계** | **5,773** |

## 관계

- [scraper-notes.md](scraper-notes.md) — 수집 단계의 PII 규칙
- [catalog.md](catalog.md) — 데이터셋 목록
- [index.md](index.md) — 폴더 규칙
