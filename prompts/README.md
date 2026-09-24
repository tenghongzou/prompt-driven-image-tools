# Prompts：v1 → v2 的 prompt engineering 心得

本目錄收錄產生本專案程式碼的 prompts。

| 版本 | 位置 | 產出 |
|---|---|---|
| v1 | `../app.txt`（原封不動保留） | commit `076968a` 的 `app.py` 與 `templates/*.html` |
| v2 | `v2/00-context.md` ～ `v2/04-docs.md` | 目前的 `app.py`、`templates/`、`static/`、`tests/`、`README.md` |

## v2 使用方式

1. 每次對話都先貼上 `v2/00-context.md`（共用規範），再貼上**一個**任務 prompt。
2. 依序執行：`01-backend` → `02-frontend` → `03-tests` → `04-docs`。後面的步驟要一併貼上前一步產出的 `app.py`，讓介面名稱一致。
3. 每個 prompt 結尾的 Acceptance criteria 就是驗收清單；`pytest` 全綠才算完成。

## 核心心得

1. **先定契約，再寫程式。** v1 的 11 段 prompt 各自獨立，LLM 每次都重新「猜」錯誤格式、檔名、限制，結果五個 route 五種寫法。v2 把所有跨檔案的決定集中在 `00-context.md`，每個 prompt 都引用同一份。
2. **單一資料來源（registry）。** v1 是 5 段幾乎相同的 prompt → 5 份 copy-paste 程式碼。v2 用一張轉換表描述差異，要求程式碼由表格驅動，禁止重複的 route body。
3. **規則要寫在 server 端的 prompt。** v1 只有前端 prompt 提到「小於 5 MB」，於是只有前端（和剛好一個 route）有檢查。安全與限制必須寫在 backend prompt，前端只是 UX 鏡像。
4. **把「沒說的事」說出來。** 大小寫、損毀檔案、透明度、錯誤格式、debug 模式、像素上限——v1 一個都沒提，LLM 就照最簡單的方式寫。v2 對每一項都給出明確行為。
5. **錯誤行為也是規格。** v1 只描述 happy path。v2 為每種錯誤指定 status code 與 JSON 形狀，並明確規定 500 不得洩漏 stack trace。
6. **驗收條件要可執行。** 每個 v2 prompt 都有 Acceptance criteria，並由 `03-tests.md` 轉成 pytest。拿同一套 API 測試跑 v1 程式碼，絕大多數會失敗——這就是 prompt 缺口的量化證據。
7. **固定環境。** 明確寫出 Python 3.9、禁止 3.10+ 語法、禁止額外依賴，避免 LLM 產出跑不起來的程式碼。

## 缺陷對照表

測試皆位於 `tests/test_api.py`（頁面測試在 `tests/test_pages.py`，啟動設定在 `tests/test_startup.py`）。

