"""Image loading and caching utilities."""

import hashlib
import logging
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from PySide6.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path.home() / ".cache" / "nanoka_leaks" / "images"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Memory cache for loaded images
IMAGE_CACHE = {}


def load_qt_image(url, size=(100, 100)):
    """Load an image from URL and return a QPixmap, with caching."""
    if not url:
        return None

    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url]

    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = IMAGE_CACHE_DIR / f"{url_hash}.png"

    img = None
    if cache_file.exists():
        try:
            img = Image.open(cache_file).convert("RGBA")
        except Exception as e:
            logger.error(f"Failed to load cached image {cache_file}: {e}")

    if img is None:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                try:
                    img.save(cache_file, "PNG")
                except Exception as e:
                    logger.error(f"Failed to save image to cache: {e}")
        except Exception as e:
            logger.error(f"Failed to load image {url}: {e}")
            return None

    if img:
        img = img.resize(size, Image.Resampling.LANCZOS)
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        IMAGE_CACHE[url] = pixmap
        return pixmap
    return None
