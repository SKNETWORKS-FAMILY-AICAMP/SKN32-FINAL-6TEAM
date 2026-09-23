# diagnose_entitlement v2

Diagnose entitlement/account mismatch using supplied evidence. Return a json object only with `outcome`, `confidence`, `answer`, `next_action`, `evidence`, `decisions`, `action_proposals`, `failure_code`, and `warnings`. State the likely cause and confidence. Do not mutate permissions and escalate when policy evidence is unavailable.
