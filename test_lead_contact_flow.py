import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name('lead_contact_flow.py')


def load_module():
    assert MODULE_PATH.exists(), 'lead_contact_flow.py must exist'
    spec = importlib.util.spec_from_file_location('lead_contact_flow', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeWS:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
    def get_all_values(self):
        return [list(r) for r in self.rows]
    def append_row(self, row, value_input_option=None):
        self.rows.append(list(row))
    def update(self, cell_range, values, value_input_option=None):
        rownum = int(cell_range.split(':', 1)[0][1:])
        while len(self.rows) < rownum:
            self.rows.append([])
        self.rows[rownum - 1] = list(values[0])


def test_prepare_dry_run_resolves_sender_generates_and_persists(monkeypatch):
    m = load_module()
    opp_headers = ['key','created_at','source_username','source_title','message_id','message_date','score','band','districts','date_text','duration_text','budget','bedrooms','occupants','pets','reasons','text','link']
    opp_row = ['SamuiGroup:12345','','SamuiGroup','SAMUI CHAT','12345','','85','HOT','Ламай','','2 месяца','80000 THB','2','','','','Ищу виллу','https://t.me/SamuiGroup/12345']
    opp_ws = FakeWS([opp_headers, opp_row])
    draft_ws = FakeWS([['key','status','created_at','updated_at','recipient_id','recipient_username','recipient_name','draft','source_username','message_id','admin_username']])

    class Manager:
        OPPORTUNITY_HEADERS = opp_headers
        @staticmethod
        def _opportunity_ws(catalog): return opp_ws
        @staticmethod
        def _worksheet(catalog, title, headers, rows):
            assert title == 'LeadDrafts'
            return draft_ws

    class Client:
        disconnected = False
        async def disconnect(self): self.disconnected = True
    client = Client()

    class Auth:
        @staticmethod
        async def new_client(catalog): return client

    recipient = SimpleNamespace(telegram_id=777, username='client_user', display_name='Client User')

    class Contact:
        @staticmethod
        async def resolve_recipient(c, source, message_id):
            assert c is client
            assert source == 'SamuiGroup'
            assert message_id == 12345
            return recipient
        @staticmethod
        def generate_ai_draft(opportunity):
            assert opportunity['budget'] == '80000 THB'
            return 'Здравствуйте!'

    class Store:
        DRAFT_HEADERS = draft_ws.rows[0]
        @staticmethod
        def upsert_draft(ws, record):
            ws.append_row([record.get(h, '') for h in Store.DRAFT_HEADERS])
            return record

    result = asyncio.run(m.prepare_dry_run(object(), 'SamuiGroup:12345', 'Cozy_asia', manager_module=Manager, auth_module=Auth, contact_module=Contact, store_module=Store))
    assert result.opportunity['source_username'] == 'SamuiGroup'
    assert result.recipient.username == 'client_user'
    assert result.draft == 'Здравствуйте!'
    assert client.disconnected is True
    assert draft_ws.rows[1][0] == 'SamuiGroup:12345'
    assert draft_ws.rows[1][1] == 'draft_ready'


def test_missing_opportunity_is_explicit_error():
    m = load_module()
    class Manager:
        OPPORTUNITY_HEADERS = ['key']
        @staticmethod
        def _opportunity_ws(catalog): return FakeWS([['key']])
    try:
        asyncio.run(m.prepare_dry_run(object(), 'missing:1', 'Cozy_asia', manager_module=Manager, auth_module=object()))
    except m.ContactFlowError as exc:
        assert 'opportunity' in str(exc).lower()
    else:
        raise AssertionError('missing opportunity must fail')
