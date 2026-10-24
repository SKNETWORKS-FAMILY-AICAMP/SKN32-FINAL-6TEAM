import pytest
from uuid import uuid4
from app.core.actions import ActionRejected
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.actions.booking_actions import APPROVED_HANDLERS
from app.domains.travel_ops.instances.booking.team import BookingTeam
from app.domains.travel_ops.instances.booking_handoff import BookingHandoffTeam
from app.domains.travel_ops.instances.lodging.team import LodgingTeam
from app.tools.read_tools import ReadToolbox, ToolContext
from .helpers import FakeTools, pack, task

@pytest.fixture(autouse=True)
def off():
    settings_hook.clear()
    yield
    settings_hook.clear()

@pytest.mark.asyncio
@pytest.mark.parametrize('cls, capability', [(BookingTeam, 'flight.assist'), (LodgingTeam,'lodging.assist'),(BookingHandoffTeam,'booking.prepare_change'),(BookingHandoffTeam,'booking.prepare_cancel'),(BookingHandoffTeam,'booking.prepare_revert')])
async def test_off_blocks_new_booking_entry_without_tool_or_model_calls(cls, capability):
    tools=FakeTools({})
    req=task(cls.manifest.team_id, capability, pack(cls.manifest.team_id), cls.manifest.allowed_tools)
    result=await cls(tools).execute(req)
    assert result.decisions == [{'booking_disabled': True}]
    assert not tools.calls and not result.action_proposals

@pytest.mark.asyncio
@pytest.mark.parametrize('cls, capability', [(BookingTeam,'flight.status'),(BookingHandoffTeam,'booking.verify'),(LodgingTeam,'lodging.status')])
async def test_off_preserves_existing_booking_read_and_locked(cls,capability):
    tools=FakeTools({'read.booking': {'booking_id':'b1','status':'confirmed','locked':True},'read.supplier':{'status':'confirmed'}})
    req=task(cls.manifest.team_id,capability,pack(cls.manifest.team_id),cls.manifest.allowed_tools)
    result=await cls(tools).execute(req)
    assert tools.calls and result.outcome == 'completed'
    assert not result.action_proposals

@pytest.mark.asyncio
async def test_off_preserves_existing_flight_status_through_normal_assist_interpretation():
    tools=FakeTools({'read.booking':{'booking_id':'b1','locked':True,'status':'confirmed'}})
    req=task('flight','flight.assist',pack('flight'),BookingTeam.manifest.allowed_tools,input_text='항공권 예약 상태 알려줘')
    result=await BookingTeam(tools).execute(req)
    assert result.decisions[0].get('locked') is True
    assert [name for name,_ in tools.calls]==['read.booking']
    assert not result.action_proposals


@pytest.mark.parametrize('handler', APPROVED_HANDLERS)
def test_off_blocks_previously_approved_execution_before_any_db_write(handler):
    class NoDatabase:
        def cursor(self):pytest.fail('OFF must not access booking DB')
    with pytest.raises(ActionRejected, match='booking_disabled'):
        handler.apply(NoDatabase(),tenant_id='owner',customer_id=uuid4(),case_id=uuid4(),arguments={'booking_id':str(uuid4())})

@pytest.mark.parametrize('method,kwargs',[('booking_search_flights',dict(origin='GMP',destination='CJU',depart_date='2026-12-01')),('booking_search_transit',dict(mode='train',origin='서울',destination='부산',depart_date='2026-12-01'))])
def test_off_blocks_direct_search_tool_before_provider(method,kwargs):
    class NoProvider:
        def __getattr__(self,name):pytest.fail('OFF must not call provider')
    box=ReadToolbox.__new__(ReadToolbox)
    box.travel=NoProvider()
    result=getattr(box,method)(pack('flight'),**kwargs)
    assert result == {'booking_disabled': True}


def test_off_blocks_standalone_stay_search_but_not_existing_lodging_itinerary(monkeypatch):
    from app.domains.travel_ops.components.booking import offers
    box=ReadToolbox.__new__(ReadToolbox)
    box.travel=object()
    calls=[]
    monkeypatch.setattr(offers,'search_stays',lambda *a,**kw:calls.append(kw) or {'options':[]})
    kwargs=dict(keyword='서울',check_in='2026-12-01',check_out='2026-12-02')
    assert box.booking_search_stays(ToolContext.from_pack(pack('lodging')),**kwargs)=={'booking_disabled':True}
    existing=pack('lodging',state={'subject_ref':{'kind':'trip','id':str(uuid4()),'part_id':'stay-1'}})
    assert box.booking_search_stays(ToolContext.from_pack(existing),**kwargs)=={'options':[]}
    assert len(calls)==1


@pytest.mark.asyncio
async def test_explicit_on_allows_handoff_proposal_but_does_not_execute_transaction():
    settings_hook.register(lambda tenant,name:True if name==settings_hook.BOOKING else None)
    tools=FakeTools({'read.booking':{'booking_id':'b1','status':'confirmed'},'read.policy':[{'source':'test-policy'}]})
    req=task('booking_handoff','booking.prepare_change',pack('booking_handoff'),BookingHandoffTeam.manifest.allowed_tools)
    result=await BookingHandoffTeam(tools).execute(req)
    assert len(result.action_proposals)==1
    assert result.next_action.value=='wait_for_approval'
    assert [name for name,_ in tools.calls]==['read.booking','read.policy']


def test_off_preserves_real_existing_stay_lookup_and_booked_lodging_itinerary():
    from .booking.test_lodging_team import test_my_stay_returns_coordinates_address_and_link, test_a_booked_lodging_is_never_changed_and_nothing_is_searched
    test_my_stay_returns_coordinates_address_and_link()
    test_a_booked_lodging_is_never_changed_and_nothing_is_searched()


def test_off_preserves_real_booked_flight_itinerary_read():
    from .booking.test_flight_team import test_a_booked_flight_is_never_changed_and_nothing_is_searched
    test_a_booked_flight_is_never_changed_and_nothing_is_searched()


def test_all_existing_teams_remain_registered_when_booking_is_off():
    from app.composition import build_registry
    registered = {m.team_id for m in build_registry().manifests()}
    assert {'activity','dining','mobility','flight','lodging','booking_handoff'} <= registered


@pytest.mark.parametrize('method,offer,kwargs',[
    ('booking_search_flights','search_flights',dict(origin='GMP',destination='CJU',depart_date='2026-12-01')),
    ('booking_search_transit','search_transit',dict(mode='train',origin='서울',destination='부산',depart_date='2026-12-01'))])
def test_explicit_on_allows_authorized_search_and_off_transition_stops_it(monkeypatch,method,offer,kwargs):
    from app.domains.travel_ops.components.booking import offers
    stored={settings_hook.BOOKING:True}
    settings_hook.register(lambda tenant,name:stored.get(name))
    box=ReadToolbox.__new__(ReadToolbox);box.travel=object();calls=[]
    monkeypatch.setattr(offers,offer,lambda *a,**kw:calls.append(kw) or {'options':[]})
    assert getattr(box,method)(pack('flight'),**kwargs)=={'options':[]}
    stored[settings_hook.BOOKING]=False
    assert getattr(box,method)(pack('flight'),**kwargs)=={'booking_disabled':True}
    assert len(calls)==1
