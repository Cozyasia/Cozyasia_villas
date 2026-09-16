from types import SimpleNamespace

import lead_engine_control as control


def _lead(**overrides):
    data = dict(source_username='SamuiGroup', source_title='SAMUI CHAT', message_id=12345, score=85, band='HOT', districts=('Lamai',), date_text='1 October', duration_text='2 months', budget_amount=80000, budget_currency='THB', bedrooms=2, occupants=2, pets=False, text='Looking for a 2 bedroom villa in Lamai for 2 months.', link='https://t.me/SamuiGroup/12345')
    data.update(overrides)
    return SimpleNamespace(**data)


def test_lead_key_is_stable():
    assert control._lead_key(_lead()) == 'SamuiGroup:12345'


def test_card_contains_decision_context():
    text = control._build_card_text(_lead())
    assert 'HOT 85' in text
    assert '@SamuiGroup' in text
    assert 'Lamai' in text
    assert '80000' in text
    assert 'https://t.me/SamuiGroup/12345' in text


def test_callback_payloads_fit_telegram_limit():
    lead = _lead(source_username='a' * 32, message_id=9999999999)
    assert len(control._callback_data('approve', lead).encode('utf-8')) <= 64
    assert len(control._callback_data('skip', lead).encode('utf-8')) <= 64
