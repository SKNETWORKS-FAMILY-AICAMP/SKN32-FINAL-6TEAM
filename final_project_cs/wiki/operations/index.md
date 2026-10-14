---
type: guide
title: 여행 제품 개발·배포·운영 안내
description: 환경별 실제 상태와 운영 절차 문서의 목차
status: draft
domain: travel
---

# 여행 제품 개발·배포·운영 안내

환경별 실제 상태와 절차를 구분합니다. ‘콘솔’이라는 말로 터미널·고객 웹·개발자 진단 화면을 합쳐 부르지 않습니다.

| 필요한 정보 | 문서 |
|---|---|
| 환경·구성·마지막 관측 | [운영 현황](current-state.md) |
| 정상 판정·장애 대응 | [상시 운영 점검·복구](always-on.md) |
| 로컬 실행·회귀 | [로컬 안내](local-setup.md)·[실행·검증](run.md) |
| 공개 배포 정의·절차 | [Docker 배포 파일](../../deploy/README.md) |
| Oracle ARM 앱 실험 | [앱 배포·실제 요청 검사](arm-develop-cd.md) |
| 모델·GPU 연구 | [ARM 모델 시험](arm-serving-queue.md)·[GPU 대기열](gpu-work-queue.md) |
| 결과를 모르는 부수효과 | [unknown 상태 확인](unknown-state.md) |
| 여행 자료·평가 | [현재 평가 도구](../quality/eval-harness.md)·[SQL 적용](../data/migrations.md) |

과거 쇼핑몰 평가 명령·GPU 실패 실측은 보존 기록으로 분리합니다. 현재 자료 검사·모델 평가·릴리스 여부는 각 정본과 실행 결과로 확인합니다. 개발자·QA 진단 권한이 있다는 이유로 고객 문제를 수동 수정하는 상주 상담원 운영을 도입하지 않습니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--operations--index.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 2026-10-12 목차에 더한 문서

- [personal-manager-sync.md](personal-manager-sync.md) — 개인 role-manager 와 팀 수정사항을 합친 기록 안내(2026-10-11)

## 이전 절 링크

<a id="operations"></a>
<a id="각-문서"></a>
<a id="자주-쓰는-명령"></a>
<a id="정정-2026-09-10-evalrun---arm-proposed-로-적혀-있었다--evalrunpy-는-없다"></a>
<a id="환경"></a>
<a id="알려진-함정"></a>
<a id="windows-wddm의-느린-실패"></a>
<a id="12gb-vram-한계"></a>
<a id="context-broker-우회"></a>
<a id="인접-영역"></a>