| # | v1 缺陷 | v1 prompt 缺了什麼 | v2 修正條款 | 守護測試 |
|---|---|---|---|---|
| 1 | `/api/jpgtopng` 用區分大小寫的 `endswith`，`photo.JPG` 被拒 | 只說「jpg format」，沒說副檔名比對規則 | `00-context`：registry 欄位「accepted extensions (case-insensitive)」；`01-backend` 步驟 2：`os.path.splitext` 後 lower-case 比對 | `test_jpeg_extension_variants_are_accepted` |
| 2 | 只有 jpgtopng 在 server 端檢查 5 MB；沒有 `MAX_CONTENT_LENGTH` | 5 MB 只寫在前端 prompt，backend prompt 完全沒提 | `00-context` Limits 表：server 端強制 5 MB → 413，`MAX_CONTENT_LENGTH = 6 MB`；`01-backend` 步驟 3 與 413 error handler | `test_file_over_5mb_is_rejected`（5 個 endpoint 全測）、`test_max_content_length_is_configured`、`test_request_over_max_content_length_is_rejected` |
| 3 | 除 webp 外沒有例外處理，損毀檔案 → 500 HTML 錯誤頁 | 從未規定錯誤行為或回應格式 | `00-context` API contract：錯誤一律 `{"error": ...}` JSON、status code 對照表；`01-backend` 步驟 4、7、8 | `test_unreadable_content_is_rejected`、`test_unexpected_conversion_failure_returns_json_500`；所有錯誤測試共用的 `assert_json_error` |
| 4 | 只看副檔名或 client 送來的 mimetype（pngtopdf），不檢查實際內容 | 只說「check image is png format」，沒定義「format」怎麼判斷 | `00-context` Conversion rules：「Validate by real content」，比對 `img.format`；`01-backend` Constraints：不得信任 `file.mimetype` | `test_real_format_must_match_extension` |
| 5 | pngtojpg 直接 `convert('RGB')`，透明像素變黑；pngtopdf 遇到 RGBA 可能失敗（依 Pillow 版本而定） | 完全沒提透明度 | `00-context` Conversion rules：轉 JPEG/PDF 時透明區域合成到**白色**背景；轉 PNG 保留 alpha | `test_png_to_jpg_flattens_transparency_onto_white`、`test_png_to_pdf_accepts_transparency`、`test_webp_to_png_keeps_alpha` |
| 6 | `app.run(debug=True)`，部署後 Werkzeug debugger 可遠端執行程式碼 | 只說「Code for Python, Flask server」，沒有任何安全預設 | `00-context` Security defaults：`FLASK_DEBUG` 控制、預設關閉、禁止寫死 `debug=True`；`01-backend` 第 6 項 Entry point | `tests/test_startup.py` 的 `test_debug_off_by_default`、`test_debug_enabled_only_by_flask_debug_env` |
| 7 | 沒有 decompression bomb／像素上限 | 沒提輸入大小以外的資源限制 | `00-context` Limits：`width * height <= 40,000,000`，`DecompressionBombError` → 400；`01-backend` 步驟 5：解碼前先檢查 | `test_image_with_too_many_pixels_is_rejected` |
| 8 | 5 個 copy-paste route + 5 個 copy-paste template，樣式不一致、用 `alert()`、下載檔名不一致（`image.png` vs `converted.png`）、未使用的 `.container` class | 每段 prompt 單獨下達，沒有共用規範；5 段 prompt 本身就是複製貼上 | `00-context` registry 與 Style；`01-backend` 單一 handler；`02-frontend` 一個 `converter.html` + 一個 CSS + 一個 JS、禁止 `alert()`、檔名取自 `Content-Disposition` | `test_conversion_succeeds`、`test_download_filename_is_sanitized`、`tests/test_pages.py` 的 `test_page_renders_html`、`test_converter_page_uses_api_rules` |
| 9 | 前端（jpgtopng）不檢查 `response.ok`，server 錯誤訊息會被當成 `image.png` 下載 | 只說「send POST request」，沒說收到錯誤時怎麼辦 | `02-frontend` 行為第 5 點：非 2xx 讀取 `error` 並 inline 顯示，**絕不**把錯誤回應當檔案下載 | 前端無自動化測試；由 `02-frontend` Acceptance criteria 人工驗收 |
| 10 | 必要欄位檢查不一致（只有 bmptopng 檢查空檔名），錯誤訊息五種寫法 | 同 #3，且沒有共用規範 | `01-backend` 步驟 1 | `test_missing_image_field_is_rejected`、`test_empty_filename_is_rejected` |
| 11 | 沒有 `requirements.txt`、沒有測試、沒有 README | 沒有要求任何交付物以外的工程產出 | `01-backend` 產出 `requirements*.txt`；`03-tests` 產出測試；`04-docs` 產出 README | `pytest` 本身 |

## 自己驗證

把 v2 的測試套用到 v1 程式碼上（不會動到工作目錄）：

```bash
mkdir -p /tmp/image-tools-v1
git archive 076968a | tar -x -C /tmp/image-tools-v1
cp -r tests pytest.ini /tmp/image-tools-v1/
(cd /tmp/image-tools-v1 && "$OLDPWD/.venv/bin/pytest" -q tests/test_api.py tests/test_startup.py)   # 46 failed, 4 passed
.venv/bin/pytest -q                                          # v2：全部通過
```
