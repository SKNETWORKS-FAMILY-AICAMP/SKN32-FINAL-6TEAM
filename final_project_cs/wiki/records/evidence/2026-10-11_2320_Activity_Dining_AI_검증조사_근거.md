---
type: evidence
title: Activity·Dining AI 검증 조사 근거
description: 고정 Git 소스 비교와 기존 평가 JSON의 분모·조건을 대조한 기록
status: draft
tags: [testing]
domain: travel
---

# Activity·Dining AI 검증 조사 근거

- 수행: Codex, 2026-10-11 KST.
- [조사 보고서](../reports/2026-10-11_2320_Activity_Dining_AI_검증조사.md).
- 이 문서는 **이번에 새 모델 실험을 실행한 결과가 아니다.** 고정 커밋의 원문과 과거 실행 결과를 읽어 대조했다.
- 병합 중인 작업 폴더의 구현 파일을 수정하거나, checkout·reset·merge·add·commit·push를 실행하지 않았다.
- 운영 DB·외부 모델 API·새 pytest는 실행하지 않았다. 계정·키·비공개 설정 원문은 저장하지 않았다.

## 1. 고정 Git 기준과 재현 명령

저장소 루트에서 실행. 아래 명령은 읽기 전용이다.

```powershell
git rev-parse origin/develop origin/role-activity origin/role-activity-test origin/role-dining
git rev-list --left-right --count 180c56ae...3fe74c15
git rev-list --left-right --count 180c56ae...af584537
git merge-base --is-ancestor 662485c2 180c56ae
git diff --stat af584537 180c56ae -- final_project_cs/app/domains/travel_ops/instances/dining final_project_cs/eval/runners/place_lookup.py final_project_cs/eval/runners/dining_alternatives.py
git grep -n -e 'dining.tick' -e 'tick_once' 180c56ae -- final_project_cs/app final_project_cs/scripts
```

확인한 고정 SHA:
- develop: `180c56aeae1ff5d25f0e00d562c2f0ebf1660b2b`
- role-activity: `662485c23aeae2a6016fb645f5c51da237c1d9f0`
- role-activity-test: `3fe74c153ab019e88b152113eb028b3edea12c65`
- role-dining: `af5845370d0b79470bd681d56ff1cd975985de87`

2026-10-11 23:24 KST 재확인 출력:
```text
25    38
27    0
activity_ancestor_exit=0
(dining 경로 + 두 실행기 diff --stat: 출력 없음)
```

- 위 숫자는 왼쪽 develop만 / 오른쪽 해당 브랜치만이다.
- `tick_once` 검색은 dining/tick.py의 문서 예제·정의·자체 문자열, scripts/dining/MERGE.md의 연결 예제, check_core_integration.py의 검사 문자열을 반환했다. 다른 app 모듈의 운영 호출은 검색 결과에 없었다. 활성 스케줄러를 재현한 것은 아니다.
- 작업 중 Claude Code가 동일 작업 트리를 병합하고 있었다. 원문 읽기는 `git show SHA:path`로 고정했다. 최종 배포 SHA는 미확인이다.

## 2. 평가 원문을 다시 읽는 명령

```powershell
git show 3fe74c15:final_project_cs/eval/activity_judge/manifest.json
git show 3fe74c15:final_project_cs/eval/reports/activity_judge/20261006T091508Z/summary.json
git show 3fe74c15:final_project_cs/eval/reports/activity_judge/20261006T091915Z/summary.json
git show 3fe74c15:final_project_cs/eval/activity_judge/metrics.py
git show 3fe74c15:final_project_cs/eval/activity_judge/run.py
git show af584537:final_project_cs/eval/reports/2026-10-08_place_lookup_v3-domains.json
git show af584537:final_project_cs/eval/reports/2026-10-08_place_lookup_holdout_v3-domains.json
git show af584537:final_project_cs/eval/reports/2026-10-08_dining_alternatives_v3-domains.json
git show af584537:final_project_cs/eval/reports/2026-10-08_dining_alternatives_holdout_v3-domains.json
git show af584537:final_project_cs/eval/runners/place_lookup.py
git show af584537:final_project_cs/eval/runners/dining_alternatives.py
```

아래는 JSON 원문의 선택 필드다. 이번 도구 세션에서 JSON.parse로 읽었으며, 비용 추정 필드는 제외했다.

