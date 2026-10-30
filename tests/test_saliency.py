"""Tests for the spectral-residual artwork focus point."""

from __future__ import annotations

import io
import unittest

from PIL import Image, ImageDraw

from nanoka_viewer.saliency import sr_centroid_x


def _subject(rect_x: int, *, width: int = 240, height: int = 120) -> Image.Image:
    image = Image.new("RGBA", (width, height), (20, 20, 24, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((rect_x, 20, rect_x + 40, 100), fill=(240, 80, 60, 255))
    return image


class SaliencyCentroidTests(unittest.TestCase):
    def test_centroid_follows_the_subject(self):
        left = sr_centroid_x(_subject(5))
        middle = sr_centroid_x(_subject(100))
        right = sr_centroid_x(_subject(170))

        self.assertLess(left, 0.5)
        self.assertAlmostEqual(middle, 0.5, delta=0.08)
        self.assertGreater(right, 0.5)
        self.assertLess(left, middle)
        self.assertLess(middle, right)

    def test_accepts_encoded_bytes(self):
        image = _subject(170)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        from_image = sr_centroid_x(image)
        from_bytes = sr_centroid_x(buffer.getvalue())

        self.assertAlmostEqual(from_image, from_bytes, places=5)

    def test_fully_transparent_image_falls_back_to_centre(self):
        image = Image.new("RGBA", (240, 120), (0, 0, 0, 0))

        self.assertEqual(sr_centroid_x(image), 0.5)

    def test_uniform_image_falls_back_to_centre(self):
        image = Image.new("RGBA", (240, 120), (50, 50, 50, 255))

        self.assertAlmostEqual(sr_centroid_x(image), 0.5, delta=0.01)

    def test_transparent_decorations_do_not_pull_the_centroid(self):
        image = _subject(40)
        draw = ImageDraw.Draw(image)
        # Bright pixels outside the alpha silhouette must not contribute.
        draw.rectangle((180, 10, 230, 110), fill=(255, 255, 255, 0))

        self.assertLess(sr_centroid_x(image), 0.5)


if __name__ == "__main__":
    unittest.main()
