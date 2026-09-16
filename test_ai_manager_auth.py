from types import SimpleNamespace

import ai_manager_auth as auth


def test_manager_auth_uses_dedicated_sheet():
    assert auth.AUTH_SHEET == "AIManagerAuth"
    assert auth.AUTH_SHEET != "MTProtoAuth"


def test_expected_username_normalization():
    assert auth.normalize_username("@CozyAsiaAI") == "cozyasiaai"
    assert auth.normalize_username(" CozyAsiaAI ") == "cozyasiaai"


def test_account_must_match_expected_manager_username():
    me = SimpleNamespace(username="CozyAsiaAI")
    assert auth.account_matches_expected(me, "@CozyAsiaAI") is True
    wrong = SimpleNamespace(username="OtherAccount")
    assert auth.account_matches_expected(wrong, "@CozyAsiaAI") is False


def test_missing_username_never_matches():
    me = SimpleNamespace(username=None)
    assert auth.account_matches_expected(me, "@CozyAsiaAI") is False
