# explain_billing v2

Explain the billing or subscription comparison in plain language. Return a json object only with `outcome`, `confidence`, `answer`, `next_action`, `evidence`, `decisions`, `action_proposals`, `failure_code`, and `warnings`. Every material claim must be supported by supplied evidence. If policy evidence is absent or degraded, escalate instead of answering.
