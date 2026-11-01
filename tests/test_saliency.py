"""Tests for the detail-weighted artwork focus point."""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from nanoka_viewer.saliency import detail_centroid_x


def _subject(rect_x: int, *, width: int = 240, height: int = 120) -> Image.Image:
    image = Image.new("RGBA", (width, height), (20, 20, 24, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((rect_x, 20, rect_x + 40, 100), fill=(240, 80, 60, 255))
    return image


class DetailCentroidTests(unittest.TestCase):
    def test_centroid_follows_the_subject(self):
        left = detail_centroid_x(_subject(5))
        middle = detail_centroid_x(_subject(100))
        right = detail_centroid_x(_subject(170))

        self.assertLess(left, 0.5)
        self.assertAlmostEqual(middle, 0.5, delta=0.08)
        self.assertGreater(right, 0.5)
        self.assertLess(left, middle)
        self.assertLess(middle, right)

    def test_accepts_encoded_bytes(self):
        image = _subject(170)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        from_image = detail_centroid_x(image)
        from_bytes = detail_centroid_x(buffer.getvalue())

        self.assertAlmostEqual(from_image, from_bytes, places=5)

    def test_fully_transparent_image_falls_back_to_centre(self):
        image = Image.new("RGBA", (240, 120), (0, 0, 0, 0))

        self.assertEqual(detail_centroid_x(image), 0.5)

    def test_uniform_image_falls_back_to_centre(self):
        image = Image.new("RGBA", (240, 120), (50, 50, 50, 255))

        self.assertAlmostEqual(detail_centroid_x(image), 0.5, delta=0.01)

    def test_module_stays_pillow_only(self):
        """NumPy is no longer shipped, so importing the module must not need it."""
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys, nanoka_viewer.saliency;"
            "raise SystemExit(1 if 'numpy' in sys.modules else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=root, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_transparent_decorations_do_not_pull_the_centroid(self):
        image = _subject(40)
        draw = ImageDraw.Draw(image)
        # Bright pixels outside the alpha silhouette must not contribute.
        draw.rectangle((180, 10, 230, 110), fill=(255, 255, 255, 0))

        self.assertLess(detail_centroid_x(image), 0.5)


if __name__ == "__main__":
    unittest.main()
