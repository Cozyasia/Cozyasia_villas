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


if __name__ == "__main__":
    unittest.main()
