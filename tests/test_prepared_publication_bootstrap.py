import tempfile
import unittest
from pathlib import Path

import publish_prepared_three_bootstrap_20260920 as bootstrap


class PreparedPublicationBootstrapTests(unittest.TestCase):
    def test_preloaded_additional_ids_tracks_all_prepared_overflow_photos(self):
        helper = getattr(bootstrap, "_preloaded_additional_ids", None)
        self.assertIsNotNone(
            helper,
            "bootstrap must provide a non-uploading overflow-photo adapter for retry mode",
        )
        record = {
            "additional_photos": ["photo_11.jpg", "photo_12.jpg"],
        }
        self.assertEqual(
            ["preloaded-01", "preloaded-02"],
            helper(record),
        )

    def test_retry_record_filter_selects_only_requested_lot(self):
        helper = getattr(bootstrap, "_filter_records_for_retry", None)
        self.assertIsNotNone(
            helper,
            "bootstrap must be able to isolate the one unpublished lot on retry",
        )
        records = [
            {"lot": "1214", "source_id": "first"},
            {"lot": "1215", "source_id": "second"},
        ]
        self.assertEqual(
            [{"lot": "1215", "source_id": "second"}],
            helper(records, "1215"),
        )

    def test_additional_photo_paths_export_only_overflow_files(self):
        helper = getattr(bootstrap, "_additional_photo_paths", None)
        self.assertIsNotNone(
            helper,
            "bootstrap must expose prepared overflow photos for recovery without republishing",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_dir = root / "photos" / "1215"
            photo_dir.mkdir(parents=True)
            for name in ("photo_02.jpg", "photo_03.jpg"):
                (photo_dir / name).write_bytes(b"jpg")
            records = [{"lot": "1215", "additional": ["photo_02.jpg", "photo_03.jpg"]}]
            self.assertEqual(
                [photo_dir / "photo_02.jpg", photo_dir / "photo_03.jpg"],
                helper(root, records, "1215"),
            )


if __name__ == "__main__":
    unittest.main()
