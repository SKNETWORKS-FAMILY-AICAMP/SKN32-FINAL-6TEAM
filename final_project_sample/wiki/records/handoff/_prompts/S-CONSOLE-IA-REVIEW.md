# 검토 의뢰 — 개발 콘솔 정보구조(IA) 교차검증

## 0. 배경 — 지금까지 잘못 잡고 있었다

이 저장소(`final_project_sample`)는 **CS 플랫폼을 찍어내는 범용 basement** 다.
실제 서비스(쇼핑몰 CS 등)는 이걸 **복사해서** 만든다(`wiki/records/handoff/10`).

그런데 `/ui/*` 를 **최종 고객사 CS 운영 화면**처럼 만들어 놨다. 그게 아니다.

★**A-COP 운영 콘솔의 사용자는 "이 제작 플랫폼을 굴리는 우리"다.**
  - 모듈을 붙였다 뗐다 하고 (Composer)
  - 샘플 프로젝트를 굴려 보고
  - 그 결과를 점검하고
  - 이 모듈화 프로젝트 자체를 관리한다

`cases`/`approvals`/`voc` 는 **샘플 런타임을 들여다보는 창**일 뿐이고,
메인 대시보드는 **프로젝트 관리**여야 한다.

## 1. 현재 상태

```
/ui/cases       Case 목록 (샘플 런타임)
/ui/cases/{id}  상세 · /trace
/ui/approvals   승인 (샘플 런타임)
/ui/voc         VOC 리포트 (샘플 런타임)
/ui/admin       Team manifest · Port · guardrails · 상태 분포
/ui/composer    ★제작 구성기 — 모듈/Port/Team 토글, 실행순서 구조도
```

기타 자산: `config/project.yaml`(조립 선언) · `wiki/records/evidence/DoD-01~28`(판정 28건) ·
`eval/reports/`(평가 540행·ablation·방어지표) · `scripts/verify_dod.py` ·
`scripts/check_corpus.py` · `tests/architecture/`(basement 순수성 게이트) ·
`app/modules/`(도메인 자리) · 마이그레이션 `001_core`(14) / `002_domain`(4)

현재 **284 passed**.

## 2. 웹 리서치로 확인한 두 계열

| 계열 | 대표 | 대시보드가 보여주는 것 |
|---|---|---|
| Internal Developer Platform | Backstage · Port | 소프트웨어 카탈로그(오너십·수명주기·의존성), **스코어카드**(품질/보안 등급), 스캐폴더 템플릿, TechDocs |
| LLM 옵저버빌리티 | Langfuse · LangSmith | 트레이스, 평가(eval), 비용·토큰, latency P50/P99, 프롬프트 버전, agent graph, 세션 |

우리 플랫폼은 **둘 다** 해당한다 — 만드는 대상이 *AI 에이전트 CS 플랫폼*이기 때문이다.

## 3. 내가 제안하는 IA (이걸 검토·반박해 달라)

```
/ui/                 ← 대시보드 (지금은 /ui/cases 로 리다이렉트 중)
  ├ 조립 상태        모듈 7 / Port 3 / Team N / 컴포넌트 9, 실행순서 구조도
  ├ 준비도 스코어카드 DoD 28항목, basement 순수성, 테스트, 코퍼스 게이트
  ├ 최근 실행        평가 540행 · ablation · 방어지표(공격 차단율)
  └ 지금 막힌 것     부분통과 DoD, 미착수 항목, 실패 게이트

/ui/composer         제작 구성기 (유지)
/ui/quality          게이트·판정 — DoD 28, 테스트, 코퍼스, basement 게이트
/ui/experiments      평가·ablation·방어지표 — 비용/토큰 포함
/ui/sample/*         ★샘플 런타임 (기존 cases/approvals/voc/trace 를 여기로)
/ui/admin            런타임 조립 실측 (유지)
```

## 4. 물어보는 것

1. ★**이 IA 가 "제작 플랫폼 운영" 목적에 맞나?** 빠진 축이 있나?
   특히 Backstage 의 *카탈로그·오너십·스코어카드*, Langfuse 의 *트레이스·비용·프롬프트 버전*
   중 우리가 반드시 넣어야 할 것과 **넣으면 과한 것**을 갈라 달라.
2. ★**대시보드 첫 화면에 무엇이 와야 하나?** 이 프로젝트에서 사람이 가장 자주 묻는 질문은
   무엇이라고 보나? (내 가설: "지금 조립이 뭐고, 무엇이 막혀 있고, 마지막 실행 결과는?")
3. **`/ui/sample/*` 로 옮기는 게 맞나?** 아니면 다른 분리 축이 나은가?
4. 우리 저장소에 **이미 있는데 화면에 안 드러난 자산**은? (위 §1 기타 자산 참조)
5. ★**하지 말아야 할 것** — 이런 콘솔에서 흔한 과설계·허수 지표는?

## 5. 형식

`wiki/records/reports/2026-08-17_S-CONSOLE-IA-REVIEW_리포트.md` 로 답을 남겨라.
코드는 건드리지 마라. **검토와 반박만** 한다.

★동의만 하지 마라. **틀린 곳을 짚어 달라.** 내 IA 가 그대로 좋으면
"왜 다른 안보다 나은지" 를 근거로 적어라.
