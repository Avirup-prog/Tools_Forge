# ToolForge API — Phase 4 Backend

FastAPI backend for [ToolForge](https://toolforge.netlify.app) — 30 server-side tools across PDF, Image, Video/Audio, and Utilities.

**Live API:** `https://toolforge-api.onrender.com`  
**Docs:** `https://toolforge-api.onrender.com/docs`

---

## File Structure

```
phase4/
├── main.py              # FastAPI app, CORS, router mounting
├── requirements.txt     # All Python dependencies
├── render.yaml          # Render deployment config
├── build_deps.sh        # System package install script
│
├── routers/
│   ├── pdf.py           # 14 PDF endpoints
│   ├── image.py         # 8 Image endpoints (incl. 2 AI tools)
│   ├── media.py         # 7 Video/Audio endpoints
│   └── utils.py         # 1 Utility endpoint (URL shortener)
│
├── utils/
│   └── helpers.py       # Shared: temp files, MIME checks, error wrapper
│
└── assets/js/           # (copy to frontend assets/js/)
    ├── api-client.js    # Shared API client used by all tool pages
    └── tool-page-api.js # Drop-in script that activates upload UI
```

---

## Endpoints

### PDF (14 endpoints) — `/api/pdf/`

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/to-word` | POST | PDF | DOCX |
| `/from-word` | POST | DOCX | PDF |
| `/to-excel` | POST | PDF | XLSX |
| `/to-ppt` | POST | PDF | PPTX |
| `/merge` | POST | PDFs (multiple) | PDF |
| `/split` | POST | PDF + `ranges` | ZIP of PDFs |
| `/compress` | POST | PDF | PDF |
| `/encrypt` | POST | PDF + `password` | PDF |
| `/decrypt` | POST | PDF + `password` | PDF |
| `/rotate` | POST | PDF + `angle` | PDF |
| `/to-image` | POST | PDF | ZIP of PNGs |
| `/from-image` | POST | Images (multiple) | PDF |
| `/watermark` | POST | PDF + `text` | PDF |
| `/fill-sign` | POST | PDF + signature image | PDF |

### Image (8 endpoints) — `/api/image/`

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/compress` | POST | Image | Image |
| `/resize` | POST | Image + dimensions | Image |
| `/convert` | POST | Image + `to_format` | Image |
| `/watermark` | POST | Image + `text` | Image |
| `/collage` | POST | Images (multiple) | PNG |
| `/color-pick` | POST | Image | JSON (color list) |
| `/remove-bg` ⚡ AI | POST | Image | PNG (transparent) |
| `/upscale` ⚡ AI | POST | Image + `scale` | PNG |

### Media (7 endpoints) — `/api/media/`

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/video-compress` | POST | Video | MP4 |
| `/video-convert` | POST | Video + `to_format` | Video |
| `/extract-audio` | POST | Video + `to_format` | Audio |
| `/audio-convert` | POST | Audio + `to_format` | Audio |
| `/gif-maker` | POST | Video + `start/duration` | GIF |
| `/trim` | POST | Video/Audio + `start/end` | Same format |
| `/volume-boost` | POST | Audio + `db` | Audio |

### Utils (1 endpoint) — `/api/utils/`

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/shorten-url` | POST | `{"url": "..."}` | JSON |

---

## Local Development

```bash
# 1. Clone and enter directory
cd phase4

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install system deps (macOS with Homebrew)
brew install poppler ffmpeg

# 4. Install Python deps
pip install -r requirements.txt

# 5. Run dev server
python main.py
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

---

## Deploy to Render

1. Push this `phase4/` folder to a GitHub repo (e.g. `toolforge-api`)
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Settings:
   - **Environment:** Python 3
   - **Build command:** `bash build_deps.sh`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy — first deploy takes ~3 min
6. Copy the `https://toolforge-api.onrender.com` URL
7. Update `BASE_URL` in `assets/js/api-client.js` if different

> ⚠️ **Free tier cold starts:** Render free tier sleeps after 15 min of inactivity.
> The `ToolForgeAPI.warmup()` call in `api-client.js` pings `/health` on page load
> to pre-warm the instance. Users still see a ~10s delay on first request after
> idle. Upgrade to Starter ($7/mo) to eliminate this.

---

## Frontend Integration

### Step 1 — Copy JS files

```
assets/
└── js/
    ├── main.js              (existing)
    ├── api-client.js        ← copy from phase4/
    └── tool-page-api.js     ← copy from phase4/
```

### Step 2 — Add scripts to API tool pages

In every `tools/*.html` that has `badge: "api"` or `badge: "ai"`, add just before `</body>`:

```html
<!-- Phase 4 API -->
<script>
  window.TOOL_CONFIG = {
    endpoint: '/api/pdf/to-word',   // ← the tool's endpoint
    multiFile: false,
    fieldSelectors: {},             // ← map formField -> CSS selector
  };
</script>
<script src="../assets/js/api-client.js"></script>
<script src="../assets/js/tool-page-api.js"></script>
```

### Step 3 — Re-run build.py

The Jinja2 build script (`build.py`) should inject these scripts automatically via
the template. Add an `api_tools` variable to `tools.json` or detect `badge === "api"`
in the template — then regenerate all 65 pages.

---

## Libraries Used

| Library | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pdfplumber` | PDF text + table extraction |
| `pypdf` | PDF manipulation (merge/split/encrypt/rotate) |
| `python-docx` | DOCX read/write |
| `reportlab` | PDF generation (watermarks, word→PDF) |
| `pdf2image` | PDF page → PIL image (needs poppler) |
| `img2pdf` | PIL images → PDF |
| `Pillow` | Image processing |
| `rembg` | AI background removal |
| `opencv-python-headless` | Image upscaling + color clustering |
| `ffmpeg-python` | Video/audio processing (wraps ffmpeg binary) |
| `pydub` | Audio utilities |
| `httpx` | Async HTTP (URL shortener) |
| `python-multipart` | File upload support for FastAPI |
