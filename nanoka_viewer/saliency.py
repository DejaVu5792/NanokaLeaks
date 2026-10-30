"""Spectral-residual saliency centroid for details artwork.

The details view shows the top of a full-height strip of the splash art.  The
owner-approved centering method uses the spectral residual from Hou & Zhang
(2007) to find the saliency map, then takes its saliency-weighted centroid as
the horizontal focus.

This module is deliberately dependency-light: Pillow for decode/resize and
NumPy for the FFT.  It works on a small (320 px) copy, so the cost stays in the
low milliseconds even for a 2048 px source.
"""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image, ImageFilter

# Matches the research probe so the app and the experiments stay comparable.
WORKING_SIDE = 320
BLUR_SIGMA = 3.0
BACKGROUND = (32, 32, 36)


def _as_rgba(source: Image.Image | bytes | bytearray) -> Image.Image:
    if isinstance(source, (bytes, bytearray)):
        with Image.open(io.BytesIO(bytes(source))) as image:
            return image.convert("RGBA")
    return source.convert("RGBA")


def _box_mean(values: np.ndarray, size: int) -> np.ndarray:
    """Edge-padded square box mean, used for the 3x3 log-amplitude average."""
    pad = size // 2
    source = np.pad(values, pad, mode="edge")
    height, width = values.shape
    total = np.zeros_like(values, dtype=np.float32)
    for y in range(size):
        for x in range(size):
            total += source[y : y + height, x : x + width]
    return total / (size * size)


def _gaussian_blur(values: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur without pulling in SciPy."""
    radius = max(1, int(math.ceil(3.0 * sigma)))
    offsets = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(offsets * offsets) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    height, width = values.shape

    output = values.astype(np.float32, copy=False)
    padded = np.pad(output, ((radius, radius), (0, 0)), mode="edge")
    output = sum(kernel[i] * padded[i : i + height, :] for i in range(len(kernel)))

    padded = np.pad(output, ((0, 0), (radius, radius)), mode="edge")
    output = sum(kernel[i] * padded[:, i : i + width] for i in range(len(kernel)))
    return output


def _interior_mask(alpha: Image.Image) -> np.ndarray:
    """Fade out the cut-out silhouette so its outline cannot win the centroid."""
    radius = max(1, int(round(min(alpha.size) * 0.008)))
    mask = alpha.point(lambda value: 255 if value > 24 else 0)
    mask = mask.filter(ImageFilter.MinFilter(radius * 2 + 1))
    mask = mask.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(mask, dtype=np.float32) / 255.0


def sr_centroid_x(source: Image.Image | bytes | bytearray) -> float:
    """Return the spectral-residual centroid as a normalized x in ``[0, 1]``.

    Falls back to ``0.5`` for empty, uniform, or fully transparent images.
    """
    rgba = _as_rgba(source)
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return 0.5

    scale = min(1.0, WORKING_SIDE / max(width, height))
    size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    small = rgba.resize(size, Image.Resampling.BOX)

    background = Image.new("RGBA", size, (*BACKGROUND, 255))
    gray = np.asarray(
        Image.alpha_composite(background, small).convert("L"), dtype=np.float32
    )
    mask = _interior_mask(small.getchannel("A"))

    spectrum = np.fft.fft2(gray)
    log_amplitude = np.log(np.abs(spectrum) + 1e-8)
    phase = np.angle(spectrum)
    residual = np.exp(log_amplitude - _box_mean(log_amplitude, 3))
    saliency = np.abs(np.fft.ifft2(residual * np.exp(1j * phase))) ** 2
    saliency = _gaussian_blur(saliency, BLUR_SIGMA) * mask

    total = float(saliency.sum())
    if not math.isfinite(total) or total <= 0.0:
        return 0.5

    height, width = saliency.shape
    x_coordinates = np.arange(width, dtype=np.float64)
    centroid = float((saliency.sum(axis=0) * x_coordinates).sum() / total)
    return min(1.0, max(0.0, centroid / max(1, width - 1)))
