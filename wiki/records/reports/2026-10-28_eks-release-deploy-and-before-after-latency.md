---
type: report
title: EKS 릴리스 2026-10-28 — PR #107 병합 · CD 1차 실패(verify URLError) 뒤 재실행 성공 · 같은 입력 배포 전후 실측 13/13
description: main e88e01925 → 20c296e77. EKS 마이그레이션 Job 시도 제한 + 전체 시험 결정성 + role-manager c52fb5c69 를 EKS 에 반영하고, 공개 도메인에서 같은 계획 글로 배포 전후 13회씩 접수 읽기 시간을 쟀다
status: draft
domain: travel
impl_scope: cs — 팀 원격 main · develop · role-manager push, EKS(CD AWS) 배포. 원본 작업 폴더 코드 변경 0
---

# EKS 릴리스 2026-10-28 — 배포와 전후 실측

> 독립 검증(V, 10-29 00시): 배포 성공 · 전후 수치 재현됨. CD 1차 verify 153.4초는 되돌리기 약 130초가 섞인 값이고 실패는 첫 공개 확인(진입 23초 안, 연결 단계 `URLError` — 이유 미기록)이다. 측정 접수 26건은 게스트 정리가 지울 때 `intake_backups` 에 영구 백업된다. [검증 보고서](2026-10-28_eks-release-independent-verification-and-bottlenecks.md)

## 결론