```json
{
  "activity": {
    "conditions": {
      "eval_run": "20261006T091508Z",
      "dataset_sha256": "5a0c98e5655479c7c0ce3e95d63a56ac86c344be8a430ae8b49576e1f5140bcb",
      "labeler": "claude(작성자) — 사람 검토 전",
      "cases": 60,
      "repeats": 3,
      "model": "gpt-5.4-nano",
      "reasoning_effort": "low",
      "web_search": true,
      "temperature": null,
      "seed": null,
      "prompt_version": "activity_judge.*.v1",
      "bootstrap": {
        "n": 10000,
        "seed": 7,
        "unit": "case"
      }
    },
    "labeled": {
      "cases": 52,
      "observations": 156,
      "llm_accuracy": {
        "value": 0.9871794871794872,
        "ci95": [
          0.9615384615384616,
          1
        ],
        "num": 154,
        "den": 156
      },
      "rule_accuracy": {
        "value": 0.46153846153846156,
        "ci95": [
          0.3269230769230769,
          0.5961538461538461
        ],
        "num": 24,
        "den": 52
      },
      "llm_minus_rule": {
        "value": 0.5256410256410257,
        "ci95": [
          0.391025641025641,
          0.6538461538461539
        ],
        "paired_cases": 52
      },
      "llm_dangerous": {
        "num": 2,
        "den": 156
      },
      "llm_safe_unknown": {
        "num": 0,
        "den": 156
      },
      "rule_dangerous": {
        "num": 13,
        "den": 52
      },
      "rule_safe_unknown": {
        "num": 15,
        "den": 52
      },
      "llm_unknown": {
        "num": 23,
        "den": 156
      },
      "llm_uncited": {
        "num": 0,
        "den": 156
      },
      "llm_call_failed": {
        "num": 0,
        "den": 156
      },
      "agree_with_rule": {
        "num": 55,
        "den": 85
      },
      "consistent_cases": {
        "num": 48,
        "den": 52
      },
      "latency_ms": {
        "p50": 1708,
        "p95": 3065,
        "n": 156
      },
      "search_calls_mean": 0,
      "citations_kept": {
        "num": 0,
        "obs": 156
      },
      "undated_citations": 0
    },
    "closure": {
      "cases": 16,
      "observations": 48,
      "llm_accuracy": {
        "value": 0.9583333333333334,
        "ci95": [
          0.875,
          1
        ],
        "num": 46,
        "den": 48
      },
      "rule_accuracy": {
        "value": 0.4375,
        "ci95": [
          0.1875,
          0.6875
        ],
        "num": 7,
        "den": 16
      },
      "llm_minus_rule": {
        "value": 0.5208333333333334,
        "ci95": [
          0.2916666666666667,
          0.75
        ],
        "paired_cases": 16
      },
      "llm_dangerous": {
        "num": 2,
        "den": 48
      },
      "llm_safe_unknown": {
        "num": 0,
        "den": 48
      },
      "rule_dangerous": {
        "num": 9,
        "den": 16
      },
      "rule_safe_unknown": {
        "num": 0,
        "den": 16
      },
      "llm_unknown": {
        "num": 13,
        "den": 48
      },
      "llm_uncited": {
        "num": 0,
        "den": 48
      },
      "llm_call_failed": {
        "num": 0,
        "den": 48
      },
      "agree_with_rule": {
        "num": 17,
        "den": 35
      },
      "consistent_cases": {
        "num": 13,
        "den": 16
      },
      "latency_ms": {
        "p50": 2100,
        "p95": 3168,
        "n": 48
      },
      "search_calls_mean": 0,
      "citations_kept": {
        "num": 0,
        "obs": 48
      },
      "undated_citations": 0
    }
  },
  "live_status": {
    "conditions": {
      "eval_run": "20261006T091915Z",
      "dataset_sha256": "5a0c98e5655479c7c0ce3e95d63a56ac86c344be8a430ae8b49576e1f5140bcb",
      "labeler": "claude(작성자) — 사람 검토 전",
      "cases": 8,
      "repeats": 3,
      "model": "gpt-5.4-nano",
      "reasoning_effort": "low",
      "web_search": true,
      "temperature": null,
      "seed": null,
      "prompt_version": "activity_judge.*.v1",
      "bootstrap": {
        "n": 10000,
        "seed": 7,
        "unit": "case"
      }
    },
    "metrics": {
      "cases": 8,
      "observations": 24,
      "llm_unknown": {
        "num": 15,
        "den": 24
      },
      "llm_uncited": {
        "num": 0,
        "den": 24
      },
      "llm_call_failed": {
        "num": 8,
        "den": 24
      },
      "agree_with_rule": {
        "num": 0,
        "den": 0
      },
      "consistent_cases": {
        "num": 3,
        "den": 8
      },
      "latency_ms": {
        "p50": 15709,
        "p95": 40672,
        "n": 16
      },
      "search_calls_mean": 1.875,
      "citations_kept": {
        "num": 20,
        "obs": 24
      },
      "undated_citations": 13
    }
  },
  "dining": {
    "d-place-dev": {
      "source": "final_project_cs/eval/reports/2026-10-08_place_lookup_v3-domains.json",
      "summary": {
        "accuracy": {
          "num": 31,
          "den": 34,
          "rate": 0.912
        },
        "wrong_confirmed": {
          "num": 0,
          "den": 34,
          "rate": 0
        },
        "wrong_review": {
          "num": 1,
          "den": 34,
          "rate": 0.029
        },
        "not_found": {
          "num": 2,
          "den": 34,
          "rate": 0.059
        },
        "blocked": {
          "num": 0,
          "den": 34,
          "rate": 0
        },
        "labels": {
          "correct_confirmed": 8,
          "correct_review": 20,
          "correct_abstain": 3,
          "wrong_review": 1,
          "wrong_confirmed": 0,
          "not_found": 2,
          "blocked": 0,
          "error": 0
        },
        "by_group": {
          "misc": {
            "num": 9,
            "den": 12,
            "rate": 0.75
          },
          "name": {
            "num": 10,
            "den": 10,
            "rate": 1
          },
          "near": {
            "num": 12,
            "den": 12,
            "rate": 1
          }
        }
      }
    },
    "d-place-hold": {
      "source": "final_project_cs/eval/reports/2026-10-08_place_lookup_holdout_v3-domains.json",
      "summary": {
        "accuracy": {
          "num": 9,
          "den": 12,
          "rate": 0.75
        },
        "wrong_confirmed": {
          "num": 0,
          "den": 12,
          "rate": 0
        },
        "wrong_review": {
          "num": 0,
          "den": 12,
          "rate": 0
        },
        "not_found": {
          "num": 3,
          "den": 12,
          "rate": 0.25
        },
        "blocked": {
          "num": 0,
          "den": 12,
          "rate": 0
        },
        "labels": {
          "correct_confirmed": 1,
          "correct_review": 7,
          "correct_abstain": 1,
          "wrong_review": 0,
          "wrong_confirmed": 0,
          "not_found": 3,
          "blocked": 0,
          "error": 0
        },
        "by_group": {
          "misc": {
            "num": 4,
            "den": 5,
            "rate": 0.8
          },
          "name": {
            "num": 3,
            "den": 4,
            "rate": 0.75
          },
          "near": {
            "num": 2,
            "den": 3,
            "rate": 0.667
          }
        }
      }
    },
    "d-alt-dev": {
      "source": "final_project_cs/eval/reports/2026-10-08_dining_alternatives_v3-domains.json",
      "summary": {
        "accuracy": {
          "num": 19,
          "den": 19,
          "rate": 1
        },
        "acceptable": {
          "num": 19,
          "den": 19,
          "rate": 1
        },
        "violations": {
          "num": 0,
          "den": 19,
          "rate": 0
        },
        "violations_any_seed": {
          "num": 0,
          "den": 19,
          "rate": 0
        },
        "labels": {
          "correct": 18,
          "ok": 0,
          "correct_no_change": 1,
          "wrong_violation": 0,
          "wrong": 0,
          "missed": 0,
          "wrong_change": 0,
          "unstable": 0
        },
        "by_group": {
          "brand": {
            "num": 3,
            "den": 3,
            "rate": 1
          },
          "move": {
            "num": 5,
            "den": 5,
            "rate": 1
          },
          "sanity": {
            "num": 3,
            "den": 3,
            "rate": 1
          },
          "similar": {
            "num": 6,
            "den": 6,
            "rate": 1
          },
          "transit": {
            "num": 2,
            "den": 2,
            "rate": 1
          }
        },
        "added_walk_min_mean": -0.8,
        "skipped": []
      }
    },
    "d-alt-hold": {
      "source": "final_project_cs/eval/reports/2026-10-08_dining_alternatives_holdout_v3-domains.json",
      "summary": {
        "accuracy": {
          "num": 8,
          "den": 8,
          "rate": 1
        },
        "acceptable": {
          "num": 8,
          "den": 8,
          "rate": 1
        },
        "violations": {
          "num": 0,
          "den": 8,
          "rate": 0
        },
        "violations_any_seed": {
          "num": 0,
          "den": 8,
          "rate": 0
        },
        "labels": {
          "correct": 7,
          "ok": 0,
          "correct_no_change": 1,
          "wrong_violation": 0,
          "wrong": 0,
          "missed": 0,
          "wrong_change": 0,
          "unstable": 0
        },
        "by_group": {
          "brand": {
            "num": 1,
            "den": 1,
            "rate": 1
          },
          "move": {
            "num": 1,
            "den": 1,
            "rate": 1
          },
          "sanity": {
            "num": 2,
            "den": 2,
            "rate": 1
          },
          "similar": {
            "num": 4,
            "den": 4,
            "rate": 1
          }
        },
        "added_walk_min_mean": -0.9,
        "skipped": []
      }
    }
  }
}
```

