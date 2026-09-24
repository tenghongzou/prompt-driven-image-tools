# prompt-driven-image-tools

> 同一個小專案、兩套 prompt：看 prompt 的品質如何直接決定 AI 產生的程式碼品質。

這是一個用 **Flask + Pillow** 寫的圖片格式轉換網站，同時也是一份 **「Prompt 驅動開發」的示範教材**：

| 版本 | Prompt | 程式碼 | 結果 |
|---|---|---|---|
| **v1** | [`app.txt`](app.txt)：11 段各自獨立、只描述 happy path 的 prompt | commit `076968a` | 能動，但有大小寫、錯誤處理、透明度、安全性等 11 項缺陷 |
| **v2** | [`prompts/v2/`](prompts/v2/)：先定共用規範，再下達任務，每段附驗收條件 | 目前的 `master` | 61 項測試全數通過 |

拿 v2 的測試去跑 v1 的程式碼：**46 failed, 4 passed**。這就是 prompt 缺口的量化結果。

## 目錄

- [功能](#功能)
- [快速開始](#快速開始)
- [API](#api)
- [專案結構](#專案結構)
- [Demo 導覽](#demo-導覽)
- [從 v1 學到的事](#從-v1-學到的事)
- [安全性](#安全性)

## 功能

| 頁面 | API | 接受的輸入（副檔名不分大小寫） | 輸出 |
|---|---|---|---|
| `/jpgtopng` | `POST /api/jpgtopng` | `.jpg`、`.jpeg` | PNG |
| `/pngtojpg` | `POST /api/pngtojpg` | `.png` | JPG，透明區域轉為白色 |
| `/webptopng` | `POST /api/webptopng` | `.webp` | PNG，保留 alpha |
| `/bmptopng` | `POST /api/bmptopng` | `.bmp` | PNG |
| `/pngtopdf` | `POST /api/pngtopdf` | `.png` | PDF，透明區域轉為白色 |

- 全程在記憶體內處理（`io.BytesIO`），不寫入磁碟。
- 以 Pillow 讀出的實際格式驗證，不信任副檔名；PNG 改名成 `.jpg` 會被拒絕。
- 前端支援拖放上傳、深色模式、鍵盤操作，錯誤訊息直接顯示在頁面上。

## 快速開始

需要 Python 3.9 以上。

```bash
git clone git@github.com:tenghongzou/prompt-driven-image-tools.git
cd prompt-driven-image-tools

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # 只需執行網站的話，裝 requirements.txt 即可

python app.py                         # http://127.0.0.1:5000
pytest                                # 61 passed
```

本機開發要開 debug 模式：`FLASK_DEBUG=1 python app.py`。

## API

**Request**：`POST /api/<converter>`，格式為 `multipart/form-data`，檔案欄位名稱是 `image`。

**成功回應**：`200`，body 是轉換後的檔案。

```
Content-Disposition: attachment; filename=<stem>.<ext>
```

`stem` 是原檔名去掉副檔名、經 `secure_filename` 處理後的結果，處理後為空就用 `converted`。例如上傳 `My Photo.JPG`，會下載成 `My_Photo.png`。

**失敗回應**：一律是 JSON，不會回 HTML 錯誤頁或 stack trace。

```json
{"error": "<human readable message>"}
```

| Status | 情況 |
|---|---|
| `400` | 缺少 `image` 欄位、沒有選檔案、副檔名不符、檔案無法讀取、實際格式與副檔名不符、超過 40,000,000 像素 |
| `413` | 檔案超過 5 MB，或整個 request 超過 6 MB |
| `500` | 轉換時發生非預期錯誤，固定回 `{"error": "Conversion failed"}` |

**範例**

```bash
# 成功：-OJ 依 Content-Disposition 存成 photo.png
curl -F image=@photo.jpg -OJ http://127.0.0.1:5000/api/jpgtopng

# 失敗：副檔名不符
curl -F image=@photo.jpg http://127.0.0.1:5000/api/pngtojpg
# {"error":"Unsupported file type; expected .png"}
```

## 專案結構

```
app.py                    # 後端：CONVERSIONS 轉換表驅動所有 route、驗證與轉換
templates/
  base.html               # 共用版型（header、nav、footer）
  _tools.html             # 各工具的顯示文字；驗證規則由 app.py 注入，不重複定義
  index.html              # 首頁：工具卡片
  converter.html          # 共用的轉換頁
  jpgtopng.html …         # 5 個，每個兩行：extends converter.html 並指定工具
static/
  style.css               # 唯一的樣式表（含深色模式）
  converter.js            # 唯一的前端腳本：前置檢查、上傳、錯誤顯示、下載
tests/
  test_api.py             # API 契約、驗證、大小限制、透明度、500 錯誤
  test_pages.py           # 頁面可 render，且前端規則與 API 一致
  test_startup.py         # debug 預設關閉
prompts/
  README.md               # v1 → v2 缺陷對照表與心得
  v2/                     # v2 prompts：00 共用規範 + 01～04 任務
app.txt                   # v1 原始 prompts（保留作對照，請勿修改）
requirements.txt          # Flask、Pillow
requirements-dev.txt      # + pytest
```

## Demo 導覽

大約 5 分鐘，帶人走過「prompt 品質 → 程式碼品質」。

**1. 看 v1 prompt**

```bash
cat app.txt
```

11 段 prompt 各自獨立。5 MB 限制只出現在前端 prompt；錯誤格式、大小寫、透明度、安全性完全沒提。

**2. 看 v1 程式碼**

```bash
git show 076968a:app.py
git show 076968a:templates/jpgtopng.html
```

可以指出的問題：`endswith('.jpg')` 區分大小寫、只有一個 route 檢查 5 MB、`convert('RGB')` 讓透明變黑、`debug=True`、`alert()`、下載檔名有的是 `image.png`，有的是 `converted.png`。

**3. 用 v2 測試量化 v1 的缺陷**（不會動到工作目錄）

```bash
mkdir -p /tmp/image-tools-v1
git archive 076968a | tar -x -C /tmp/image-tools-v1
cp -r tests pytest.ini /tmp/image-tools-v1/
(cd /tmp/image-tools-v1 && "$OLDPWD/.venv/bin/pytest" -q tests/test_api.py tests/test_startup.py)
# 46 failed, 4 passed
```

**4. 看 v2 prompt**

```bash
cat prompts/v2/00-context.md   # 共用規範：轉換表、限制、錯誤格式、安全預設
cat prompts/v2/01-backend.md   # 步驟化的驗證流程 + 驗收條件
```

**5. 看 v2 程式碼並跑測試**

```bash
cat app.py
pytest -q                      # 61 passed
```

## 從 v1 學到的事

完整的缺陷對照表在 [`prompts/README.md`](prompts/README.md)，每一列說明：v1 缺陷 → prompt 缺了什麼 → v2 哪一條補上 → 哪個測試守住。重點整理：

1. **先定規範，再寫程式。** 跨檔案的決定（錯誤格式、檔名、限制）集中寫在一份共用 context，每段 prompt 都引用它。
2. **單一資料來源。** 用一張轉換表描述 5 種轉換的差異，取代 5 段複製貼上的 prompt 和程式碼。
3. **限制寫在後端。** 前端檢查只是 UX；安全和限制要寫進 backend prompt。
4. **把沒說的事說出來。** LLM 會用最簡單的方式填補空白。大小寫、損毀檔案、透明度、debug 模式都要明確規定。
5. **錯誤行為也是規格。** 每種錯誤都要指定 status code 與回應格式。
6. **驗收條件要能執行。** 每段 prompt 的驗收條件都轉成 pytest，才能客觀判斷 AI 有沒有做到。

## 安全性

- **Debug 預設關閉**，只有 `FLASK_DEBUG=1` 才會開啟。Werkzeug debugger 可以執行任意程式碼，對外環境絕對不要開。
- **預設只綁定 `127.0.0.1:5000`。**
- **大小限制**：單檔 5 MB、整個 request 6 MB（`MAX_CONTENT_LENGTH`）。
- **像素上限** 40,000,000，防止 decompression bomb。
- **依內容驗證格式**，不信任副檔名或 client 送來的 mimetype。
- **不寫入磁碟**；上傳檔名只經 `secure_filename` 處理後用於下載檔名。

這是示範專案，沒有 rate limiting 或身分驗證。正式上線請改用 WSGI server（例如 gunicorn），並放在 reverse proxy 後面。
