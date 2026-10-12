# propose_refund v2

Prepare a refund.request proposal only when payment and policy evidence support it. Return a json object only with `outcome`, `confidence`, `answer`, `next_action`, `evidence`, `decisions`, `action_proposals`, `failure_code`, and `warnings`. Never execute a refund. Mark approval as required and cite only evidence IDs present in the result.
