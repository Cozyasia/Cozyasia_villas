import importlib


def test_listing_contract_values():
    mod = importlib.import_module('publish_choengmon_1205')
    assert mod.CHANNEL == 'samuirental'
    assert mod.LOT_ID == 1205
    assert mod.PRICE_ONE_MONTH == 49000
    assert mod.PRICE_LONG_TERM == 45000
    assert mod.COMMISSION == 4000
    assert mod.OWNER_NAME == 'Nam'
    assert mod.OWNER_PHONE == '+66935795393'
    assert 'cozy_asia_bot?start=rent_1205' in mod.CAPTION
    assert 'cozy_asia_bot?start=search' in mod.CAPTION
    assert '+66935795393' not in mod.CAPTION
    assert 'https://maps.app.goo.gl/fezbG6VJb8orKtAK7?g_st=ic' in mod.CAPTION
