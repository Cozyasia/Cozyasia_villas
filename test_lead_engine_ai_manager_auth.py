from pathlib import Path


def test_lead_engine_wires_dedicated_ai_manager_auth_handlers():
    source = Path('lead_engine_main.py').read_text(encoding='utf-8')
    assert 'import ai_manager_auth' in source
    assert 'ai_manager_auth.install_handlers' in source