| 항목 | 결과 |
|---|---|
| EKS 서빙 판 | **main `20c296e77`**(PR #107 병합 22:24 KST). CD (AWS) run `40699378486` 이 22:54:45 KST 에 api · worker · web · admin 4개 digest · 준비 상태 · 공개 `/health` · `/` 200 을 확인(`aws-deploy-result.json`) |
| EKS 인증 | 이 PC · x600 에는 유효한 AWS 자격증명이 **없다**(aws CLI · kubectl 없음). EKS 접근은 CD 의 GitHub OIDC 역할로만 했다 — 「Connect to the existing EKS cluster」 · 이미지 게시 · 마이그레이션 Job · 롤아웃 · digest 확인이 그 인증으로 성공 |
| CD 1차 | run `40697290826` **실패** — `stage=verify, error=URLError`(공개 주소 첫 확인이 15초 안에 응답 못 함 추정), 자동 복구 `recovery=restored`(이전 이미지로 되돌림), 마이그레이션 `committed`(새 SQL 0개라 영향 없음). 실패 뒤 `/health` 200 |
| CD 2차 | 같은 SHA `workflow_dispatch` 재실행 **성공**. 배포 내내 2초 간격 공개 감시 550/550 = 100% 200, 5초 넘는 응답 0 |
| 마이그레이션 Job(이번 수정의 실측) | 1차 30.5초 · 2차 17.4초, 둘 다 `committed`. 시도 제한 · 기한 검사 값(`migration-job.json`)으로 막힘 없음 |
| 배포 단계 시간(2차) | preflight 8.5 · migration 17.4 · worker-pause 4.2 · api 79.0 · worker 12.5 · web 16.5 · admin 20.6 · verify 53.3초 |

## 배포 전후 같은 입력 실측

- 방법: 공개 `https://guguroute.devroro.click` 에서 새 손님 세션 → 같은 계획 글(고정 날짜 2026-11-04 · 05, 6일정 — 「예시 불러오기」 내용과 같은 장소) 접수 → 읽기 SSE 를 `result` 까지 → `GET /v1/web/trip-intakes/{id}`. 같은 스크립트(`probe_intake.py`) · 같은 PC · 같은 순서(3~4회 묶음, 묶음 사이 쉼). 배포 전 21:23~22:28, 배포 후 22:55~23:08 KST.
- 표본: 전 **13/13**, 후 **13/13** 성공(모두 `status=review`). 각 묶음 첫 회는 캐시가 식은 상태라 느린 편이다(아래 행 표 참고).

| 지표 | 배포 전 p50 (최소~최대) | 배포 후 p50 (최소~최대) | 판단 |
|---|---|---|---|
| 접수 → 읽기 끝(`done`) | 45.6초 (27.0~77.1) | 32.1초 (27.0~72.5) | 중앙값 −13.5초. **통계적으로 확정 못 함**(순열 검정 단측 p≈0.20) — 27초대와 45~77초대로 갈리는 두 갈래가 전후 모두 있다 |
| 접수 → GET 끝 | 52.8초 (28.4~90.4) | 33.7초 (28.0~93.6) | 중앙값 −19.1초, p≈0.19 — 같은 이유로 확정 못 함 |
| 읽기 끝 뒤 GET | 3.7초 (0.6~29.5) | 1.2초 (0.6~21.2) | p≈0.06 — 경계 |
| SSE 최대 간격 | 4.05초 (3.21~**22.32**) | 3.01초 (3.00~3.51) | **개선 확인**(p<0.001). 7초 넘는 간격(웹 「연결이 끊겼어요」 기준)이 있던 회차 1/13 → 0/13 |

★개선으로 말할 수 있는 것은 **SSE 생존 신호가 3초 간격으로 고르게 온다**는 것뿐이다(접수 SSE beat 분리 변경의 목적과 일치). 끝까지 걸린 시간은 중앙값이 줄었지만 변동이 커서 13회로는 우연과 구별되지 않는다. 서버 쪽 단계 시각 · pod CPU 는 AWS 자격증명이 없어 보지 못했다.

## 통합 내용과 검증

| 묶음 | 커밋 | 검증 |
|---|---|---|
| EKS 마이그레이션 Job 시도 제한 | `d83ec69b4` · `aaebdacc3` · `0f584a2eb` · `ca879220b` | 이전 독립 검토 2회 · 실 PG 경합. 이번 CD 실제 Job 2회 committed |
| 전체 시험 결정성(시험만) | `ee606a5ef` · `1826f5f42` · `1dbef9e6d` (sa-0-b2602e61, [보고서](2026-10-28_eks-candidate-test-failures-root-cause-and-skips.md)) | Codex read-only 독립 검토: 5파일 수용, **mobility `test_contract_keys` 는 추가 후보가 실제 `more_options` 인지 대조하지 않아 단언이 약해짐** 지적 — 자료 기기 전용(CI · EKS 에서 건너뜀)이라 통합하고 후속 과제로 남김 |
| role-manager | `efc6fca47` + `f24b71080`(시험 날짜) + `e6e754f27`(ST4F-710) + `0d2fd47a6`(ruff F401) + `c52fb5c69`(아래) | 합친 트리에서 바뀐 시험 70파일 격리 PG16: 902 통과 · 0 실패 · 42 건너뜀. PR CI 전 항목 통과 |
| PR #107 CI 1 실패 → 수정 | `c52fb5c69` (시험만) | `test_chat_lodging_web::…picking_one_changes_the_stay` 가 `expired` 409. bisect 로 `4fee819ca`(시험 시계 고정 제거) 확정 — `api` 준비물이 `pending.wall_clock` 을 대본 재생 시계로 꽂는데 대본이 「오늘+7일 이후」로 옮겨져 실제 내일 숙소가 만료로 판정. 숙소 시험 준비물에서 만료 시계를 실제 시계로. RED(기준 main 통과 · rm 실패) → GREEN 27/27, 재실행 CI 전 항목 통과. 제품 코드 0 |

- push(모두 fast-forward, force 0): role-manager 팀 · 개인 `efc6fca47 → 0d2fd47a6 → c52fb5c69`, develop 팀 `36ba4c2fc → 0e12304f8 → 3463b30c6`, main = PR #107 병합 `20c296e77`. 개인 develop(`da35486cb`)은 팀 develop 의 조상이 아니라 손대지 않음.
- SQL 마이그레이션 · requirements · Dockerfile 변경 0 → 앱 롤백과 DB 호환.

## 안전 · 남은 위험

- 운영 DB 에 측정용 손님 접수 26건(전 13 · 후 13, `status=review`, 취소 API 는 409)이 남았다. id 앞 8자리는 scratch `summary.json`. 손님 세션 만료 정리에 맡기며 이 세션은 지우지 않았다. 외부 모델 호출은 운영 설정대로 일어났다(비용 미확인).
- x600(`tripilot.devroro.click`)은 21:3x 부터 Cloudflare 523 · LAN SSH 타임아웃 — 기계/망 정지로 보인다. role-manager push(21:41 · 22:10)의 자동 배포 여부는 **미확인**. 21:34 경 게시판 조회도 이미 응답이 없어 push 전부터 끊긴 것으로 보이나 확정은 못 함.
- CD 1차 verify 실패 원인은 공개 확인 15초 제한 초과로 추정할 뿐(실패 시점 공개 감시 없음). 같은 일이 반복되면 verify 첫 확인 재시도 · 제한 시간을 설정 파일로 빼는 것을 검토.
- 후속: mobility 계약 시험 단언 강화(`more_options` 와 id · 값 대조), x600 복구 뒤 role-manager `c52fb5c69` 배포 확인.

## 증거 (Hermes profile scratch `eks-release-20261028/`)

`probe_intake.py` · `before*.json` · `after_*.json` · `summary.json` · `aggregate.py` · `public_watch.jsonl` · `cd_art/`(1차 실패 기록) · `cd_art2/`(2차 결과) · `ci_fail.log` · `bisect.log` · `ev/targeted/` · `codex_a.txt` · `codex_review_a.txt` · `PR_BODY.md` · `ids*.txt`
