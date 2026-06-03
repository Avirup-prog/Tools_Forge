#!/usr/bin/env python3
"""
build.py — ToolForge Phase 2 build automation
===============================================
Reads tools.json and uses Jinja2 to auto-generate one HTML page per tool.

Usage:
    python build.py                  # generate all 65 tool pages
    python build.py --tool pdf-to-word   # regenerate a single tool
    python build.py --dry-run        # validate template + config, no files written
    python build.py --stats          # print category/badge breakdown

Output:
    dist/tools/<tool-id>.html        (65 files)
    dist/sitemap.xml                 (auto-generated sitemap)
    dist/tools.manifest.json         (build manifest for Netlify)
"""

import json
import shutil
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:
    sys.exit("❌  Jinja2 not installed. Run: pip install jinja2")

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
TOOLS_JSON = ROOT / "tools.json"
TMPL_DIR   = ROOT / "templates"
DIST_DIR   = ROOT / "dist"
OUT_DIR    = DIST_DIR / "tools"

# ── Jinja2 custom filters ────────────────────────────────────────────────────
MIME_EXT_MAP = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/zip":   ".zip",
    "application/json":  ".json",
    "image/jpeg":  ".jpg",
    "image/png":   ".png",
    "image/webp":  ".webp",
    "image/gif":   ".gif",
    "image/bmp":   ".bmp",
    "image/*":     ".img",
    "audio/mpeg":  ".mp3",
    "audio/wav":   ".wav",
    "audio/ogg":   ".ogg",
    "audio/*":     ".audio",
    "video/mp4":   ".mp4",
    "video/webm":  ".webm",
    "video/mov":   ".mov",
    "video/*":     ".video",
}

def mime_to_ext(mime: str) -> str:
    """Return a file extension for a MIME type."""
    return MIME_EXT_MAP.get(mime, "")

def hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R,G,B' string for rgba() CSS."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    except (ValueError, IndexError):
        return "56,189,248"  # fallback: cyan

# ── Build helpers ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    """Load and validate tools.json."""
    if not TOOLS_JSON.exists():
        sys.exit(f"❌  {TOOLS_JSON} not found.")
    with open(TOOLS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if "categories" not in data or "meta" not in data:
        sys.exit("❌  tools.json missing 'categories' or 'meta' key.")
    return data

def build_lookup(data: dict) -> dict[str, dict]:
    """Build a flat id → {tool, cat} lookup for related-tool resolution."""
    lookup: dict[str, dict] = {}
    for cat in data["categories"]:
        for tool in cat["tools"]:
            lookup[tool["id"]] = {"tool": tool, "cat": cat}
    return lookup

def make_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TMPL_DIR)),
        undefined=StrictUndefined,
        autoescape=False,          # we control the HTML, no user input in template vars
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["mime_to_ext"] = mime_to_ext
    env.filters["hex_to_rgb"]  = hex_to_rgb
    return env

def render_tool(tmpl, tool: dict, cat: dict, meta: dict, lookup: dict) -> str:
    """Render one tool page."""
    related_tools = []
    for rid in tool.get("related", []):
        if rid in lookup and rid != tool["id"]:
            related_tools.append(lookup[rid]["tool"])

    return tmpl.render(
        tool=tool,
        cat=cat,
        meta=meta,
        related_tools=related_tools,
    )

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

# ── Sitemap ───────────────────────────────────────────────────────────────────
def generate_sitemap(data: dict, out_path: Path) -> None:
    meta = data["meta"]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # Homepage
    lines.append(f"  <url><loc>{meta['base_url']}/</loc><changefreq>weekly</changefreq><priority>1.0</priority><lastmod>{now}</lastmod></url>")
    for cat in data["categories"]:
        for tool in cat["tools"]:
            loc = f"{meta['base_url']}/tools/{tool['id']}.html"
            lines.append(f"  <url><loc>{loc}</loc><changefreq>monthly</changefreq><priority>0.7</priority><lastmod>{now}</lastmod></url>")
    lines.append("</urlset>")
    write_file(out_path, "\n".join(lines))
    print(f"  📡  sitemap.xml → {out_path.relative_to(ROOT)}")

