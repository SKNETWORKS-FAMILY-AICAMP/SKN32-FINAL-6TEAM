---
type: runbook
title: 안 될 때
description: 실제로 겪은 실패와 그 원인. 겪지 않은 것은 적지 않는다
status: draft
tags: [release, testing]
domain: neutral
---

# 안 될 때

`[실측]` **여기 있는 것은 2026-09-02에 실제로 겪은 것뿐이다.** 겪지 않은 실패를 미리 적지 않는다 — 그러면 틀린 처방이 남는다.

## 겪은 것

### `--timeout` 을 붙이면 pytest 가 죽는다

```
error: unrecognized arguments: --timeout=60
  inifile: pytest.ini
```

**`pytest-timeout` 이 안 깔려 있다.** 그냥 빼고 돌린다.

```bash
python -m pytest -q
469 passed, 1 deselected in 43.89s
```

### 콘솔 출력이 깨진다

`scripts/check_env.py` 출력이 이렇게 나온다.

```
[OK  ] guardrails ε         guardrails.yaml
```

**Windows 콘솔이 cp949 라서다.** 환경변수로 고정한다.

```bash
PYTHONIOENCODING=utf-8 python scripts/check_env.py
```

### 환경 점검이 1건 실패한다

```
[FAIL] v4 원문 대조   찾을 수 없음: A-COP_구현계획서(4).md
```

**기능과 무관하다.** 나머지 10개가 통과하면 띄워도 된다. → [local-setup.md](local-setup.md)

### `/composer/changes` 가 405 를 낸다

**GET 으로 부르면 그렇다. POST 전용이다.** → [run.md](run.md)

### `/v1/*` 가 전부 401 이다

**정상이다.** 개발 키를 만들어 붙인다. → [run.md](run.md)의 "개발 키 만들기"

## 테스트 기준값

`[실측]` 2026-09-02.

```
469 passed, 1 deselected in 43.89s
```

`[실측]` **1건이 deselect 되는 건 설정 때문이다.** `pytest.ini:2`

```ini
addopts = -m "not live"
```

**`live` 마커가 붙은 테스트는 기본으로 안 돈다.** 외부를 실제로 부르는 것이라 그렇다.

## 아직 안 겪은 것

`[미확보]` 다음은 처방을 적을 근거가 없다.

```
Postgres 가 안 떠 있을 때
extension 이 없을 때
임베딩 차원이 어긋날 때
포트가 이미 쓰이고 있을 때
```

**`check_env.py` 가 앞의 셋을 잡는다는 건 코드에서 확인했지만, 실패시켜 본 적은 없다.**

## 관계

- [local-setup.md](local-setup.md) — 띄우기 전
- [run.md](run.md) — 떴는지 확인
