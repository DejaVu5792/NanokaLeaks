"""Pillow-only detail centroid for details artwork.

The details view shows the top of a full-height strip of the splash art, and
the horizontal focus comes from a saliency map of the artwork.  The first
implementation used the spectral residual from Hou & Zhang (2007), which needs
an FFT: NumPy plus its bundled OpenBLAS build cost about 42 MB of the
distribution for this one call.

This module keeps the rest of that pipeline unchanged -- a 320 px working copy,
a neutral background composite and an eroded alpha mask -- and swaps the FFT
for a difference-of-Gaussians high-pass, then takes the centroid of the column
means.  Every step is a Pillow C operation, so NumPy is no longer imported.
Measured against the spectral residual over the 30-character probe set, the two
centroids stay within 0.015 normalized x of each other, at most 23 pixels on the
native artwork.

The cost stays in the low milliseconds even for a 2048 px source.
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageChops, ImageFilter

# Matches the research probe so the app and the experiments stay comparable.
WORKING_SIDE = 320
BLUR_SIGMA = 3.0
DETAIL_RADIUS = 2.0
BACKGROUND = (32, 32, 36)


def _as_rgba(source: Image.Image | bytes | bytearray) -> Image.Image:
    if isinstance(source, (bytes, bytearray)):
        with Image.open(io.BytesIO(bytes(source))) as image:
            return image.convert("RGBA")
    return source.convert("RGBA")


def _interior_mask(alpha: Image.Image) -> Image.Image:
    """Fade out the cut-out silhouette so its outline cannot win the centroid."""
    radius = max(1, int(round(min(alpha.size) * 0.008)))
    mask = alpha.point(lambda value: 255 if value > 24 else 0)
    mask = mask.filter(ImageFilter.MinFilter(radius * 2 + 1))
    return mask.filter(ImageFilter.GaussianBlur(radius))


def _column_centroid(image: Image.Image) -> float:
    """Horizontal centroid of an ``L`` image from its column means."""
    width, height = image.size
    columns = image.resize((width, 1), Image.Resampling.BOX)
    try:
        values = columns.get_flattened_data()
    except AttributeError:  # Pillow < 12
        values = columns.getdata()
    total = float(sum(values))
    if not math.isfinite(total) or total <= 0.0:
        return 0.5
    centroid = sum(index * value for index, value in enumerate(values)) / total
    return min(1.0, max(0.0, centroid / max(1, width - 1)))


def detail_centroid_x(source: Image.Image | bytes | bytearray) -> float:
    """Return the detail-weighted centroid as a normalized x in ``[0, 1]``.

    Falls back to ``0.5`` for empty, uniform, or fully transparent images.
    """
    rgba = _as_rgba(source)
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return 0.5

    scale = min(1.0, WORKING_SIDE / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    small = rgba.resize(size, Image.Resampling.BOX)

    background = Image.new("RGBA", size, (*BACKGROUND, 255))
    gray = Image.alpha_composite(background, small).convert("L")
    mask = _interior_mask(small.getchannel("A"))

    # Difference of Gaussians: the spatial band-pass that stands in for the
    # spectral residual.  It keeps edges/detail and discards the flat fill.
    detail = ImageChops.difference(
        gray, gray.filter(ImageFilter.GaussianBlur(DETAIL_RADIUS))
    )
    detail = detail.filter(ImageFilter.GaussianBlur(BLUR_SIGMA))
    detail = ImageChops.multiply(detail, mask)
    return _column_centroid(detail)