### 채점 해석 대조

- Activity `metrics.py:22`: `value in acceptable`이면 correct, 허용 밖 unknown은 safe_unknown, 허용 밖 확정값은 dangerous.
- 52개 × 3회 = 156관측, 정답 집합 일치 154/156 = 98.7%. labeler는 `claude(작성자) — 사람 검토 전`.
- Activity CI는 case 단위 bootstrap 10,000회, seed 7. 반복 관측 156개를 독립 사례로 세지 않는다.
- Dining 장소 runner의 `chat=None`와 기록의 `llm=off` 확인. 원장의 장소 수 1,888은 당시 실험 환경값이며 현재 DB 실측이 아니다.
- Dining 대체 runner 설명 6~10행: DB·외부 API·모델 호출 없음, 합성 장소·좌표·시간. 예약/고정 보호는 평가 밖.
- Dining seed 5는 장소 ID를 바꿔 동률 처리 일관성을 검사한다.

## 3. RAG 자료 수와 실행 경로

```powershell
git grep -c '^## ' 180c56ae -- final_project_cs/knowledge/travel/documents
git show 180c56ae:final_project_cs/knowledge/travel/manifest.json
git show 180c56ae:final_project_cs/app/infrastructure/rag/retriever.py
git show 180c56ae:final_project_cs/app/domains/travel_ops/instances/_shared/itinerary_team.py
git show 180c56ae:final_project_cs/tests/integration/rag/test_travel_corpus_retrieval.py
```

