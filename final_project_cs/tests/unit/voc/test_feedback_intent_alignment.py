"""Guards the exact class of bug found 2026-08-17: the VOC classifier's
INTENTS drifting out of sync with what Teams actually route.

``feedback.classify()`` is the default classifier wired into the live REST
API (``app/composition.py::build_classifier`` -> ``app/presentation/api/app.py``).
If ``INTENTS`` does not contain every ``case_type`` a Team accepts, a Case
with that intent can never route -- the classifier itself rejects the label
before the Case reaches ``registry.resolve()``.

See ``docs/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md``.
"""
from app.modules.customer_ops import VocStoreManagerTeam
from app.modules.customer_ops.feedback import INTENTS


def test_every_routable_case_type_is_a_classifiable_intent():
    routable = set(VocStoreManagerTeam.manifest.accepted_case_types)
    missing = routable - INTENTS
    assert not missing, (
        f"Team(s) accept case_type(s) {missing} that feedback.INTENTS cannot produce -- "
        "the classifier would reject a correctly-classified Case before it can route. "
        "Add the missing value(s) to feedback.INTENTS."
    )
