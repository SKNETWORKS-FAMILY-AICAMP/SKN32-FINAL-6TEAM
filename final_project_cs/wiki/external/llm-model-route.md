---
type: contract
title: 모델 경로 — 관리 콘솔에서 로컬 모델 · SSH(런팟) · API 고르기
description: 관리 콘솔 운영 설정 「모델 경로」(local · ssh · api)가 무엇을 바꾸는지, 넘김 순서, SSH 터널을 앱 밖에서 여는 설치 순서
status: draft
tags: [agent, security]
owners: [human:미배정]
domain: neutral
domain_note: 모델 호출 경로 고르기라 도메인 낱말이 없다. 코드 `app/infrastructure/ollama_chat.py`
---

# 모델 경로 — 관리 콘솔에서 로컬 모델 · SSH(런팟) · API 고르기

> `[2026-10-15 사용자 지시]` 「관리자 웹앱에서 모델 사용을 api 로 할지 ssh 로 할지 로컬 모델로 할지 설정 가능한 옵션」.
> 구조는 사용자가 승인했다. 오라클 서버도 같은 세 경로다(ssh = 런팟, 로컬 = 그 기계의 모델, api).

## 한눈에

| 고르는 값 | 콘솔에 보이는 이름 | 부르는 곳 | 안 되면 |
|---|---|---|---|
| `local` (기본) | 로컬 모델 — 이 기계의 학습 E4B | 이 기계의 Ollama(또는 Ollama 모양 어댑터)에 올린 우리 학습 E4B | 모델 넘김 장치가 켜져 있으면 유료 API |
| `ssh` | SSH — 런팟 GPU 서버 | SSH 터널 입구(`ACOP_OLLAMA_SSH_BASE_URL`) 너머 런팟 Ollama 의 **같은 이름** 모델 | 넘김 장치가 켜져 있으면 이 기계 Ollama → 유료 API |
| `api` | API — 유료(서버용 키) | 유료 API(`ACOP_OPENAI_API_KEY_SERVER`, 모델 `ACOP_LLM_FAILOVER_MODEL`) | 늘 이 기계 Ollama 로 넘긴다 |

- **어디서 바꾸나**: 관리 콘솔 「운영 설정 · 보관 기간」 → 「웹 이용 · 서비스 설정」 → **모델 경로(채팅 해석 · 일정 짚기 · 공지 확인)**. 변경 사유를 적고 저장한다.
- **언제 반영되나**: 재기동 없이. 운영 설정 캐시(`web_guard.cache_seconds`, 30초)만큼 늦을 수 있다.
- **설정 없는 경로를 고르면**: 로컬 모델로 돈다(경고 로그 `app.model_route` 한 번). 콘솔 설명 맨 끝 줄이 이 기계에서 어느 경로가 「준비됨」인지 보여 준다(주소 · 키 값은 안 보인다).

## 무엇이 따르나

| 자리 | 따르나 | 왜 |
|---|---|---|
| 채팅 해석(할 일 고르기) · 계획 읽기 · 번역 · 분류 · 신고 추출 | 따른다 — 부를 때마다 경로를 읽는다 | `ollama_chat.from_settings` 가 `RoutedChat` 을 돌려준다 |
| 일정 짚기 · 공지 「끝났나」 · 「여행 영향」 2차 확인 | `local` · `ssh` 만 따른다. `api` 를 골라도 이 기계 Ollama | 학습 모델이 API 에 없다. 못 부르면 지금처럼 규칙으로 돌아간다 |
| 규정 검색(임베딩) | 따르지 않는다 | 벡터 차원이 달라(bge-m3 1024 · OpenAI 1536) 바꾸면 검색이 깨진다 |
| 규정 재순위(`policy_rerank`) · 운영 점검용 직접 호출 | 따르지 않는다 | 기본 꺼짐 · 점검 도구. 필요하면 따로 붙인다 |

## SSH 경로 설치 — 터널은 앱 밖에서 연다

앱(cs 프로젝트 서버 컨테이너)은 **SSH 키를 들지 않는다.** 같은 기계에서 앱과 따로 도는 터널 프로그램이 런팟과의 SSH 통로를 열어 두고, 앱은 그 입구 주소만 부른다. 앱이 뚫려도 키가 새지 않고, 배포로 앱이 다시 떠도 통로가 끊기지 않는다.

