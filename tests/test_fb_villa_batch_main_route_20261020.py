# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


class MainRouteTests(unittest.TestCase):
    def test_batch_route_is_explicitly_gated(self):
        source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("PUBLISH_FB_VILLA_BATCH_20261020", "0")', source)
        self.assertIn("import fb_villa_batch_20261020 as _fb_villa_batch", source)
        self.assertIn("_fb_villa_batch.run_service_mode()", source)


if __name__ == "__main__":
    unittest.main()
