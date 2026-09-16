from pathlib import Path


def test_villa_bot_main_does_not_install_traffic_engine():
    source = Path('main.py').read_text(encoding='utf-8')
    forbidden = [
        'cozy_traffic_runtime',
        'cozy_traffic_manager',
        'cozy_traffic_scoring_patch',
        'cozy_traffic_discovery_patch',
        'traffic_discover',
        'ensure_smoke_started',
    ]
    for token in forbidden:
        assert token not in source