| 단계 | 하는 일 | 끝나면 보이는 것 |
|---|---|---|
| 1 | 런팟 포드에 Ollama 를 띄우고 **x600 서버와 같은 이름**(`tripilot-pointer:e4b-ft`, 기본 파일 + 학습 덧붙임 같은 판)으로 모델을 올린다 | 런팟에서 `ollama list` 에 그 이름이 보인다 |
| 2 | 터널을 열 기계(x600 서버면 도커가 도는 WSL, 오라클 서버면 그 리눅스)에 터널 계정 · SSH 키 · `~/.ssh/config` 런팟 별칭을 둔다 | 그 계정에서 `ssh <런팟 별칭> true` 가 비밀번호 없이 끝난다 |
| 3 | [deploy/model-ssh-tunnel.service](../../deploy/model-ssh-tunnel.service) 의 `<...>` 칸을 채워 `/etc/systemd/system/` 에 두고 `systemctl enable --now model-ssh-tunnel` | `systemctl status model-ssh-tunnel` 이 active, 입구에서 `curl <입구>/api/tags` 가 런팟 모델 목록을 낸다 |
| 4 | 그 기계의 배포 환경 파일에 `ACOP_OLLAMA_SSH_BASE_URL=<입구 주소와 포트>` 한 줄을 넣고 **컨테이너를 다시 만든다** | 관리 콘솔 모델 경로 설명에 「SSH 준비됨」 |
| 5 | 콘솔에서 「SSH — 런팟 GPU 서버」를 고르고 채팅을 한 번 보낸다 | 채팅 답이 오고, 런팟 쪽 Ollama 로그에 그 요청이 찍힌다 |

- ★**x600 서버 환경 파일에 줄을 더하면 자동 배포가 멈춘다**(떠 있는 컨테이너와 설정이 달라져 drift 로 본다). 4단계는 컨테이너 재생성과 한 묶음으로, 사용자 확인 뒤에 한다.
- 입구 주소는 **앱 컨테이너가 닿는 주소**여야 한다. 오라클 서버는 앱이 `network_mode: host` 라 그 기계의 루프백이면 된다. x600 서버는 앱이 지금 Ollama 에 닿는 길(호스트 중계)과 같은 쪽에 연다 — 설치할 때 확인한다(이 문서를 쓸 때 x600 서버에서 확인하지 않았다).
- 런팟은 켜 둔 시간만큼 요금이 난다. 포드를 끄면 SSH 경로는 실패하고, 넘김 장치가 켜져 있으면 이 기계 Ollama → API 로 간다.

## 막히면

| 보이는 것 | 원인 | 고치는 법 |
|---|---|---|
| 콘솔에서 SSH 를 골랐는데 로그에 `ACOP_OLLAMA_SSH_BASE_URL is empty` | 환경 파일에 입구 줄이 없다 | 설치 4단계 |
| `API 를 골랐는데 ACOP_OPENAI_API_KEY_SERVER is empty` | 서버용 키가 없다(개인 키는 쓰지 않는다) | 서버 `.env.apikeys` 에 서버용 키 |
| SSH 를 골랐더니 답이 모두 「모름」 | 넘김 장치가 꺼져 있고 터널 · 런팟이 죽었다 | `systemctl status model-ssh-tunnel` · 런팟 포드 상태 확인. 급하면 콘솔에서 로컬 모델로 되돌린다 |
| SSH 경로에서 「모델 없음」 | 런팟에 같은 이름의 모델이 없다 | 설치 1단계 |

## 코드

- 경로 고르기 · 클라이언트 조립: [app/infrastructure/ollama_chat.py](../../app/infrastructure/ollama_chat.py) (`current_route` · `RoutedChat` · `route_base_url`)
- 넘김 순서(고른 경로 먼저): [app/infrastructure/llm_failover.py](../../app/infrastructure/llm_failover.py) `wrap_from_settings(extra_urls=, api_first=)` — 넘김 장치 자체는 [llm-failover.md](llm-failover.md)
- 콘솔 값 읽기: `app/domains/travel_ops/components/settings_hook.py` `model_route` · 콘솔 항목: `modules/web_account/web_guard.py` `llm.model_route`
- 기본값: `config/guardrails.yaml` `web_guard.model_route`
- 시험: `tests/unit/infrastructure/test_model_route.py`(mock 서버 · 조립만 — 실제 모델 · 유료 API 는 부르지 않는다)
