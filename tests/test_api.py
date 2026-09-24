"""Executable specification of the conversion API (see CONTRACT: API section).

Every endpoint accepts a multipart upload in the ``image`` field and either
returns the converted file (200) or a JSON body ``{"error": "..."}``.
"""
import io
from collections import namedtuple

import pytest
from PIL import Image
from werkzeug.http import parse_options_header

from app import app as flask_app
from tests.conftest import MAX_UPLOAD_BYTES, MB, make_image_bytes

Conversion = namedtuple(
    "Conversion", "endpoint source_format source_ext mimetype target_ext target_format"
)

CONVERSIONS = [
    Conversion("/api/jpgtopng", "JPEG", ".jpg", "image/png", ".png", "PNG"),
    Conversion("/api/pngtojpg", "PNG", ".png", "image/jpeg", ".jpg", "JPEG"),
    Conversion("/api/webptopng", "WEBP", ".webp", "image/png", ".png", "PNG"),
    Conversion("/api/bmptopng", "BMP", ".bmp", "image/png", ".png", "PNG"),
    Conversion("/api/pngtopdf", "PNG", ".png", "application/pdf", ".pdf", None),
]
ENDPOINTS = [c.endpoint for c in CONVERSIONS]


def by_endpoint(conversion):
    return conversion.endpoint.rsplit("/", 1)[-1]


def download_filename(response):
    _, options = parse_options_header(response.headers.get("Content-Disposition", ""))
    return options.get("filename")


def assert_json_error(response, status):
    assert response.status_code == status
    assert response.is_json, response.data[:200]
    message = response.get_json().get("error")
    assert isinstance(message, str) and message.strip()


def open_image(data):
    return Image.open(io.BytesIO(data))


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("conv", CONVERSIONS, ids=by_endpoint)
def test_conversion_succeeds(upload, conv):
    source = make_image_bytes(conv.source_format)

    response = upload(conv.endpoint, source, "photo" + conv.source_ext)

    assert response.status_code == 200
    assert response.mimetype == conv.mimetype
    disposition, _ = parse_options_header(response.headers["Content-Disposition"])
    assert disposition == "attachment"
    assert download_filename(response) == "photo" + conv.target_ext
    if conv.target_format is None:
        assert response.data.startswith(b"%PDF")
    else:
        assert open_image(response.data).format == conv.target_format


@pytest.mark.parametrize("filename", ["PHOTO.JPG", "photo.jpeg", "photo.JPEG"])
def test_jpeg_extension_variants_are_accepted(upload, filename):
    response = upload("/api/jpgtopng", make_image_bytes("JPEG"), filename)

    assert response.status_code == 200
    assert download_filename(response) == filename.rsplit(".", 1)[0] + ".png"


@pytest.mark.parametrize(
    "uploaded_name, expected_name",
    [
        ("My Photo.JPG", "My_Photo.png"),
        ("../../etc/passwd.jpg", "etc_passwd.png"),
        ("日本.jpg", "converted.png"),  # secure_filename strips non-ASCII -> empty stem
    ],
)
def test_download_filename_is_sanitized(upload, uploaded_name, expected_name):
    response = upload("/api/jpgtopng", make_image_bytes("JPEG"), uploaded_name)

    assert response.status_code == 200
    assert download_filename(response) == expected_name


# --------------------------------------------------------------------------- #
# Request validation errors (400)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_missing_image_field_is_rejected(client, endpoint):
    response = client.post(endpoint, data={}, content_type="multipart/form-data")

    assert_json_error(response, 400)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_empty_filename_is_rejected(upload, endpoint):
    response = upload(endpoint, b"", "")

    assert_json_error(response, 400)


@pytest.mark.parametrize(
    "endpoint, filename",
    [
        ("/api/jpgtopng", "photo.png"),
        ("/api/pngtojpg", "photo.jpg"),
        ("/api/webptopng", "photo.png"),
        ("/api/bmptopng", "photo.gif"),
        ("/api/pngtopdf", "photo"),
    ],
)
def test_wrong_extension_is_rejected(upload, endpoint, filename):
    response = upload(endpoint, make_image_bytes("PNG"), filename)

    assert_json_error(response, 400)


