import pytest
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard

NAME = 'travel.booking.enabled'

@pytest.fixture(autouse=True)
def reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


def test_admin_lists_booking_off_by_default_and_validates_boolean():
    spec = web_guard.specs().get(NAME)
    assert spec is not None, 'product admin must list booking master switch'
    assert spec.type == 'bool' and spec.default is False
    assert spec.check(True) is None
    assert spec.check(False) is None
    assert spec.check(1) == 'wrong_type'
    assert spec.check('true') == 'wrong_type'

@pytest.mark.parametrize('value, expected', [(None, False),(True, True),(False, False),(1, False),('true', False)])
def test_booking_requires_explicit_tenant_boolean(value, expected):
    settings_hook.register(lambda tenant, name: value if tenant == 'owner' and name == NAME else None)
    enabled = getattr(settings_hook, 'booking_enabled', None)
    assert enabled is not None, 'runtime setting reader must exist'
    assert enabled('owner') is expected
    assert enabled('other') is False
