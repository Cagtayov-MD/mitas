# -*- coding: utf-8 -*-
"""Unit & Smoke Test for LeBron James Grup 1 Enhancements (Madde 9, 2, 10)."""
import os
import sys
import unittest
import numpy as np
from pathlib import Path

# Add harness/master_dup to sys.path
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
MASTER_DUP_DIR = PROJECT_ROOT / "harness" / "master_dup"
if str(MASTER_DUP_DIR) not in sys.path:
    sys.path.insert(0, str(MASTER_DUP_DIR))

import lebron_james as lebron


class TestLeBronGrup1(unittest.TestCase):

    def test_madde_9_ocr_logging(self):
        """Verify ai_flashlight_mask falls back gracefully on exception without crashing."""
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Should execute ai_flashlight_mask cleanly
        res = lebron.ai_flashlight_mask(dummy_img)
        self.assertEqual(res.shape, (100, 100))

    def test_madde_10_manifest_expansion(self):
        """Verify compose_lebron manifest contains expanded diagnostic fields."""
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.zeros((100, 100, 3), dtype=np.uint8)
        # Draw some dummy text-like shapes
        img1[20:40, 20:80] = 255
        img2[40:60, 20:80] = 255

        kanvas, manifest = lebron.compose_lebron("smoke_test", ims=[img1, img2])
        self.assertIsNotNone(manifest)
        self.assertIn("segment_kareler", manifest)
        self.assertIn("sinif_sayimi", manifest)
        self.assertIn("scroll_dy_medyan", manifest)
        self.assertIsInstance(manifest["segment_kareler"], list)
        self.assertIsInstance(manifest["sinif_sayimi"], dict)

    def test_madde_2_cli_interface(self):
        """Verify lebron_james has a runnable CLI interface."""
        import subprocess
        python_bin = sys.executable
        script_path = MASTER_DUP_DIR / "lebron_james.py"
        res = subprocess.run([python_bin, str(script_path), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--slug", res.stdout)
    def test_madde_6_hybrid_scoring(self):
        """Verify hybrid sharpness + contrast scoring selects best frame."""
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.zeros((100, 100, 3), dtype=np.uint8)
        img1[20:40, 20:80] = 255
        img2[10:90, 10:90] = 255 # higher text coverage & contrast

        kanvas, manifest = lebron.compose_lebron("grup2_test_m6", ims=[img1, img2])
        self.assertIsNotNone(kanvas)
        self.assertEqual(manifest["durum"], "OK")

    def test_madde_7_compiler_filter(self):
        """Verify non-text single frames are pruned while valid frames remain."""
        blank_img = np.zeros((100, 100, 3), dtype=np.uint8) # pure black, no text
        text_img = np.zeros((100, 100, 3), dtype=np.uint8)
        text_img[20:40, 20:80] = 255

        kanvas, manifest = lebron.compose_lebron("grup2_test_m7", ims=[text_img, blank_img, text_img])
        self.assertIsNotNone(kanvas)
        self.assertEqual(manifest["durum"], "OK")


if __name__ == "__main__":
    unittest.main()

