---
type: research
title: 대규모 코드베이스 학습 게임 방법론
description: acop_dojo에 적용할 교수법·게임 설계·자동화 원칙과 근거의 한계를 정리한다.
status: draft
tags: [architecture, evaluation, testing, documentation]
---

## 결론

적합한 형태는 강의에 점수와 배지를 붙이는 방식이 아니라 작은 실제 시스템 실행부터 실제 저장소 변경까지 이어지는 검증 가능한 임무의 연쇄다. 핵심 루프는 `관찰 → 예측 → 실행/추적 → 설명 → 수정 → 회고`다.

지도는 디렉터리 트리가 아니라 실행·데이터·상태·도구·권한·평가 경로를 겹쳐 보여 주는 지식 지도여야 한다. `[외부]` 2025~2026년에는 저장소 기반 위키·코드 투어·이해 문항 자동 생성 기술이 등장했다. `[미확보]` 임의의 대규모 저장소를 검증된 게임형 코스로 완전 자동 변환한 성숙 사례는 확인하지 못했다.

현실적인 방식은 정적·동적 분석으로 구조를 잡고 LLM이 후보 퀘스트를 만들며 테스트·원본 링크·전문가 검토로 정답과 난이도를 보증하는 반자동 파이프라인이다.

## 핵심 교수법 10가지

### 1. Karpathy식 직접 구축

