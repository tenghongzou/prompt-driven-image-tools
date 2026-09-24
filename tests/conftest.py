"""Shared fixtures for the image-tools-py test suite.

Everything happens in memory: images are generated with Pillow and sent
through Flask's test client, so no files touch the disk.
"""
import io

import pytest
from PIL import Image

from app import app as flask_app

MB = 1024 * 1024
MAX_UPLOAD_BYTES = 5 * MB


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as client:
        yield client


def make_image_bytes(fmt, mode="RGB", size=(8, 8), color=(200, 100, 50)):
    """Return an encoded image (e.g. fmt="PNG") as raw bytes."""
    if mode in ("1", "L", "P"):
        color = 0
    elif mode == "RGBA" and len(color) == 3:
        color = color + (255,)
    img = Image.new(mode, size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def image_bytes():
    """Fixture form of :func:`make_image_bytes` for use inside tests."""
    return make_image_bytes


@pytest.fixture
def upload(client):
    """POST ``data`` as the ``image`` field of a multipart form to ``endpoint``."""

    def _upload(endpoint, data, filename):
        return client.post(
            endpoint,
            data={"image": (io.BytesIO(data), filename)},
            content_type="multipart/form-data",
        )

    return _upload
