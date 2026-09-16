from pathlib import Path


def test_lead_engine_suppresses_httpx_info_logging():
    source = Path('lead_engine_main.py').read_text(encoding='utf-8')
    assert 'logging.getLogger("httpx").setLevel(logging.WARNING)' in source
