# 04 — Documentation (`README.md`)

> Prepend `00-context.md`, then paste this. Also paste the final file tree and `app.py`.

---

## Task

Write the top-level `README.md` in **Traditional Chinese (繁體中文)**, keeping technical terms
(Flask, Pillow, endpoint, multipart/form-data, etc.) in English. Use full-width Chinese punctuation
(，。：；「」) in Chinese sentences.

## Inputs

- The context, the final file tree, `app.py`.
- The fact that `app.txt` holds the original v1 prompts and commit `076968a` holds the v1 generated code.

## Output

`README.md` with exactly these sections, in order:

1. **Title + one-paragraph intro** — what the app does; that it is a demo of AI-generated code, comparing
   v1 prompts (`app.txt`) with v2 prompts (`prompts/v2/`).
2. **功能** — table of the 5 converters: page route, API endpoint, input, output.
3. **快速開始** — `python3 -m venv .venv`, activate, `pip install -r requirements-dev.txt`, `python app.py`,
   open `http://127.0.0.1:5000`, `pytest`.
4. **API** — request format (field `image`), success response (`Content-Disposition` naming rule), error JSON shape,
   status-code table (400 / 413 / 500), a `curl -F image=@photo.jpg -OJ` example and an error example.
5. **專案結構** — annotated tree.
6. **Demo 導覽** — step-by-step walkthrough: show v1 prompts and v1 code, reproduce a v1 bug, then show v2
   prompts, v2 code and the test that guards the bug. Link to `prompts/README.md` for the full defect table.
7. **安全性說明** — debug off by default via `FLASK_DEBUG`, size/pixel limits, content-based validation,
   no disk writes; note it is a demo, not hardened for public production (no rate limiting, use a WSGI server).

## Constraints

- Concise and scannable: tables and code blocks over prose. No marketing language, no emojis, no screenshots.
- Every command must actually work on macOS/Linux with Python 3.9+.
- Every number (5 MB, 6 MB cap, 40,000,000 pixels) must match the context exactly.

## Acceptance criteria

- [ ] A newcomer can go from clone to passing tests using only the README.
- [ ] The curl example downloads a correctly named file.
- [ ] The Demo section can be followed in under 5 minutes.
