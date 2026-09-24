# 02 — Frontend (`templates/`, `static/`)

> Prepend `00-context.md`, then paste this. Also paste the final `app.py` from step 01
> so the template variable names match exactly.

---

## Task

Write the UI for the five converters as **one shared layout + one registry + one generic page + one CSS + one JS**.
The five per-converter templates become two-line stubs.

## Inputs

- The converter registry and API contract from the context.
- `app.py`: a context processor injects `conversions` (the registry, keyed by slug) and `max_file_size` into every
  template. Validation rules come ONLY from these; templates never restate extensions, output formats or limits.

## Outputs

1. `templates/base.html` — `<!DOCTYPE html>`, `lang="en"`, `<meta charset>` + viewport, `<title>{% block title %}`,
   links `static/style.css` via `url_for`, a header/nav built from `TOOLS`, `{% block content %}` and `{% block scripts %}`.
2. `templates/_tools.html` — `{% set TOOLS = {...} %}` keyed by slug holding display text only (name, input/output
   label, `accept` mimetypes, one-line description). Imported with `{% from "_tools.html" import TOOLS %}`.
   Links use `url_for(slug)`; the API endpoint is `url_for("api_" ~ slug)`.
3. `templates/index.html` — extends base; renders links/cards to all converters by looping over `TOOLS`
   (no hard-coded list).
4. `templates/<slug>.html` (x5) — exactly `{% extends "converter.html" %}` + `{% set active_tool = "<slug>" %}`.
5. `templates/converter.html` — extends base; looks up `TOOLS[active_tool]` (text) and `conversions[active_tool]`
   (rules); one form with:
   - a file `<input>` whose `accept` attribute lists the accepted extensions,
   - the button label from the registry,
   - an inline status/error region with `role="alert"` / `aria-live="polite"`,
   - `data-*` attributes on the form carrying: API endpoint, accepted extensions, max bytes, output extension.
   - loads `static/converter.js` (with `defer`). No inline script logic.
6. `static/style.css` — the single stylesheet. Every selector used somewhere; no unused classes.
7. `static/converter.js` — generic, reads its configuration from the `data-*` attributes only.

## Behavior of `converter.js`

On submit:
1. Prevent default submission; clear the previous message.
2. Client pre-checks (UX only; server is authoritative), each showing an inline message:
   - no file selected → "Please select an image."
   - extension (lower-cased) not accepted → "Please select a <.ext list> file."
   - size > max bytes → "File must be 5 MB or smaller."
3. Disable the button and show "Converting…" while the request is in flight.
4. `fetch(endpoint, {method: "POST", body: FormData})` with field name `image`.
5. If `!response.ok`: try `await response.json()` and show its `error`; if the body is not JSON show
   "Conversion failed (HTTP <status>)". **Never** treat an error response as the file to download.
6. If ok: take the filename from the `Content-Disposition` header (handle `filename=` and `filename*=UTF-8''`);
   fall back to `converted.<output ext>`. Download via `URL.createObjectURL` + temporary `<a download>`,
   then `URL.revokeObjectURL`. Show a success message naming the file.
7. Network failure → inline "Network error, please try again."
8. Always re-enable the button.

## Constraints

- No `alert()`, `confirm()`, `console.log` left in, or inline event handlers (`onclick=`).
- No external resources (fonts, CDNs).
- Works in current evergreen browsers; plain ES2017+ (async/await OK), no modules/bundler required.
- All five pages look identical apart from title, accept list and button label.

## Acceptance criteria

- [ ] `grep -r "alert(" templates static` finds nothing.
- [ ] `grep -r "<style" templates` and inline `<script>` logic find nothing.
- [ ] Every `GET` page route returns 200 HTML (checked by `tests/test_pages.py`).
- [ ] Uploading `PHOTO.JPG` passes the client pre-check (case-insensitive).
- [ ] A server 400/413 shows the server's `error` text inline and downloads nothing.
- [ ] Downloaded file name matches the server's `Content-Disposition`.
