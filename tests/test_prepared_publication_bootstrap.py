import unittest

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


if __name__ == "__main__":
    unittest.main()
