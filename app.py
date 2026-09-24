"""Small Flask app that converts images between common formats, fully in memory."""

import io
import os
import warnings
from typing import Dict, NamedTuple, Tuple

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB per upload
MAX_PIXELS = 40_000_000  # width * height

app = Flask(__name__)
# Hard cap on the whole request body; slightly above MAX_FILE_SIZE to leave room for multipart overhead.
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

# Pillow raises DecompressionBombError above 2 * MAX_IMAGE_PIXELS and only warns in between;
# our explicit pixel check rejects the in-between range, so the warning is just noise.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("ignore", Image.DecompressionBombWarning)


class Conversion(NamedTuple):
    extensions: Tuple[str, ...]  # accepted upload extensions (lowercase)
    source_formats: Tuple[str, ...]  # accepted Pillow `img.format` values
    output_format: str  # Pillow format name used when saving
    mimetype: str
    output_ext: str


CONVERSIONS: Dict[str, Conversion] = {
    # Pillow reports multi-picture JPEGs (common from phone cameras) as MPO.
    "jpgtopng": Conversion((".jpg", ".jpeg"), ("JPEG", "MPO"), "PNG", "image/png", ".png"),
    "pngtojpg": Conversion((".png",), ("PNG",), "JPEG", "image/jpeg", ".jpg"),
    "webptopng": Conversion((".webp",), ("WEBP",), "PNG", "image/png", ".png"),
    "bmptopng": Conversion((".bmp",), ("BMP",), "PNG", "image/png", ".png"),
    "pngtopdf": Conversion((".png",), ("PNG",), "PDF", "application/pdf", ".pdf"),
}

PNG_MODES = {"1", "L", "LA", "I", "I;16", "P", "RGB", "RGBA"}


class ConversionError(Exception):
    """A client-facing error that is turned into a JSON response."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ConversionError)
def handle_conversion_error(error: ConversionError):
    return jsonify(error=error.message), error.status


@app.errorhandler(413)
def handle_too_large(_error):
    return jsonify(error="File is too large (max 5 MB)"), 413


@app.errorhandler(500)
def handle_internal_error(_error):
    return jsonify(error="Conversion failed"), 500


@app.context_processor
def inject_conversion_rules():
    # Templates read validation rules from here so they never drift from the API.
    return {"conversions": CONVERSIONS, "max_file_size": MAX_FILE_SIZE}


def load_upload(conversion: Conversion) -> Tuple[Image.Image, str]:
    """Validate the uploaded file and return the opened image and its original filename."""
    upload = request.files.get("image")
    if upload is None:
        raise ConversionError("No file uploaded (expected form field 'image')")
    if not upload.filename:
        raise ConversionError("No file selected")

    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in conversion.extensions:
        raise ConversionError(f"Unsupported file type; expected {', '.join(conversion.extensions)}")

    data = read_limited(upload)
    too_many_pixels = ConversionError(f"Image is too large (max {MAX_PIXELS:,} pixels)")
    try:
        img = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError:
        raise too_many_pixels from None
    except OSError:
        raise ConversionError("File is not a readable image") from None

    if img.width * img.height > MAX_PIXELS:
        raise too_many_pixels
    if img.format not in conversion.source_formats:
        raise ConversionError(f"File content is {img.format}, not {conversion.source_formats[0]}")

    try:
        img.load()  # decode now so truncated files are reported as bad input
    except OSError:
        raise ConversionError("File is not a readable image") from None
    return img, upload.filename


def read_limited(upload: FileStorage) -> bytes:
    data = upload.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise ConversionError("File is too large (max 5 MB)", 413)
    return data


def flatten_on_white(img: Image.Image) -> Image.Image:
    """Return an RGB copy, compositing any transparency onto a white background."""
    if not img.has_transparency_data:
        return img.convert("RGB")
    rgba = img.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def convert_image(img: Image.Image, output_format: str) -> io.BytesIO:
    if output_format in ("JPEG", "PDF"):
        img = flatten_on_white(img)
    elif img.mode not in PNG_MODES:  # e.g. CMYK or YCbCr
        img = img.convert("RGBA" if img.has_transparency_data else "RGB")

    buffer = io.BytesIO()
    img.save(buffer, format=output_format)
    buffer.seek(0)
    return buffer


def download_name(filename: str, ext: str) -> str:
    stem = secure_filename(os.path.splitext(filename)[0]) or "converted"
    return stem + ext


def make_converter(conversion: Conversion):
    def convert():
        img, filename = load_upload(conversion)
        try:
            output = convert_image(img, conversion.output_format)
        except Exception:
            app.logger.exception("Conversion failed")
            raise ConversionError("Conversion failed", 500) from None
        return send_file(
            output,
            mimetype=conversion.mimetype,
            as_attachment=True,
            download_name=download_name(filename, conversion.output_ext),
        )

    return convert


def make_page(template: str):
    return lambda: render_template(template)


app.add_url_rule("/", "index", make_page("index.html"))
for name, conversion in CONVERSIONS.items():
    app.add_url_rule(f"/{name}", name, make_page(f"{name}.html"))
    app.add_url_rule(f"/api/{name}", f"api_{name}", make_converter(conversion), methods=["POST"])


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
