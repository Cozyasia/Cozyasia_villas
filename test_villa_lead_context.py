import villa_lead_context as subject


def test_parses_precise_deep_link():
    got = subject.parse_rent_payload("rent_v_a_1931_1237")
    assert got == subject.LeadLotIdentity(lot_id="1237", channel="a", message_id="1931")


def test_legacy_link_keeps_lot_but_not_false_precision():
    assert subject.parse_rent_payload("rent_1237") == subject.LeadLotIdentity(lot_id="1237")


def test_duplicate_legacy_lot_fails_closed(monkeypatch):
    rows = [
        {"№ лота — малый канал": "1237", "Внутренний ID": "CA-1"},
        {"№ лота — малый канал": "1237", "Внутренний ID": "CA-2"},
    ]
    monkeypatch.setattr(subject, "_load_registry_rows", lambda: rows)
    result = subject.resolve_owner_context(subject.LeadLotIdentity(lot_id="1237"))
    assert result.status == "требует проверки"
    assert "не подставлен автоматически" in result.text


def test_precise_link_returns_matching_private_card(monkeypatch):
    rows = [
        {
            "Ссылка — малый канал": "https://t.me/arenda_vill_samui/1931",
            "№ лота — малый канал": "1237",
            "Внутренний ID": "CA-1237",
            "Статус контакта": "подтверждён",
            "Имя собственника / агента": "Owner",
            "WhatsApp собственника": "+66000000000",
        }
    ]
    monkeypatch.setattr(subject, "_load_registry_rows", lambda: rows)
    result = subject.resolve_owner_context(subject.LeadLotIdentity(lot_id="1237", channel="a", message_id="1931"))
    assert result.fields["ID"] == "CA-1237"
    assert result.fields["WhatsApp"] == "+66000000000"
