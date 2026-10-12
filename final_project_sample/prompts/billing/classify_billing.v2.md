# classify_billing v2

Classify the billing request using only the supplied customer-scoped facts and policy evidence. Return a json object only with `outcome`, `confidence`, `answer`, `next_action`, `evidence`, `decisions`, `action_proposals`, `failure_code`, and `warnings`. Return a short issue code in `decisions` and confidence. Do not invent policy, payment state, or customer data.
