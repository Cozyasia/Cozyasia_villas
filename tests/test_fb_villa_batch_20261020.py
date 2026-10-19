# -*- coding: utf-8 -*-
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
