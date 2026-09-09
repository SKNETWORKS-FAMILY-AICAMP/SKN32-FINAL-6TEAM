---
type: runbook
title: 막히면 여기부터
description: 이 저장소에서 실제로 겪은 함정들. 증상에서 원인으로 찾아간다
status: draft
tags: [testing, gpu]
owners: [human:미배정]
domain: neutral
---

# 막히면 여기부터

`[실측]` **전부 이 프로젝트에서 실제로 겪은 것들이다.** 일반론이 아니다.

## 증상 → 원인

| 증상 | 먼저 볼 것 |
|---|---|
| DB 연결이 안 된다 | PostgreSQL이 안 떠 있다 (§1) |
| GPU 작업이 25분 걸려 죽는다 | Windows WDDM 느린 실패 (§2) |
| 토큰이 예상보다 훨씬 많다 | Context Broker 우회 (§3) |
| 테스트는 통과하는데 실 경로가 죽는다 | 테스트가 그 경로를 안 탄다 (§4) |
| 평가 수치가 이상하다 | 옛 도메인 데이터 (§5) |
| 승인이 409로 막힌다 | 표시용 필드 거부 (§6) |
| 오류 메시지가 헷갈린다 | 충돌을 실패로 보고 (§7) |

---

## 1. PostgreSQL이 안 떠 있다

**Windows 서비스가 아니다.** conda env `pgv`에서 뜬 프로세스라 재부팅 후 안 떠 있을 수 있다.

`psql`도 PATH에 없다. → [local-setup.md](local-setup.md)

## 2. Windows WDDM 느린 실패

**증상이 특이하다. 즉시 죽지 않고 25분을 끈다.**

Linux는 VRAM 초과 시 바로 OOM인데, Windows는 초과분을 shared GPU memory(시스템 RAM, PCIe 경유)로 넘겨 극도로 느리게 처리하다 죽는다.

`[실측]` `max_length=2560`으로도 25분 걸려 실패한 사례가 있다.

**빠른 실패가 아니라 느린 실패라 장애 판정이 늦는다.**

| 우회 | 방법 |
|---|---|
| 로딩 | `device_map="auto"`와 4-bit를 **모두 버리고** bf16으로 CPU에 올린 뒤 `.to("cuda")` |
| 재현 | `eval/finetune/diag_3b.py` |

**자체호스팅을 제품으로 만들면 Linux를 전제해야 한다.**

## 3. Context Broker 우회

**증상은 토큰 폭증이다.**

`[실측]` 데이터 수확 스크립트가 `ContextBroker.build()`를 안 거치고 `team_result.evidence`를 그대로 쓰면 정책 청크가 두 번 중복된다.

```
개별 policy evidence 8개 + 그걸 통째로 품은 병합 evidence 1개
  → 중앙값 10,670 토큰 → 12GB VRAM OOM
```

**프로덕션은 안전하다.** Broker가 예산 안에서 조합한다.

**우회 경로를 만들지 않는다.** → [../context/context-broker.md](../context/context-broker.md)

## 4. 테스트가 실 경로를 안 탄다

**가장 뼈아픈 종류다. 통과하는데 죽는다.**

`[실측]` Response Review Team이 production DB-감사 경로로 호출될 때마다 `RuntimeError: no active prompt registered`로 죽고 있었다.

**발견이 늦은 이유** — 그 Team의 유일한 실 LLM 테스트가 `connection_factory` 없이 LLM을 만들어 **문제의 경로 자체를 건너뛰었다.**

`[실측]` 비슷한 것 하나 더. `eval/runners/common.py`가 삭제된 옛 모듈을 import해 라이브 경로가 깨져 있었다. **pytest가 이 모듈을 안 돌려서 안 잡혔다.**

**확인법 — DB를 직접 조회하거나 실 경로를 한 번 태워 본다.**

## 5. 옛 도메인 평가 데이터

**2026-08-17에 도메인이 쇼핑몰로 바뀌면서 이전 측정이 전부 무효가 됐다.**

판별은 `case_id`다.

```bash
python -c "import json; print(json.loads(open('eval/reports/raw_proposed.jsonl',encoding='utf-8').readline())['case_id'])"
```

`g-billing-*` · `g-technical-*` → **무효**
`g-exchange-*` · `g-order-*` · `h-*` · `synth-*` → 유효

→ [../quality/eval-harness.md](../quality/eval-harness.md)

## 6. 승인이 409로 막힌다

`[실측]` `verification_policy.py`가 **표시용 `evidence` 필드를 거부**해서였다. 고쳐졌고 회귀 테스트가 있다.

**같이 있던 결함** — 승인 감사 기록이 대기 큐에 유령 항목으로 남았다.

**둘 다 브라우저에서 승인 버튼을 여러 번 눌러 발견했다.** 테스트만으로는 안 나왔다.

## 7. 오류 메시지가 사실을 잘못 전한다

`[실측]` **상태 충돌을 "LLM 실패"로 보고하면 한참 헤맨다.**

충돌은 정상 동작이다. 실패로 보고하면 있지도 않은 버그를 찾게 된다.

| 구분 | 뜻 | 대응 |
|---|---|---|
| `StateConflict` | 남이 먼저 썼다 | 재시도 |
| `InvalidTransition` | 허용 안 된 전이 | **버그** |
| provider timeout | 모른다 | `unknown`, 재시도 안 함 |

→ [../runtime/conflict-retry.md](../runtime/conflict-retry.md)

---

## 진단할 때의 원칙

`[실측]` 이 저장소의 규칙이다.

| 원칙 | 왜 |
|---|---|
| **오진 위에 수정을 쌓지 않는다** | 하나 고치면 그것만 검증하고 다음으로 |
| **회귀가 의심되면 옛 커밋을 먼저 실행한다** | 추측보다 빠르다 |
| **오진했던 내용을 주석에 남긴다** | 다음 사람이 되풀이하지 않도록 |
| **건수만 세는 검증을 믿지 않는다** | 이 프로젝트에서 두 번 실패했다 |

마지막 줄이 특히 그렇다. 코퍼스는 `check_corpus.py`로, seed는 DB 직접 조회로 센다.

## 관계

- [local-setup.md](local-setup.md) — 환경
- [run.md](run.md) — 실행 명령
- [../quality/blind-spots.md](../quality/blind-spots.md) — 테스트가 못 잡는 것
- [../quality/eval-harness.md](../quality/eval-harness.md) — 평가 데이터 판별
