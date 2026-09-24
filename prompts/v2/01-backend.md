# 01 — Backend (`app.py`, `requirements*.txt`)

> Prepend `00-context.md`, then paste this.

---

## Task

Write `app.py`, `requirements.txt` and `requirements-dev.txt` for the project described above.

## Inputs

- The converter registry, limits, API contract, conversion rules and security defaults from the context.

## Outputs

1. `app.py` — a single Flask module exposing a module-level `app` object (tests do `from app import app`).
2. `requirements.txt` — `flask>=3.0`, `pillow>=10.1` (one per line; 10.1 adds `Image.has_transparency_data`).
3. `requirements-dev.txt` — `-r requirements.txt` and `pytest>=7`.

## Required structure of `app.py`

1. **A registry** — one data structure (e.g. a dict of small dataclasses/namedtuples) holding, per slug:
   accepted extensions, accepted Pillow formats (a tuple: `("JPEG", "MPO")` for jpgtopng), output Pillow format, output mimetype,
   output extension. (UI-only fields such as labels live in the frontend registry.) Every route below is generated from it; there are no five hand-written
   route functions.
2. **Page routes** — `GET /` renders `index.html`; `GET /<slug>` for each slug renders `<slug>.html`
   (a thin template that extends `converter.html`, see `02-frontend.md`). Register them in the same loop
   over the registry as the API routes.
3. **API routes** — `POST /api/<slug>` for each slug, all handled by ONE function that runs these steps in order,
   returning the first error encountered:
   1. `image` field present and filename non-empty → else 400.
   2. Extension (lower-cased, via `os.path.splitext`) in the accepted set → else 400.
   3. Read at most `5 * 1024 * 1024 + 1` bytes; if more than 5 MB → 413.
   4. `Image.open(io.BytesIO(data))` (lazy: reads only the header). `OSError` → 400 "not a readable image";
      `Image.DecompressionBombError` → 400 "too many pixels".
   5. `img.width * img.height <= 40_000_000` → else 400. (Check before decoding, so a bomb is never decoded.)
   6. `img.format` in the accepted formats → else 400 (message names the real and expected format).
   7. `img.load()` so truncated/corrupt data fails here → 400 "not a readable image".
   8. Convert per the conversion rules (white-background flattening for JPEG/PDF; mode-preserving for PNG).
      Wrap ONLY this step in `try/except Exception` → 500 `{"error": "Conversion failed"}`; log the exception
      with `app.logger.exception`, never return it.
   9. Return the bytes with the output mimetype and `Content-Disposition` built per the contract
      (use `send_file(..., as_attachment=True, download_name=...)` or equivalent).
4. **Error handlers** — register a 413 handler (`RequestEntityTooLarge`) returning the JSON error shape,
   so an over-cap upload rejected by Werkzeug still gets JSON, not HTML. Any other error on `/api/*`
   must also be JSON (register a 500 handler as a safety net).
5. **Template context** — a context processor injects `conversions` (the registry) and `max_file_size`, so the
   frontend renders its client-side checks from the same data the API enforces.
6. **Entry point** — under `if __name__ == "__main__":` read `FLASK_DEBUG` (`"1"` → True, anything else False)
   and run on `127.0.0.1:5000`.

Keep helpers small and pure where possible (e.g. `flatten_on_white(img)`, `convert_image(img, fmt)`,
`download_name(filename, ext)`) so they are easy to unit-test. Raise one custom exception type
(e.g. `ConversionError(message, status)`) from validation code and turn it into the JSON response in a single
`@app.errorhandler`, instead of returning ad-hoc tuples from deep helpers.

## Constraints

- Python 3.9 syntax only.
- No disk I/O, no temp files.
- Never trust `file.mimetype` or the extension for format decisions; they are only a first cheap filter.
- No `debug=True` literal anywhere.
- No global state mutated per request.

## Acceptance criteria (the test suite in `03-tests.md` checks all of these)

- [ ] `photo.JPG`, `photo.JPEG`, `photo.jpeg` all accepted by `/api/jpgtopng`.
- [ ] Every endpoint rejects > 5 MB with 413 + JSON; oversized body beyond `MAX_CONTENT_LENGTH` also 413 + JSON.
- [ ] Random bytes named `x.png` → 400 JSON, not 500 HTML.
- [ ] A real PNG renamed `x.jpg` sent to `/api/jpgtopng` → 400.
- [ ] Fully transparent RGBA PNG → `/api/pngtojpg` output pixels are white, not black; `/api/pngtopdf` succeeds.
- [ ] RGBA PNG through a PNG-output converter keeps its alpha channel.
- [ ] Image with > 40,000,000 pixels → 400.
- [ ] `My Photo.JPG` → download name `My_Photo.png`; `../../.jpg`-style names fall back to `converted.<ext>`.
- [ ] Missing field / empty filename → 400 JSON.
- [ ] Every error response has `Content-Type: application/json` and exactly one key, `error`.
- [ ] Running `python app.py` without `FLASK_DEBUG` starts with debug off.
