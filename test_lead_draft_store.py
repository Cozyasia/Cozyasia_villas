import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name('lead_draft_store.py')


def load_module():
    assert MODULE_PATH.exists(), 'lead_draft_store.py must exist'
    spec = importlib.util.spec_from_file_location('lead_draft_store', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeWS:
    def __init__(self):
        self.rows = []
        self.updates = []

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def append_row(self, row, value_input_option=None):
        self.rows.append(list(row))

    def update(self, cell_range, values, value_input_option=None):
        self.updates.append((cell_range, values))
        rownum = int(cell_range.split(':', 1)[0][1:])
        while len(self.rows) < rownum:
            self.rows.append([])
        self.rows[rownum - 1] = list(values[0])


def test_callback_data_fits_telegram_limit():
    m = load_module()
    key = 'a' * 32 + ':9999999999'
    for action in ('send', 'edit', 'cancel'):
        payload = m.callback_data(action, key)
        assert len(payload.encode('utf-8')) <= 64
        assert m.parse_callback(payload) == (action, key)


def test_upsert_and_get_draft_round_trip():
    m = load_module()
    ws = FakeWS()
    ws.rows = [m.DRAFT_HEADERS.copy()]
    record = {
        'key': 'SamuiGroup:12345',
        'status': 'draft_ready',
        'recipient_id': '777',
        'recipient_username': 'client_user',
        'recipient_name': 'Client User',
        'draft': 'Здравствуйте!',
        'source_username': 'SamuiGroup',
        'message_id': '12345',
        'admin_username': 'Cozy_asia',
    }
    m.upsert_draft(ws, record, now='2026-09-17T00:00:00+00:00')
    saved = m.get_draft(ws, 'SamuiGroup:12345')
    assert saved['status'] == 'draft_ready'
    assert saved['recipient_id'] == '777'
    assert saved['draft'] == 'Здравствуйте!'
    assert saved['created_at'] == '2026-09-17T00:00:00+00:00'


def test_update_status_preserves_existing_draft():
    m = load_module()
    ws = FakeWS()
    ws.rows = [m.DRAFT_HEADERS.copy()]
    m.upsert_draft(ws, {
        'key': 'SamuiGroup:12345',
        'status': 'draft_ready',
        'recipient_id': '777',
        'recipient_username': 'client_user',
        'recipient_name': 'Client User',
        'draft': 'Здравствуйте!',
        'source_username': 'SamuiGroup',
        'message_id': '12345',
        'admin_username': 'Cozy_asia',
    }, now='2026-09-17T00:00:00+00:00')
    assert m.update_status(ws, 'SamuiGroup:12345', 'dry_run_approved', now='2026-09-17T00:01:00+00:00')
    saved = m.get_draft(ws, 'SamuiGroup:12345')
    assert saved['status'] == 'dry_run_approved'
    assert saved['draft'] == 'Здравствуйте!'
    assert saved['updated_at'] == '2026-09-17T00:01:00+00:00'
