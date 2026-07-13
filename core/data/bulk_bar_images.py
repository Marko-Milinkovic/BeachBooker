"""Beach bar images from core/static/core/images/bars/."""

import hashlib
from pathlib import Path
from urllib.parse import quote

LOCAL_BARS_DIR = Path(__file__).resolve().parents[1] / "static" / "core" / "images" / "bars"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def static_bar_image_url(filename):
    return f"/static/core/images/bars/{quote(filename)}"


def local_bar_image_urls():
    """Return sorted static URLs, skipping duplicate file content."""
    if not LOCAL_BARS_DIR.is_dir():
        return []
    seen_hashes = set()
    urls = []
    for path in sorted(LOCAL_BARS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        urls.append(static_bar_image_url(path.name))
    return urls


def bulk_image_url(index):
    """Return local static image URL for bulk bar index (0-based)."""
    pool = local_bar_image_urls()
    if not pool:
        raise ValueError(
            "No images found in core/static/core/images/bars/. "
            "Add beach bar photos before running seed_bulk."
        )
    return pool[index % len(pool)]


def unique_urls_for_bars(bar_count, reserved_urls=()):
    """Return `bar_count` unique local static image URLs."""
    reserved = set(reserved_urls)
    pool = [url for url in local_bar_image_urls() if url not in reserved]
    if len(pool) < bar_count:
        raise ValueError(
            f"Need {bar_count} unique images but only {len(pool)} in "
            "core/static/core/images/bars/. Add more photos or reduce --bars."
        )
    return pool[:bar_count]
