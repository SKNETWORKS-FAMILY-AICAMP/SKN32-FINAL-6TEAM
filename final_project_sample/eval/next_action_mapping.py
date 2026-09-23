"""Canonical mapping from dataset action descriptions to the v5 contract enum."""

NEXT_ACTIONS = {
    "continue", "wait_for_input", "wait_for_approval", "call_tool",
    "handoff", "respond", "escalate",
}

# The first verb is not always the terminal action.  Approval gates and
# escalation take precedence; otherwise a request for missing information is
# wait_for_input, a lookup/verification is call_tool, and an explanation or
# feedback acknowledgement is respond.
ACTION_MAP = {
    "investigate_and_propose_refund": "wait_for_approval",
    "explain_policy": "respond",
    "compare_events_and_escalate": "escalate",
    "check_entitlement_and_explain": "call_tool",
    "check_payment_and_status": "call_tool",
    "check_refund_eligibility": "call_tool",
    "redact_and_request_safe_identifier": "wait_for_input",
    "verify_plan_and_require_approval_if_charge": "wait_for_approval",
    "request_minimum_identifiers": "wait_for_input",
    "verify_account_and_escalate": "escalate",
    "calculate_and_explain_proration": "call_tool",
    "explain_original_payment_method_rule": "respond",
    "check_latest_event_and_wait": "wait_for_input",
    "request_invoice_and_check_events": "wait_for_input",
    "verify_and_cancel_or_explain": "call_tool",
    "verify_contact_and_resend": "call_tool",
    "prepare_approval_proposal": "wait_for_approval",
    "degraded_mode_wait_or_escalate": "escalate",
    "check_entitlement_and_wait_or_escalate": "escalate",
    "request_safe_diagnostics": "wait_for_input",
    "collect_diagnostics_and_escalate": "escalate",
    "classify_severity_and_escalate": "escalate",
    "ask_clarifying_question_and_diagnose": "wait_for_input",
    "redact_secret_and_request_safe_diagnostics": "wait_for_input",
    "check_transition_and_entitlement": "call_tool",
    "explain_retry_and_collect_trace": "wait_for_input",
    "request_timestamp_and_diagnostics": "wait_for_input",
    "check_plan_and_propose_approved_change": "wait_for_approval",
    "verify_scope_and_require_approval": "wait_for_approval",
    "ask_for_trace_and_diagnose": "wait_for_input",
    "explain_plan_matrix": "respond",
    "verify_latest_event_and_update": "call_tool",
    "require_human_approval": "wait_for_approval",
    "escalate_with_trace_only": "escalate",
    "record_feedback": "respond",
    "ask_clarifying_question": "wait_for_input",
    "redact_and_record_feedback": "respond",
    "record_feedback_and_open_case": "handoff",
    "record_feedback_and_request_details": "wait_for_input",
    "verify_identity_and_escalate": "escalate",
    "record_minimal_feedback_and_escalate": "escalate",
    "record_feedback_and_handoff": "handoff",
    "request_timestamp": "wait_for_input",
    "redact_and_escalate": "escalate",
    "record_feedback_and_escalate": "escalate",
    "verify_events_and_escalate": "escalate",
    "record_feedback_and_mark_degraded": "respond",
    "check_price_table_and_events": "call_tool",
    "check_latest_event_and_wait": "wait_for_input",
    "check_entitlement_and_escalate": "escalate",
    "request_trace_and_diagnose": "wait_for_input",
}

assert set(ACTION_MAP.values()) <= NEXT_ACTIONS
