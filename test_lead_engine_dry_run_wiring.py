from pathlib import Path


def test_lead_engine_control_wires_dry_run_flow():
    src = Path('lead_engine_control.py').read_text(encoding='utf-8')
    assert 'import lead_contact_flow' in src
    assert 'import lead_contact_dry_run' in src
    assert 'import lead_draft_store' in src
    assert 'prepare_dry_run' in src
    assert 'pattern=r"^draft:(send|edit|cancel):"' in src
    assert 'MessageHandler' in src
    assert 'COZY_LEAD_CONTACT_MODE' in src or 'live_send_enabled' in src
    assert 'send_message(' not in src or 'application.bot.send_message' in src
