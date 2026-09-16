import asyncio
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name('lead_contact_dry_run.py')


def load_module():
    assert MODULE_PATH.exists(), 'lead_contact_dry_run.py must exist'
    spec = importlib.util.spec_from_file_location('lead_contact_dry_run', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_opportunity():
    return {
        'key': 'SamuiGroup:12345',
        'source_username': 'SamuiGroup',
        'source_title': 'SAMUI CHAT',
        'message_id': '12345',
        'text': 'Ищу виллу 2 спальни на Ламае на 2 месяца, бюджет до 80000 бат.',
        'districts': 'Ламай',
        'budget': '80000 THB',
        'bedrooms': '2',
        'date_text': '',
        'duration_text': '2 месяца',
        'occupants': '',
        'pets': '',
        'link': 'https://t.me/SamuiGroup/12345',
    }


def test_prompt_uses_known_request_and_forbids_inventing_facts():
    m = load_module()
    system, user = m.build_draft_prompt(sample_opportunity())
    joined = (system + '\n' + user).lower()
    assert '80000 thb' in joined
    assert 'ламай' in joined
    assert '2' in joined
    assert 'не выдум' in joined or 'do not invent' in joined
    assert 'availability' in joined or 'доступност' in joined


def test_preview_is_explicitly_dry_run_and_names_recipient():
    m = load_module()
    recipient = m.Recipient(telegram_id=777, username='client_user', display_name='Client User')
    text = m.build_dry_run_preview(sample_opportunity(), recipient, 'Здравствуйте! Могу помочь с подбором.')
    assert 'DRY RUN' in text
    assert 'НЕ отправлено' in text or 'не отправлено' in text
    assert '@client_user' in text
    assert '@CozyAsiaAI' in text
    assert 'Здравствуйте!' in text


def test_contact_mode_defaults_to_dry_run(monkeypatch):
    monkeypatch.delenv('COZY_LEAD_CONTACT_MODE', raising=False)
    m = load_module()
    assert m.contact_mode() == 'dry_run'
    assert m.live_send_enabled() is False


def test_resolve_recipient_from_original_message_sender():
    m = load_module()

    class Sender:
        id = 777
        username = 'client_user'
        first_name = 'Client'
        last_name = 'User'
        bot = False

    class Message:
        sender_id = 777
        async def get_sender(self):
            return Sender()

    class Client:
        async def get_entity(self, value):
            return f'entity:{value}'
        async def get_messages(self, entity, ids):
            assert entity == 'entity:SamuiGroup'
            assert ids == 12345
            return Message()

    recipient = asyncio.run(m.resolve_recipient(Client(), 'SamuiGroup', 12345))
    assert recipient.telegram_id == 777
    assert recipient.username == 'client_user'
    assert recipient.display_name == 'Client User'


def test_bot_sender_is_rejected():
    m = load_module()

    class Sender:
        id = 999
        username = 'somebot'
        first_name = 'Bot'
        last_name = ''
        bot = True

    class Message:
        async def get_sender(self):
            return Sender()

    class Client:
        async def get_entity(self, value):
            return object()
        async def get_messages(self, entity, ids):
            return Message()

    try:
        asyncio.run(m.resolve_recipient(Client(), 'SamuiGroup', 12345))
    except m.RecipientResolutionError as exc:
        assert 'bot' in str(exc).lower()
    else:
        raise AssertionError('bot sender must be rejected')
