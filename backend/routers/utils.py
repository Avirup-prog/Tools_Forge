"""
routers/utils.py — utility endpoints
POST /api/utils/shorten-url
"""

import json
import re
from fastapi import APIRouter
from fastapi.responses import Response
import httpx

from utils.helpers import tool_error

router = APIRouter()

# Using is.gd — free, no auth needed, generous rate limits
ISGD_API = "https://is.gd/create.php"


# ─────────────────────────────────────────────────────────────────────────────
# URL Shortener  /api/utils/shorten-url
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/shorten-url", summary="Shorten a URL using is.gd")
async def shorten_url(body: dict):
    url = (body.get("url") or "").strip()
    if not url:
        raise tool_error("'url' field is required.")

    # Basic URL validation
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise tool_error("URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                ISGD_API,
                params={"format": "json", "url": url},
            )
            data = resp.json()

        if "shorturl" in data:
            return Response(
                content=json.dumps({
                    "original": url,
                    "short": data["shorturl"],
                    "provider": "is.gd",
                }),
                media_type="application/json",
            )
        else:
            # is.gd returns {"errorcode":..., "errormessage":...} on failure
            msg = data.get("errormessage", "Could not shorten URL.")
            raise tool_error(f"Shortener error: {msg}")

    except httpx.TimeoutException:
        raise tool_error("URL shortener service timed out. Please try again.", 503)
    except tool_error.__class__:
        raise
    except Exception as e:
        raise tool_error(f"URL shortener failed: {e}", 500)