실제 Markdown 절 개수:
```text
t01 11
t02 10
t03 10
t04 12
t05 11
t06 11
t07 10
t08 11
t09 10
t10 10
t11 13
t12 11
합계: 12문서, 130개 절
```

- manifest의 문서·절 수와 실제 파일 수·절 수 일치.
- 실제 DB의 문서·청크·벡터 적재 개수는 조회하지 않았다.
- retriever는 tenant/scope 제한 + 활성 벡터 컬럼 cosine top-k를 사용한다. guardrails의 top_k=8, hybrid_bm25_enabled=false, rerank_enabled=false 확인.
- `question_answer:439`는 고객용 문장 상위 2개 + 구조화 예약 조건을 조합한다.
- 기존 여행 분류 자료 파일 행 수도 확인했다: `travel_golden.jsonl` 72행, `travel_holdout.jsonl` 24행. 이는 Activity Judge의 52라벨과 별도 자료다. 파일 이름만으로 Dining 전용 종단 평가가 충분하다고 판단하지 않는다.

## 4. 현재 코드와 미래 계획 대조

- Activity: `team.py:105` judge 주입·모드, `:331` feasibility, `:499` shadow, `judge/llm.py:109` 이후 근거 검사.
- Activity 최신 문서: `wiki/teams/activity.md:35` 이후 현재 구현·멘토 기준·사람 라벨 검토 필요. 에이전트 루프 미착수 명시.
- Dining: `team.py:149` 실제 execute, `:243` 조건 판정. `wiki/teams/dining-mcp-boundary.md:196` 이후 Q 측정·모델 종단·도입 결정 대기.
- 근처 기준점 문제: `pipeline.py`가 resolve에 near를 넘김 → `places.py`의 dining 경로는 `_tour(dining, query, ...)` → `_tour`는 `find(name, area_code=SEOUL_AREA_CODE)`만 호출 → `LedgerPlaceLookup.find`는 ctx callback의 near만 사용. 기존 재측정 보고서의 원인 설명과 일치. 새 실서버 재현은 미수행.
- 별도 판정: 코어 감시, Dining tick 함수, 고객 API 접수, Judge 라이브러리 존재를 실제 운영 연결 완료와 혼동하지 않았다.

## 5. 검증 한계

이번 조사로 확인한 것은 소스·기존 기록·실험 범위다. 병합 후 회귀 통과, 실환경 모델 사용 여부, DB 정합성, 운영 품질은 아직 판정하지 않았다. 새 평가 결과를 만들지 않았으며 기록된 과거 수치를 현재 실측으로 표현하지 않았다.

## 6. 산출물 확인

- 보고서의 고정 커밋 소스 링크 26개를 21개 파일로 중복 제거해 `git cat-file -e`로 확인: 21/21 = 100% 존재. 인용 줄 번호도 해당 소스 길이 안에 있다.
- 보고서·근거 문서의 충돌 표식: 0건. 새 문서에서 API 키 형태·DB 연결 문자열·Bearer 토큰 형태가 검출되지 않았다.
- wiki 로그는 기존 내용을 보존하고 이 조사 링크 2행만 추가했다. `git diff --check -- final_project_cs/wiki/log.md` 최종 종료 0, 출력 없음. 추가 부분의 CRLF 경고는 해당 부분만 정리했다.
- 위 결과는 문서 점검 결과이며 애플리케이션 테스트 통과율이 아니다.

