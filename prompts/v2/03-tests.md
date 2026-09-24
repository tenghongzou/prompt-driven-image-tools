# 03 — Tests (`tests/`)

> Prepend `00-context.md`, then paste this. Also paste the final `app.py`.

---

## Task

Write a pytest suite that proves the API contract and guards every rule in the context. The tests are the
executable form of the spec: a behavior not tested is a behavior not guaranteed.

## Inputs

- The context (registry, limits, API contract, conversion rules).
- `app.py` exposing a module-level `app`.

## Outputs

1. `tests/conftest.py` — fixtures:
   - `client`: Flask test client with `TESTING=True`.
   - a helper that builds images **in memory** with Pillow (`Image.new(mode, size, color)` → `BytesIO`) for any format/mode.
   - an `upload(endpoint, data, filename)` helper posting multipart with field `image`.
2. `tests/test_pages.py` — `test_page_renders_html` (every `GET` route returns 200 `text/html`) and
   `test_converter_page_uses_api_rules` (each converter page's `data-*` endpoint, extensions and max bytes match
   the backend registry, so the client pre-checks cannot drift from the server).
3. `tests/test_api.py` — the API tests below.
4. `pytest.ini` — `testpaths = tests`, `pythonpath = .`.

## Required tests (use these names; parametrize over the registry where it applies)

Put one `assert_json_error(response, status)` helper in `tests/test_api.py` that checks: status code,
`Content-Type: application/json`, body is `{"error": <non-empty str>}` with no other keys, no `Traceback` text.
Every error test goes through it.

**Happy path**
- `test_conversion_succeeds` — each endpoint, valid image → 200, correct mimetype, output re-opens with Pillow
  as the expected format (PDF: body starts with `%PDF`).
- `test_jpeg_extension_variants_are_accepted` — `PHOTO.JPG`, `photo.jpeg`, `photo.JPEG`.
- `test_download_filename_is_sanitized` — `My Photo.JPG` → `My_Photo.png`; a name whose secured stem is empty
  (e.g. `../.jpg`) → `converted.png`.

**Validation (400)**
- `test_missing_image_field_is_rejected`, `test_empty_filename_is_rejected` — every endpoint.
- `test_wrong_extension_is_rejected` — e.g. `.gif` to `/api/pngtojpg`, `.png` to `/api/jpgtopng`.
- `test_unreadable_content_is_rejected` — random bytes with a valid extension, every endpoint.
- `test_real_format_must_match_extension` — a real PNG renamed `.jpg`, a JPEG renamed `.png`, etc.
- `test_image_with_too_many_pixels_is_rejected` — just over 40,000,000 pixels (use mode `1` or `L` and PNG so
  the file stays tiny).

**Size limits (413)**
- `test_file_over_5mb_is_rejected` — a valid image padded past 5 MB (so only the size check can reject it);
  parametrize over all five endpoints (v1 only checked one).
- `test_request_over_max_content_length_is_rejected` — body > `MAX_CONTENT_LENGTH` → 413 JSON, not Werkzeug HTML.

**Transparency**
- `test_png_to_jpg_flattens_transparency_onto_white` — half-transparent RGBA PNG → JPEG; a pixel well inside the
  transparent area has every channel ≥ 240 (JPEG tolerance), mode is `RGB`.
- `test_png_to_pdf_accepts_transparency` — RGBA PNG → 200, `%PDF`.
- `test_webp_to_png_keeps_alpha` — RGBA WEBP → `/api/webptopng` → mode `RGBA`.

**Robustness / security defaults**
- `test_unexpected_conversion_failure_returns_json_500` — monkeypatch the conversion helper to raise →
  500 `{"error": "Conversion failed"}`.
- `tests/test_startup.py::test_debug_off_by_default` — stub `Flask.run`, execute `app.py` as `__main__` with
  `runpy.run_path`, and assert it was called with `debug=False` when `FLASK_DEBUG` is unset (and `True` when it is "1").
- `tests/test_pages.py::test_converter_page_uses_api_rules` — each tool page's `data-*` attributes equal the
  backend registry (endpoint, extensions, output ext, max bytes).
- `test_max_content_length_is_configured` — `app.config["MAX_CONTENT_LENGTH"] == 6 * 1024 * 1024`.

## Constraints

- No files on disk, no network, no fixtures directory — generate every image in the test.
- Whole suite runs in a few seconds on a laptop.
- Python 3.9 syntax.

## Acceptance criteria

- [ ] `pytest` passes against the v2 `app.py`.
- [ ] `tests/test_api.py` only talks to the app over HTTP (test client), so it can also run against v1.
- [ ] Against the v1 `app.py` (`git show 076968a:app.py`), the uppercase-extension, 5 MB, corrupt-file,
      format-mismatch, transparency and JSON-error tests **fail** — i.e. each v1 defect is caught by at least one test.
