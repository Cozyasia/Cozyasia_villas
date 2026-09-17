from pathlib import Path


def test_control_wires_safe_dry_run_selftest():
    src = Path("lead_engine_control.py").read_text(encoding="utf-8")
    assert "async def cmd_traffic_dry_run_test" in src
    assert 'CommandHandler("traffic_dry_run_test"' in src
    assert '"test_draft_ready"' in src
    assert 'Recipient(telegram_id=0' in src
    assert '"🧪 SELF TEST"' in src
    assert "_draft_keyboard(key)" in src


def test_selftest_has_no_recipient_send_path():
    src = Path("lead_engine_control.py").read_text(encoding="utf-8")
    start = src.index("async def cmd_traffic_dry_run_test")
    end = src.index("async def _monitor_loop", start)
    block = src[start:end]
    assert "send_message(" not in block
    assert "client.send_message" not in block
    assert "resolve_recipient" not in block
