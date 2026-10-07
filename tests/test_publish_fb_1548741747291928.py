# -*- coding: utf-8 -*-
import importlib
from pathlib import Path

import pytest
from telethon.extensions import html as telethon_html

import channel_publication_policy


MODULE_NAME = "publish_fb_1548741747291928"


def _publisher():
    return importlib.import_module(MODULE_NAME)


def test_listing_contract_and_public_caption(monkeypatch):
    mod = _publisher()
    monkeypatch.setattr(
        mod,
        "EXTRA_FOLDER_URL",
        "https://drive.google.com/drive/folders/test-public-folder",
    )

    assert mod.CHANNEL == "samuirental"
    assert mod.EXPECTED_LOT == "1206"
    assert mod.PRICE_MONTHLY == 65000
    assert mod.COMMISSION == 5000
    assert mod.SOURCE_URL == "https://www.facebook.com/marketplace/item/1548741747291928/"
    assert mod.MAP_URL == (
        "https://www.google.com/maps/search/?api=1&query="
        "International+School+of+Samui"
    )

    caption = mod._caption_html("1206")
    assert "65 000 THB/мес." in caption
    assert "Комиссия Cozy Asia: 5 000 THB" in caption
    assert "контракт: 1 год" in caption.lower()
    assert "Вода: 60 THB/м³" in caption
    assert "cozy_asia_bot?start=rent_1206" in caption
    assert "cozy_asia_bot?start=search" in caption
    assert mod.MAP_URL in caption
    assert mod.EXTRA_FOLDER_URL in caption
    assert "+66 80 537 2533" not in caption
    assert "080-537-2533" not in caption
    assert "marketplace/profile" not in caption
    assert mod.SOURCE_URL not in caption

    text, entities = telethon_html.parse(caption)
    assert len(text) <= 1024
    result = channel_publication_policy.validate_listing_caption(
        text, entities, "1206", mod.CHANNEL
    )
    assert result["bot"] == "cozy_asia_bot"


def test_photo_manifest_contract_is_exact():
    mod = _publisher()
    expected_selected = [
        "22.jpg",
        "01.jpg",
        "02.jpg",
        "05.jpg",
        "04.jpg",
        "07.jpg",
        "09.jpg",
        "14.jpg",
        "20.jpg",
        "12.jpg",
    ]
    expected_overflow = [
        "03.jpg",
        "06.jpg",
        "08.jpg",
        "10.jpg",
        "11.jpg",
        "13.jpg",
        "15.jpg",
        "16.jpg",
        "17.jpg",
        "18.jpg",
        "19.jpg",
        "21.jpg",
    ]
    assert mod.TELEGRAM_PHOTO_NAMES == expected_selected
    assert mod.ADDITIONAL_PHOTO_NAMES == expected_overflow
    assert len(set(mod.TELEGRAM_PHOTO_NAMES + mod.ADDITIONAL_PHOTO_NAMES)) == 22

    manifest = {
        "telegram_selected": expected_selected,
        "additional_photos": expected_overflow,
    }
    selected, overflow = mod._validate_manifest(manifest)
    assert selected == expected_selected
    assert overflow == expected_overflow


def test_photo_manifest_rejects_reordered_selected_files():
    mod = _publisher()
    manifest = {
        "telegram_selected": list(reversed(mod.TELEGRAM_PHOTO_NAMES)),
        "additional_photos": mod.ADDITIONAL_PHOTO_NAMES,
    }
    with pytest.raises(RuntimeError, match="Unexpected Telegram photo manifest"):
        mod._validate_manifest(manifest)


def test_main_routes_only_when_explicit_flag_is_enabled():
    root = Path(__file__).resolve().parents[1]
    source = (root / "main.py").read_text(encoding="utf-8")
    assert 'os.getenv("PUBLISH_FB_1548741747291928", "0")' in source
    assert "import publish_fb_1548741747291928" in source
    assert "_fb_1548741747291928.run_service_mode()" in source
