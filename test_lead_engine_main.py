from pathlib import Path


def test_lead_engine_entrypoint_uses_dedicated_bot_token_and_polling():
    source = Path('lead_engine_main.py').read_text(encoding='utf-8')
    assert 'COZY_LEAD_BOT_TOKEN' in source
    assert 'run_polling' in source
    assert 'lead_engine_control.install_handlers' in source
    assert 'cozy_traffic_scoring_patch.apply' in source
    assert 'cozy_traffic_discovery_patch.apply' in source
    assert 'ThreadingHTTPServer' in source


def test_lead_engine_entrypoint_does_not_use_villa_bot_token_name():
    source = Path('lead_engine_main.py').read_text(encoding='utf-8')
    assert 'TELEGRAM_BOT_TOKEN' not in source


def test_lead_engine_creates_event_loop_before_run_polling_for_python_314():
    source = Path('lead_engine_main.py').read_text(encoding='utf-8')
    assert 'asyncio.new_event_loop()' in source
    assert 'asyncio.set_event_loop' in source
    assert source.index('asyncio.set_event_loop') < source.index('app.run_polling')
