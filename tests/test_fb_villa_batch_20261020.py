# -*- coding: utf-8 -*-
import tempfile
import unittest
from unittest.mock import AsyncMock
from fb_villa_batch_20261020 import run_batch
from pathlib import Path

from fb_villa_batch_20261020 import ListingSpec, render_caption, validate_manifest


def listing(**overrides):
    data = dict(
        lot_id="V01",
        title="Plai Laem Pool Villa",
        district="Plai Laem",
        source_url="https://www.facebook.com/marketplace/item/2304437457076333/",
        seller_url="https://www.facebook.com/profile.php?id=588505707",
        bedrooms=4,
        price_thb=120000,
        price_terms="monthly asking price; final price for 31 nights must be confirmed",
        photo_paths=(),
        notes="Private pool; 3 bathrooms",
    )
    data.update(overrides)
    return ListingSpec(**data)


class VillaBatchManifestTests(unittest.TestCase):
    def test_accepts_valid_four_bedroom_listing(self):
        result = validate_manifest([listing()])
        self.assertEqual(result[0].lot_id, "V01")

    def test_rejects_non_four_bedroom_listing(self):
        with self.assertRaisesRegex(ValueError, "exactly 4 bedrooms"):
            validate_manifest([listing(bedrooms=3)])

    def test_rejects_duplicate_source_urls(self):
        with self.assertRaisesRegex(ValueError, "duplicate source_url"):
            validate_manifest([listing(), listing(lot_id="V02")])

    def test_rejects_duplicate_lot_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate lot_id"):
            validate_manifest([listing(), listing(source_url="https://www.facebook.com/marketplace/item/2/")])

    def test_rejects_missing_required_urls(self):
        with self.assertRaises(ValueError):
            validate_manifest([listing(source_url="")])

    def test_rejects_more_than_ten_photos(self):
        with self.assertRaisesRegex(ValueError, "at most 10"):
            validate_manifest([listing(photo_paths=tuple(f"/tmp/{n}.jpg" for n in range(11)))])

    def test_caption_contains_dates_source_and_cta(self):
        caption = render_caption(listing(), "V01")
        self.assertIn("24.12.2026–24.01.2027", caption)
        self.assertIn("31 ноч", caption)
        self.assertIn("2304437457076333", caption)
        self.assertIn("Cozy Asia", caption)
        self.assertLessEqual(len(caption), 1024)

    def test_caption_escapes_html(self):
        caption = render_caption(listing(title="<Villa> & pool"), "V01")
        self.assertIn("&lt;Villa&gt; &amp; pool", caption)

    def test_dry_run_does_not_create_client(self):
        factory = AsyncMock(side_effect=AssertionError("client must not be created"))
        result = __import__("asyncio").run(run_batch([listing()], dry_run=True, client_factory=factory))
        self.assertEqual(result[0]["status"], "dry_run")
        factory.assert_not_awaited()

    def test_publish_isolates_listing_failure_and_verifies_readback(self):
        class Message:
            def __init__(self, mid):
                self.id = mid

        class FakeClient:
            def __init__(self):
                self.sent = 0
                self.disconnected = False
            async def get_entity(self, channel):
                return channel
            async def send_file(self, channel, files, caption, album):
                self.sent += 1
                if self.sent == 1:
                    raise RuntimeError("simulated send failure")
                return [Message(42)]
            async def get_messages(self, channel, ids):
                return Message(ids)
            async def disconnect(self):
                self.disconnected = True

        client = FakeClient()
        photo = tempfile.NamedTemporaryFile(suffix=".jpg")
        async def factory():
            return client
        async def no_duplicate(*args, **kwargs):
            return None
        first = listing(photo_paths=(photo.name,))
        second = listing(lot_id="V02", source_url="https://www.facebook.com/marketplace/item/2/", photo_paths=(photo.name,))
        result = __import__("asyncio").run(run_batch([first, second], dry_run=False, client_factory=factory, duplicate_checker=no_duplicate))
        self.assertEqual([row["status"] for row in result], ["failed", "published"])
        self.assertTrue(client.disconnected)
        photo.close()


if __name__ == "__main__":
    unittest.main()

