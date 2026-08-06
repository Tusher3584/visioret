"""Saves uploaded scans and their Grad-CAM overlays to local disk.

Media is served back out by FastAPI's StaticFiles mount in main.py. This is
plain filesystem storage -- fine at this scale; an object store (S3-style)
would be overkill for a single-instance app like this.
"""

import os
import uuid

from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(ROOT_DIR, "backend", "media", "scans")


def new_scan_id() -> str:
    return uuid.uuid4().hex


def save_scan_images(scan_id: str, original_image: Image.Image, overlay_image: Image.Image):
    """Saves both images to disk, returns (original_url_path, overlay_url_path)."""
    os.makedirs(MEDIA_DIR, exist_ok=True)

    original_filename = f"{scan_id}_original.jpg"
    overlay_filename = f"{scan_id}_gradcam.jpg"

    original_image.convert("RGB").save(os.path.join(MEDIA_DIR, original_filename), quality=90)
    overlay_image.convert("RGB").save(os.path.join(MEDIA_DIR, overlay_filename), quality=90)

    return f"/media/scans/{original_filename}", f"/media/scans/{overlay_filename}"
