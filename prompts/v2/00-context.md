# 00 — Project context (prepend to EVERY prompt below)

> Paste this block first, then paste exactly one of `01`–`04` after it.
> Every later prompt assumes these conventions; they are never restated, never overridden.

---

You are working on **image-tools-py**, a tiny web app that converts images between formats.
Read these conventions carefully. They apply to every file you generate. If a later instruction
seems to conflict with them, these conventions win — say so explicitly instead of guessing.

## Stack

- Python **3.9** exactly. Do NOT use `match`, `X | Y` type unions, or any 3.10+ syntax/stdlib.
- Flask 3.x, Pillow 11.x. No other runtime dependencies.
- Tests: pytest (dev only).
- Frontend: plain HTML (Jinja2 templates), one CSS file, one vanilla JS file. No frameworks, no CDN, no build step.

## File layout (final state)

```
app.py                  # the whole backend
templates/base.html     # shared layout: <head>, stylesheet link, header/nav, content block
templates/_tools.html   # display text for the 5 converters; rules are injected from app.py, never copied
templates/index.html    # extends base.html, lists the 5 converters by looping over the registry
templates/converter.html# extends base.html, ONE generic converter page
templates/<slug>.html   # x5, two lines each: extend converter.html + set the slug
static/style.css        # the only stylesheet; no inline <style> anywhere
static/converter.js     # the only script; no inline <script> logic anywhere
tests/                  # pytest suite
requirements.txt        # runtime deps (pinned lower bounds)
requirements-dev.txt    # -r requirements.txt + pytest
README.md
```

## The converter registry (single source of truth)

All behavior derives from this table. Backend, frontend and tests MUST use these exact values.
Never copy-paste per-converter code; drive everything from one data structure.

| slug        | page route   | API endpoint      | accepted extensions (case-insensitive) | required real format (`PIL.Image.format`) | output mimetype   | output ext | button label     |
|-------------|--------------|-------------------|----------------------------------------|-------------------------------------------|-------------------|------------|------------------|
| jpgtopng    | /jpgtopng    | /api/jpgtopng     | .jpg .jpeg                             | JPEG (also MPO, see note)                 | image/png         | .png       | Convert to PNG   |
| pngtojpg    | /pngtojpg    | /api/pngtojpg     | .png                                   | PNG                                       | image/jpeg        | .jpg       | Convert to JPG   |
| webptopng   | /webptopng   | /api/webptopng    | .webp                                  | WEBP                                      | image/png         | .png       | Convert to PNG   |
| bmptopng    | /bmptopng    | /api/bmptopng     | .bmp                                   | BMP                                       | image/png         | .png       | Convert to PNG   |
| pngtopdf    | /pngtopdf    | /api/pngtopdf     | .png                                   | PNG                                       | application/pdf   | .pdf       | Convert to PDF   |

Plus `GET /` → home page listing the five converters.

Note: Pillow reports multi-picture JPEGs (common from phone cameras) as `MPO`; accept it wherever `JPEG` is required.

## Limits (enforced on the SERVER; the client only mirrors them for UX)

| limit | value | server response |
|---|---|---|
| max file size | 5 MB = `5 * 1024 * 1024` bytes | 413 |
| hard request cap | `app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024` | 413 (via error handler) |
| max pixels | `width * height <= 40_000_000` | 400 |

## API contract

- Request: `POST`, `multipart/form-data`, file field name **`image`**.
- Success: `200`, body = converted file bytes, correct mimetype, header
  `Content-Disposition: attachment; filename=<stem>.<ext>` where
  `stem = werkzeug.utils.secure_filename(<uploaded name without extension>)`, or `converted` if that is empty.
  Example: uploading `My Photo.JPG` to `/api/jpgtopng` → `My_Photo.png`.
- Error: **always** JSON, **never** HTML, **never** a stack trace:
  ```json
  {"error": "<short human-readable English sentence>"}
  ```

| status | when |
|---|---|
| 400 | no `image` field; empty filename; extension not accepted; content not a decodable image; real format ≠ required format (e.g. a PNG renamed to `.jpg`); pixels > 40,000,000 |
| 413 | file > 5 MB, or request body > `MAX_CONTENT_LENGTH` |
| 500 | anything unexpected during conversion → exactly `{"error": "Conversion failed"}` |

## Conversion rules

- Validate by **real content**, not by extension or client-sent mimetype: open with Pillow, check `img.format`.
- Output to **JPEG or PDF**: if the image has transparency (`RGBA`, `LA`, or `P` with a `transparency` entry),
  alpha-composite it onto a **white** background; final mode `RGB`. Never let transparent pixels turn black.
- Output to **PNG**: keep the mode if PNG supports it (`RGBA` stays `RGBA`, `L`, `LA`, `P`, `RGB` stay);
  convert others (e.g. `CMYK`) to `RGB`.
- **Never write to disk.** Use `io.BytesIO` for input and output.

## Security defaults

- `debug` comes from env `FLASK_DEBUG` (`"1"` → on). Default **off**. Never hard-code `debug=True`.
- Default bind `127.0.0.1:5000`.
- Set `Image.MAX_IMAGE_PIXELS` consistently with the 40 MP limit, and treat
  `Image.DecompressionBombError` / `DecompressionBombWarning` as a 400, not a 500.
- Uploaded filenames are untrusted: only ever used through `secure_filename`.

## Style

- Small, named functions; no duplicated route bodies. PEP 8, 4-space indent, double quotes.
- Error messages: English, one sentence, no trailing period required but be consistent.
- UI: one consistent look across all pages (driven by `static/style.css`). Errors are shown **inline**
  in the page, never with `alert()`. No unused CSS classes.
- Comments explain *why*, not *what*.

## How to answer

- Output complete files, each preceded by its path as a heading. No placeholders like `# ... rest unchanged`.
- If something is ambiguous, state your assumption in one line before the code.
