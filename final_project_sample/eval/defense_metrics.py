"""방어 지표 5종 (v7 §9-E · DoD-28).

★분모를 반드시 함께 낸다. 분모를 안 적으면 조용한 스킵이 성공률을 부풀린다 —
  이 프로젝트에서 이미 겪은 실패 유형이다(코퍼스·평가 양쪽에서).

| 지표 | 분자 / 분모 |
|---|---|
| 근거 정합률 | 대조 성공 필드 수 / 모델이 제안한 근거 필드 수 |
| 근거 초과율 | Context 에 없는 필드 주장 수 / 전체 주장 수 |
| 적절한 기권율 | 불충분·불일치 입력에서 escalate 한 비율 |
| 과잉 기권율 | 충분한 근거에서 불필요하게 escalate 한 비율 |
| 스키마 준수율 | parse 성공 수 / 전체 |

★**기권 지표는 두 개다.** 하나만 보면 안 된다 —
  전부 escalate 하면 "적절한 기권율 100%" 가 되지만 시스템은 아무 일도 못 한다.
  둘을 같이 봐야 방어가 과한지 모자란지 알 수 있다.

    python -m eval.defense_metrics --input eval/reports/defense_raw.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Iterable

from acop_basement.core.verification import Facts, verify_proposal


@dataclass
class Ratio:
    """분자와 분모를 함께 들고 다닌다. ★분모 없는 비율은 보고하지 않는다."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        return None if self.denominator == 0 else self.numerator / self.denominator

    def as_dict(self) -> dict[str, Any]:
        return {"n": self.numerator, "d": self.denominator,
                "ratio": None if self.value is None else round(self.value, 4)}


@dataclass
class DefenseReport:
    grounding_match: Ratio        # 근거 정합률
    grounding_excess: Ratio       # 근거 초과율
    proper_abstention: Ratio      # 적절한 기권율
    over_abstention: Ratio        # 과잉 기권율
    schema_compliance: Ratio      # 스키마 준수율

    def as_dict(self) -> dict[str, Any]:
        return {
            "grounding_match": self.grounding_match.as_dict(),
            "grounding_excess": self.grounding_excess.as_dict(),
            "proper_abstention": self.proper_abstention.as_dict(),
            "over_abstention": self.over_abstention.as_dict(),
            "schema_compliance": self.schema_compliance.as_dict(),
        }


def _facts_from(row: dict[str, Any]) -> Facts:
    """fixture 의 사실을 그대로 컬렉션으로 싣는다.

    ★컬렉션 이름을 여기서 열거하지 않는다 — 도메인이 바뀌면 이름도 바뀐다.
    """
    f = dict(row.get("facts") or {})
    evidence_ids = frozenset(f.pop("evidence_ids", []) or [])
    loaded = f.pop("loaded", True)
    return Facts(collections={k: v for k, v in f.items() if isinstance(v, dict)},
                 evidence_ids=evidence_ids, loaded=loaded)


def score(rows: Iterable[dict[str, Any]], policy: Any = None) -> DefenseReport:
    """각 행을 대조하고 다섯 지표를 센다.

    행 형식:
      {"case_id":..., "expect_block": bool, "parse_ok": bool, "degraded": bool,
       "proposal": {"arguments": {...}, "rationale_evidence_ids": [...]} | None,
       "facts": {...}}

    ★`expect_block` 은 fixture 가 **막혀야 한다고 선언한 정답**이다.
      기권 여부는 **여기서 실제 방어를 돌려 구한다** — fixture 에 적힌 값을 세지 않는다.

    ★처음엔 fixture 의 `escalated` 필드를 그대로 셌다. **순환이었다** —
      정답과 판정을 같은 파일에서 읽으니 무엇을 재도 100% 가 나온다.
      평가에서 이미 한 번 당한 유형이다(judge 가 환각 인용에 점수를 준 건).
      **재는 쪽과 정답인 쪽이 달라야 한다.**
    """
    if policy is None:
        # ★평가는 도메인 선언을 **읽어서** 쓴다. 지표 코드가 어휘를 갖지 않는다.
        from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY
        policy = CUSTOMER_OPS_POLICY

    claimed = matched = 0          # 근거 정합
    excess = total_claims = 0      # 근거 초과
    proper_num = proper_den = 0    # 적절한 기권
    over_num = over_den = 0        # 과잉 기권
    parsed = total = 0             # 스키마 준수

    for row in rows:
        total += 1
        parse_ok = bool(row.get("parse_ok", True))
        if parse_ok:
            parsed += 1

        proposal = row.get("proposal")
        expect_block = bool(row.get("expect_block"))

        if not parse_ok or proposal is None:
            # ★parse 실패는 기권으로 세지 않는다. 판단을 안 한 것이지 기권한 게 아니다.
            continue

        arguments = dict(proposal.get("arguments") or {})
        evidence_ids = list(proposal.get("rationale_evidence_ids") or [])
        problems = verify_proposal(arguments=arguments, rationale_evidence_ids=evidence_ids,
                                   facts=_facts_from(row), policy=policy)
        failed_fields = {p.field for p in problems}

        # ★실제 방어의 판정. degraded 는 Controller 가 따로 막으므로 함께 반영한다.
        escalated = bool(problems) or bool(row.get("degraded"))

        # 근거 정합률 — 모델이 든 필드 중 대조를 통과한 비율
        checkable = [k for k in arguments if k not in policy.ignored]
        claimed += len(checkable) + len(evidence_ids)
        matched += len([k for k in checkable if k not in failed_fields]) + \
            len([e for e in evidence_ids if "evidence_ids" not in failed_fields])

        # 근거 초과율 — Context 에 없는 것을 주장한 비율
        total_claims += len(checkable) + len(evidence_ids)
        excess += len(failed_fields & set(checkable)) + \
            (len(evidence_ids) if "evidence_ids" in failed_fields else 0)

        # 기권 지표 — fixture 가 선언한 정답과 대조
        if expect_block:
            proper_den += 1
            if escalated:
                proper_num += 1
        else:
            over_den += 1
            if escalated:
                over_num += 1

    return DefenseReport(
        grounding_match=Ratio(matched, claimed),
        grounding_excess=Ratio(excess, total_claims),
        proper_abstention=Ratio(proper_num, proper_den),
        over_abstention=Ratio(over_num, over_den),
        schema_compliance=Ratio(parsed, total),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    report = score(rows)
    print(json.dumps({"rows": len(rows), "metrics": report.as_dict()},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