@pytest.mark.parametrize("conv", CONVERSIONS, ids=by_endpoint)
def test_unreadable_content_is_rejected(upload, conv):
    response = upload(conv.endpoint, b"this is not an image", "photo" + conv.source_ext)

    assert_json_error(response, 400)


@pytest.mark.parametrize(
    "endpoint, real_format, filename",
    [
        ("/api/jpgtopng", "PNG", "renamed.jpg"),
        ("/api/pngtojpg", "JPEG", "renamed.png"),
        ("/api/webptopng", "PNG", "renamed.webp"),
        ("/api/bmptopng", "PNG", "renamed.bmp"),
        ("/api/pngtopdf", "WEBP", "renamed.png"),
    ],
)
def test_real_format_must_match_extension(upload, endpoint, real_format, filename):
    response = upload(endpoint, make_image_bytes(real_format), filename)

    assert_json_error(response, 400)


@pytest.mark.slow
@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_image_with_too_many_pixels_is_rejected(upload):
    # 8000 x 6000 = 48,000,000 px > 40,000,000. A 1-bit blank PNG compresses
    # to a few KB, so the upload itself stays far below the size limit.
    huge = make_image_bytes("PNG", mode="1", size=(8000, 6000))
    assert len(huge) < MB

    response = upload("/api/pngtojpg", huge, "huge.png")

    assert_json_error(response, 400)


# --------------------------------------------------------------------------- #
# Size limits (413)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("conv", CONVERSIONS, ids=by_endpoint)
def test_file_over_5mb_is_rejected(upload, conv):
    # A valid image padded with trailing bytes: readable by Pillow, but too big,
    # so only the size check can reject it.
    small = make_image_bytes(conv.source_format)
    oversized = small + b"\0" * (MAX_UPLOAD_BYTES + 1 - len(small))

    response = upload(conv.endpoint, oversized, "big" + conv.source_ext)

    assert_json_error(response, 413)


def test_max_content_length_is_configured():
    assert flask_app.config["MAX_CONTENT_LENGTH"] == 6 * MB


def test_request_over_max_content_length_is_rejected(upload):
    response = upload("/api/pngtojpg", b"\0" * (6 * MB + 1), "huge.png")

    assert_json_error(response, 413)


# --------------------------------------------------------------------------- #
# Transparency handling
# --------------------------------------------------------------------------- #


TRANSPARENT_SAMPLE_POINT = (3, 8)  # well inside the transparent half


def transparent_png():
    """16x16 RGBA PNG: left half fully transparent black, right half opaque red.

    The transparent area is large enough that JPEG chroma subsampling cannot
    bleed the red half into the sampled pixel.
    """
    img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    img.paste((0, 0, 0, 0), (0, 0, 8, 16))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_to_jpg_flattens_transparency_onto_white(upload):
    response = upload("/api/pngtojpg", transparent_png(), "alpha.png")

    assert response.status_code == 200
    result = open_image(response.data)
    assert result.mode == "RGB"
    assert all(channel >= 240 for channel in result.getpixel(TRANSPARENT_SAMPLE_POINT))


def test_png_to_pdf_accepts_transparency(upload):
    response = upload("/api/pngtopdf", transparent_png(), "alpha.png")

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


def test_webp_to_png_keeps_alpha(upload):
    # (BMP is not used here: Pillow reads 32-bit BMPs back as RGB.)
    source = make_image_bytes("WEBP", mode="RGBA", color=(10, 20, 30, 128))
    assert open_image(source).mode == "RGBA"  # sanity: the source really has alpha

    response = upload("/api/webptopng", source, "alpha.webp")

    assert response.status_code == 200
    assert open_image(response.data).mode == "RGBA"


def test_unexpected_conversion_failure_returns_json_500(upload, monkeypatch):
    jpeg = make_image_bytes("JPEG")  # build the input before breaking the encoder

    def broken_save(*args, **kwargs):
        raise RuntimeError("encoder crashed")

    monkeypatch.setattr(Image.Image, "save", broken_save)
    response = upload("/api/jpgtopng", jpeg, "photo.jpg")

    assert_json_error(response, 500)
    assert response.get_json() == {"error": "Conversion failed"}
