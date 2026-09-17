from pathlib import Path


def test_main_wires_safe_dry_run_selftest():
    main = Path("lead_engine_main.py").read_text(encoding="utf-8")
    module = Path("lead_engine_selftest.py").read_text(encoding="utf-8")
    assert "import lead_engine_selftest" in main
    assert "lead_engine_selftest.install_handlers(app, cozy_catalog)" in main
    assert "async def cmd_traffic_dry_run_test" in module
    assert 'CommandHandler("traffic_dry_run_test"' in module
    assert '"test_draft_ready"' in module
    assert 'Recipient(telegram_id=0' in module
    assert '"🧪 SELF TEST"' in module


def test_selftest_has_no_recipient_send_or_resolution_path():
    module = Path("lead_engine_selftest.py").read_text(encoding="utf-8")
    assert "send_message(" not in module
    assert "client.send_message" not in module
    assert "resolve_recipient" not in module
    assert "new_client(" not in module