- 핵심: 작지만 작동하는 모델을 직접 만들고 내부를 층별로 확장한다.
- `[외부]` 출처: [Zero to Hero](https://karpathy.ai/zero-to-hero.html), [nanoGPT](https://github.com/karpathy/nanoGPT), 2025년 [nanochat](https://github.com/karpathy/nanochat), [Eureka Labs](https://eurekalabs.ai/)
- 적용: `요청 → 오케스트레이터 → 도구 → 관찰 → 응답 → 평가` 미니 에이전트를 먼저 실행하고 구성요소를 실제 구현으로 교체한다.
- `[미확보]` LLM101n 완성 코스의 효과 평가는 확인하지 못했다.

### 2. fast.ai의 top-down whole game

- 핵심: 유용한 전체 작업을 먼저 경험하고 같은 전체를 반복하면서 고수준 API에서 저수준 구현으로 내려간다.
- `[외부]` 출처: [fast.ai teaching philosophy](https://www.fast.ai/posts/2016-10-08-teaching-philosophy.html), [Deep Learning from the Foundations](https://www.fast.ai/posts/2019-06-28-course-p2v3.html)
- 적용: 대표 사용자 시나리오를 먼저 성공시키고 호출 그래프, 상태·복구, 비용·보안을 같은 시나리오에 겹친다.

### 3. Making Learning Whole 7원칙

- 핵심: 초보자용 전체 게임, 가치, 어려운 부분, 전이, 숨은 구조, 협업, 자기조절을 함께 설계한다.
- `[외부]` 출처: [Making Learning Whole](https://pz.harvard.edu/resources/making-learning-whole-how-seven-principles-of-teaching-can-transform-education), [Education at Bat](https://www.gse.harvard.edu/ideas/usable-knowledge/09/01/education-bat-seven-principles-educators)
- 적용: 전체 제품 흐름을 초보자 리그로 삼고 비결정성·동시성·도구 실패를 보스전으로 분리한다.

### 4. 실패·평가 중심 AI 엔지니어링 교육

- 핵심: 실제 실패를 관찰하고 평가 단위를 만들며 개선한다.
- `[외부]` 출처: [LLM applications for production](https://huyenchip.com/2023/04/11/llm-engineering.html), [AI Evals](https://hamel.dev/notes/llm/evals/index.html), [LLM systems patterns](https://eugeneyan.com/writing/llm-patterns/), [How coding agents work](https://simonwillison.net/guides/agentic-engineering-patterns/how-coding-agents-work/)
- 적용: 트레이스 분류, 실패 가설, 평가 케이스, 수정, 회귀 방지 순으로 진행하고 재현 가능성·근거·평가 오류·회귀 방지를 채점한다.

### 5. 단순 에이전트 패턴부터 확장

- 핵심: 증강 LLM에서 시작해 체이닝·라우팅·병렬화·오케스트레이션을 필요할 때만 추가한다.
- `[외부]` 출처: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), [Agents SDK quickstart](https://openai.github.io/openai-agents-python/quickstart/), [orchestration](https://openai.github.io/openai-agents-python/multi_agent/), [Google ADK 튜토리얼](https://google.github.io/agents-cli/guide/hands-on-tutorial/)
- 적용: 단일 호출을 이해한 뒤 멀티에이전트를 해금하고 비용·지연·정확도로 복잡성을 정당화한다.

### 6. 인지적 도제와 스캐폴딩 페이딩

- 핵심: 전문가 사고를 보여 주고 발판을 제공한 뒤 도움을 제거한다.
- `[외부]` 출처: [Cognitive Apprenticeship](https://www.ideals.illinois.edu/items/18043), [Making Thinking Visible](https://www.aft.org/ae/winter1991/collins_brown_holum)
- 적용: 전문가 고스트에서 시작해 시작 파일·부분 그래프만 남기고 마지막에는 탐색 계획과 근거를 제출하게 한다.

### 7. 가설 주도 프로그램 이해

- 핵심: 질문과 가설을 만들고 도메인 모델과 실제 제어 흐름 사이를 오간다.
- `[외부]` 출처: [Cognitive processes](https://doi.org/10.1016/0164-1212(87)90032-X), [Program comprehension](https://doi.org/10.1109/2.402076), [large-scale 연구](https://doi.org/10.1109/32.508315)
- 적용: 원인 가설을 먼저 쓰고 검색·로그·실행으로 지지하거나 폐기한다.

### 8. 능동적 코드 읽기와 코드 투어

- 핵심: 코드 읽기를 질문, 경로 선택, 요약, 실행 확인이 결합된 과업으로 만든다.
- `[외부]` 출처: 2025년 [data-enhanced active reading](https://doi.org/10.1186/s41039-025-00299-2), [Linear walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/)
- 적용: 파일 읽기 대신 입력이 모델 인자로 바뀌는 지점을 찾게 하고 파일·심볼·실행 증거·요약을 요구한다.

### 9. notional machine과 실행 추적

- 핵심: 문법보다 시스템의 단계별 상태 변화를 명시한다.
- `[외부]` 출처: [Some Difficulties of Learning to Program](https://doi.org/10.2190/3LFX-9RRF-67T8-UVK9), [학생 코드 추적 전략 연구](https://cseweb.ucsd.edu/~bsimon/pubs/papers/icer2005_strats.pdf)
- 적용: 대화 상태, 컨텍스트, 큐, 도구, 권한, 재시도, 캐시, 비용의 다음 상태를 예측한 뒤 실제 트레이스를 공개한다.

### 10. Parsons 문제와 점진적 구성

- 핵심: 빈 편집기에서 작성하기 전에 코드 조각을 선택·배열해 생성 부담을 낮춘다.
- `[외부]` 출처: [Python Grids](https://doi.org/10.1007/s40593-018-0156-y), [Exercism FAQ](https://exercism.org/docs/using/faqs)
- 적용: 정답 조각 제공, distractor, 빈칸 완성, 독립 변경 순으로 지원을 줄인다.

## 추가 교수법과 게임 설계

### 11. 결함 주입과 mutation testing

`[외부]` 작은 의미 변화의 실패를 찾고 테스트를 쓰는 방식이다. 출처: [Mutation Testing for Teaching](https://doi.org/10.58459/icce.2014.413), [Decoding Debugging Instruction](https://doi.org/10.1145/3690652), 2025년 [교육용 mutation 연구](https://www.iris.unina.it/handle/11588/1005441). 권한 확인 순서, idempotency, 도구 결과 기록 오류를 변이로 만들고 실패 재현·가설·최소 테스트·수정 순으로 해결한다.

### 12. 작은 실제 과업과 buddy

`[외부]` 첫 주부터 좁은 실제 변경을 동료와 수행한다. 출처: Dropbox [Engineer onboarding](https://dropbox.tech/culture/a-day-in-the-life-engineer-onboarding-at-dropbox), Microsoft [온보딩 사례](https://arxiv.org/abs/2103.05055), Google SRE [온콜 학습 경로](https://sre.google/sre-book/accelerating-sre-on-call/). 최종 과제는 실제 backlog의 저위험 변경으로 한다. `[미확보]` 대형 회사가 코드베이스 온보딩 전체를 장기 게임화해 효과를 계량한 확실한 1차 사례는 없다.

### 13. 재미를 패턴 학습으로 보기

`[외부]` 외적 보상보다 시스템 패턴 발견과 변형 적용을 중심으로 한다. 출처: [Theory of Fun 강연](https://www.raphkoster.com/games/presentations/theory-of-fun/), [공식 사이트](https://www.theoryoffun.com/). 코드베이스 교육에 대한 직접 실험은 `[미확보]`이다.

### 14. desirable difficulties와 인출·간격·교차 연습

`[외부]` 인출, 간격 반복, 유사 문제 혼합은 장기 보존과 전이에 유리할 수 있다. 출처: [Bjork Lab](https://bjorklab.psych.ucla.edu/research/), [The Critical Importance of Retrieval](https://doi.org/10.1126/science.1152408). 1·3·7일 뒤 다른 모듈에서 원리를 다시 찾게 하되 실패율이 높으면 힌트를 복구한다.

### 15. mastery learning과 AI 튜터

`[외부]` 시간보다 수행으로 숙달을 확인한다. 출처: [2 Sigma Problem](https://doi.org/10.3102/0013189X013006004). 2시그마를 모든 환경의 보장치로 해석하면 안 된다. 레벨 해금은 정상·타임아웃·권한 거부 트레이스 설명과 테스트 통과로 판단한다.

### 16. roguelike·metroidvania 지식 구조

`[외부]` 반복 탐험과 능력 기반 재방문을 적용한다. 출처: [Metroidvania design](https://www.gamedeveloper.com/design/making-sense-of-metroidvania-game-design), [Vim Adventures](https://vim-adventures.com/). `[미확보]` 코드베이스 학습에서 우월하다는 직접 실증은 없다.

### 17. pointsification 피하기

`[외부]` 점수·배지·순위표만 붙이면 의미와 자율성을 약화할 수 있다. 출처: [Humanistic Design](https://doi.org/10.1177/1056492618790912), [Meaningful Play](https://talks.ui-patterns.com/videos/meaningful-play-getting-gamification-right), [교육 게임화 부정 효과](https://doi.org/10.1016/j.infsof.2022.107142). 능력 증거를 진행 표시로 사용하고 전역 순위표는 기본값에서 뺀다.

## 실제 개발자용 게임과 도구

### 18. Build Your Own X와 작은 퍼즐

`[외부]` 작은 호환 단계로 실제 시스템을 재구현하고 외부 테스트로 검증한다. 출처: [CodeCrafters](https://app.codecrafters.io/concepts/overview), [Redis 과정](https://github.com/codecrafters-io/build-your-own-redis), [Advent of Code 2025](https://adventofcode.com/2025/about). 2025년 Advent of Code는 전역 순위표를 제거했다.

### 19. Boot.dev와 Exercism

`[외부]` 짧은 과제, 자동 테스트, 해금, 개인화 복습, 답을 직접 주지 않는 도움을 결합한다. 출처: [Training Grounds](https://www.boot.dev/training), [Boots](https://www.boot.dev/lessons/e4fac74c-9d67-41ad-a85c-c579cb3ad76f), [Exercism Getting Started](https://exercism.org/docs/using/getting-started).

### 20. 실제 도구를 게임 입력으로 사용

`[외부]` 실제 조작을 게임 입력으로 만들어 연습과 전이를 분리하지 않는다. 출처: [Oh My Git!](https://ohmygit.org/), [Vim Adventures](https://vim-adventures.com/), [Regex Crossword](https://regexcrossword.com/), [TIS-100](https://zachtronics.com/tis-100/). 실제 git·테스트·검색·트레이스·디버거를 사용한다.

### 21. 코드로 플레이하는 지속 세계

`[외부]` 코드를 작성하고 장기 행동을 관찰해 설계·피드백·최적화를 반복한다. 출처: [Screeps](https://docs.screeps.com/introduction.html), [Robocode](https://robocode.dev/articles/intro). 에이전트 정책을 샌드박스에 배치하고 성공률·비용·지연·안전·복구를 관찰한다.

### 22. CTF·Game Day·장애 대응

`[외부]` 현실적 장애, 역할 분담, 실제 도구, 회고를 사용한다. 출처: AWS [chaos engineering](https://aws.amazon.com/blogs/security/how-to-use-chaos-engineering-in-incident-response/), Google SRE [Incident Response](https://sre.google/workbook/incident-response/), GitHub [Secure Code Game](https://securitylab.github.com/secure-code-game/). 모델 지연, 잘못된 도구 출력, prompt injection, 큐 적체를 주입한다.

### 23. CI 기반 품질 퀘스트

`[외부]` 실제 커밋과 CI 결과에서 개선 임무를 생성한다. 출처: Jenkins [Gamekins](https://github.com/jenkinsci/gamekins-plugin), [논문](https://arxiv.org/abs/2202.06562), [교육 적용 연구](https://arxiv.org/abs/2401.17740). 교육 연구는 결과 개선을 보고했지만 인과 일반화에는 추가 검증이 필요하다.

## AI 튜터와 저장소 기반 코스

### 24. 코드 인지형 단계적 AI 힌트

`[외부]` 과제·현재 코드·실패 테스트를 보고 다음 한 걸음을 제안한다. 출처: 2025년 [AI Hints](https://blog.jetbrains.com/education/2025/06/02/ai-hints-plugin/), [프로그래밍 교육 LLM 설문](https://aclanthology.org/2025.hcinlp-1.21/). 힌트는 `관찰 요청 → 부분 힌트 → 전략 힌트 → 제한 예시` 순으로 제공한다.

### 25. 코드 이해 문항 자동 생성

`[외부]` 실제 코드에서 개인화 문항을 만들 수 있지만 타당도와 정답 근거 검증이 필요하다. 출처: 2025년 [AutoMCQ](https://arxiv.org/abs/2505.16430), [Testing Code Comprehension using GenAI](https://doi.org/10.1145/3754508.3754532). 저장소 전체 코스 생성의 입증은 `[미확보]`이다.

### 26. 살아 있는 저장소 위키와 다이어그램

`[외부]` 저장소 위키·검색·코드 링크·채팅·다이어그램 자동화가 등장했다. 출처: 2025년 [DeepWiki](https://cognition.com/blog/deepwiki), 2025년 [Code Wiki](https://developers.googleblog.com/ko/introducing-code-wiki-accelerating-your-code-understanding/), 2026년 [CodeWiki 평가](https://aclanthology.org/2026.findings-acl.288/). 문서 생성과 학습 성취는 다르므로 코드·테스트·트레이스로 검증한 항목만 발견 처리한다.

### 27. 정적 그래프와 LLM 코드 투어

`[외부]` 호출·의존 그래프로 핵심 경로를 고른 뒤 LLM이 설명한다. 출처: [LLM-Generated Code Tours](https://xdevroey.be/publication/balfroid-2024/balfroid-2024.pdf), 2025년 [RepoMaster](https://arxiv.org/abs/2505.21577), 2025년 [Multi-agent Onboarding Assistant](https://doi.org/10.1145/3696630.3728611). 모든 투어 단계에 원본 심볼을 남긴다.

### 28. repo-to-course 반자동 파이프라인

`[외부]` 2026년 현재 가능한 것은 자동 초안이며 신뢰할 코스에는 분석·실행 검증·난이도 보정·전문가 승인이 필요하다. 출처: [Linear walkthroughs](https://simonwillison.net/guides/agentic-engineering-patterns/linear-walkthroughs/), 2026년 [(Im)Paired Programming](https://arxiv.org/abs/2607.26375). 후자는 코딩 에이전트의 자동 수락 같은 저노력 상호작용이 낮은 이해와 연결됐다고 보고한다.

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

- `[미확보]` Eureka Labs LLM101n의 완성 강의 전체와 학습 효과 평가
- `[미확보]` 대형 회사가 대규모 코드베이스 온보딩을 장기간 게임화해 효과를 계량한 공개 1차 사례
- `[미확보]` roguelike·metroidvania가 코드베이스 학습에 특별히 우월하다는 직접 실증
- `[미확보]` 임의 저장소를 완전하고 검증된 코스로 자동 변환했다는 근거
- `[외부]` 작은 실제 프로젝트, codelab, buddy, 재난 역할극과 자동 위키·질문·코드 투어의 개별 근거는 확인됐다.

## 관계

- 원본: program/research/학습게임_방법론_조사.md