# ── Manifest ──────────────────────────────────────────────────────────────────
def generate_manifest(data: dict, generated: list[str], out_path: Path) -> None:
    manifest = {
        "build_time": datetime.now(timezone.utc).isoformat(),
        "total_tools": len(generated),
        "categories":  len(data["categories"]),
        "pages": generated,
    }
    write_file(out_path, json.dumps(manifest, indent=2))
    print(f"  📋  manifest → {out_path.relative_to(ROOT)}")

# ── Stats ─────────────────────────────────────────────────────────────────────
def print_stats(data: dict) -> None:
    from collections import Counter
    badges: Counter = Counter()
    print("\n📊  ToolForge — tools.json stats")
    print("─" * 44)
    total = 0
    for cat in data["categories"]:
        n = len(cat["tools"])
        total += n
        cat_badges = Counter(t["badge"] for t in cat["tools"])
        badge_str = "  ".join(f"{v}×{k.upper()}" for k, v in sorted(cat_badges.items()))
        print(f"  {cat['icon']}  {cat['label']:<22}  {n:>2} tools   {badge_str}")
        badges.update(cat_badges)
    print("─" * 44)
    print(f"  Total: {total} tools")
    print(f"  Badges: {dict(badges)}\n")

# ── Main build ────────────────────────────────────────────────────────────────
def build(target_id: str | None = None, dry_run: bool = False) -> None:
    data   = load_config()
    lookup = build_lookup(data)
    env    = make_jinja_env()
    meta   = data["meta"]

    try:
        tmpl = env.get_template("tool.html.j2")
    except Exception as e:
        sys.exit(f"❌  Template error: {e}")

    generated: list[str] = []
    errors: list[str] = []

    print(f"\n🔨  ToolForge build.py — Phase 2")
    print(f"    Output: {OUT_DIR.relative_to(ROOT)}/")
    print(f"    Mode:   {'DRY RUN' if dry_run else 'WRITE'}")
    print(f"    Target: {target_id or 'all 65 tools'}\n")

    for cat in data["categories"]:
        for tool in cat["tools"]:
            if target_id and tool["id"] != target_id:
                continue

            out_path = OUT_DIR / f"{tool['id']}.html"
            try:
                html = render_tool(tmpl, tool, cat, meta, lookup)
                if not dry_run:
                    write_file(out_path, html)
                badge_icon = {"js": "⚡", "api": "🔌", "ai": "✨"}.get(tool["badge"], "  ")
                status = "  (dry)" if dry_run else f"  {len(html):,} chars"
                print(f"  {badge_icon}  tools/{tool['id']}.html{status}")
                generated.append(f"tools/{tool['id']}.html")
            except Exception as e:
                errors.append(f"{tool['id']}: {e}")
                print(f"  ❌  tools/{tool['id']}.html — {e}")

    if not dry_run and not target_id:
        generate_sitemap(data, DIST_DIR / "sitemap.xml")
        generate_manifest(data, generated, DIST_DIR / "tools.manifest.json")

    print(f"\n{'✅' if not errors else '⚠️ '}  Done: {len(generated)} pages generated", end="")
    print(f", {len(errors)} errors" if errors else "")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)

# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="ToolForge Phase 2 — Jinja2 build script"
    )
    parser.add_argument("--tool",     metavar="ID",  help="Regenerate a single tool by ID")
    parser.add_argument("--dry-run",  action="store_true", help="Validate only, no files written")
    parser.add_argument("--stats",    action="store_true", help="Print tools.json breakdown and exit")
    parser.add_argument("--clean",    action="store_true", help="Delete dist/tools/ before building")
    args = parser.parse_args()

    if args.stats:
        print_stats(load_config())
        return

    if args.clean and OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
        print(f"🗑️   Cleaned {OUT_DIR.relative_to(ROOT)}/")

    build(target_id=args.tool, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
