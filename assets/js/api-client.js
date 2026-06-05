/**
 * api-client.js — ToolForge Phase 4 frontend API client
 * Drop this in assets/js/ and include it on every API tool page.
 *
 * Usage on a tool page:
 *   ToolForgeAPI.upload({
 *     endpoint: '/api/pdf/to-word',
 *     file: fileObj,              // File from <input type="file">
 *     fields: { quality: 75 },   // optional extra FormData fields
 *     onProgress: (pct) => {},    // 0-100
 *     onSuccess: (blob, filename) => {},
 *     onError: (msg) => {},
 *   });
 */

const ToolForgeAPI = (() => {
  // ── Config ──────────────────────────────────────────────────────────────────
  const BASE_URL = "https://toolforge-api-o6q8.onrender.com";

  // Warn-once flag for cold-start UX message
  let _coldStartWarned = false;

  // ── Core upload function ─────────────────────────────────────────────────────
  async function upload({
    endpoint,
    file,
    files,        // array of File — for multi-file endpoints (merge, collage, image-to-pdf)
    fields = {},
    onProgress = () => {},
    onSuccess,
    onError,
  }) {
    const form = new FormData();

    if (files && files.length) {
      files.forEach((f) => form.append("files", f));
    } else if (file) {
      // Detect whether the server expects "file", "pdf_file", or "files"
      const key = endpoint.includes("fill-sign") ? "pdf_file" : "file";
      form.append(key, file);
    }

    for (const [k, v] of Object.entries(fields)) {
      if (v !== null && v !== undefined && v !== "") {
        form.append(k, String(v));
      }
    }

    // ── XHR for progress events ────────────────────────────────────────────
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = async () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const blob = xhr.response;
          const cd = xhr.getResponseHeader("Content-Disposition") || "";
          const match = cd.match(/filename="([^"]+)"/);
          const filename = match ? match[1] : "result";
          onSuccess(blob, filename);
          resolve({ blob, filename });
        } else {
          // Try to parse JSON error body
          let msg = `Server error ${xhr.status}`;
          try {
            const text = await new Response(xhr.response).text();
            const parsed = JSON.parse(text);
            if (Array.isArray(parsed.detail)) {
              msg = parsed.detail.map(x => x.msg).join(', ');
}           else {
              msg = parsed.detail || parsed.message || msg;
}
          } catch (_) {}
          onError(msg);
          reject(new Error(msg));
        }
      };

      xhr.onerror = () => {
        const msg = "Network error — is the API server online?";
        onError(msg);
        reject(new Error(msg));
      };

      xhr.ontimeout = () => {
        const msg = "Request timed out. The server may be waking up — try again.";
        onError(msg);
        reject(new Error(msg));
      };

      xhr.open("POST", BASE_URL + endpoint);
      xhr.responseType = "blob";
      xhr.timeout = 120_000; // 2 min for heavy processing
      xhr.send(form);

      // Cold-start UX: if > 10s with no response, show a friendly note
      setTimeout(() => {
        if (!_coldStartWarned) {
          _coldStartWarned = true;
          onProgress(-1); // signal "still working"
        }
      }, 10_000);
    });
  }

  // ── JSON POST (for URL shortener) ─────────────────────────────────────────
  async function post(endpoint, body, { onError } = {}) {
    const resp = await fetch(BASE_URL + endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) {
      const msg = data.detail || `Error ${resp.status}`;
      if (onError) onError(msg);
      throw new Error(msg);
    }
    return data;
  }

  // ── Auto-download helper ───────────────────────────────────────────────────
  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }

  // ── Wake-up ping ───────────────────────────────────────────────────────────
  // Call this on page load for API tool pages so the Render instance warms up
  // before the user hits "process"
  async function warmup() {
    try {
      await fetch(BASE_URL + "/health", { method: "GET", cache: "no-store" });
    } catch (_) {}
  }

  return { upload, post, download, warmup, BASE_URL };
})();

// Auto-warmup when script loads on an API tool page
ToolForgeAPI.warmup();
