"""
OCR utilities: extract structured data from Eve Echoes screenshots.

Two backends are supported:
  • openai   – GPT-4o Vision (best accuracy; requires OPENAI_API_KEY)
  • tesseract – local Tesseract OCR (fallback; less accurate on mobile UI)
"""

from __future__ import annotations

import re
import base64
import asyncio
from io import BytesIO
from typing import Any

import aiohttp
from PIL import Image

from bot.config import OCR_BACKEND, OPENAI_API_KEY, OPENAI_MODEL


# ── Shared helpers ─────────────────────────────────────────────────────────────

async def _fetch_image_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()


def _image_to_base64(data: bytes) -> str:
    img = Image.open(BytesIO(data)).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ── OpenAI Vision backend ──────────────────────────────────────────────────────

async def _ask_openai_vision(image_b64: str, prompt: str) -> str:
    import openai
    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content or ""


# ── Tesseract backend ──────────────────────────────────────────────────────────

def _tesseract_ocr(data: bytes) -> str:
    try:
        import pytesseract
        img = Image.open(BytesIO(data))
        return pytesseract.image_to_string(img, lang="eng")
    except Exception as exc:
        return f"[tesseract error: {exc}]"


async def _run_ocr(data: bytes, prompt: str) -> str:
    """Run OCR on image bytes using the configured backend."""
    if OCR_BACKEND == "openai":
        b64 = _image_to_base64(data)
        return await _ask_openai_vision(b64, prompt)
    return await asyncio.get_event_loop().run_in_executor(None, _tesseract_ocr, data)


# ── Public API ─────────────────────────────────────────────────────────────────

async def ocr_raw(url: str) -> str:
    """Return raw text extracted from an image URL."""
    data = await _fetch_image_bytes(url)
    return await _run_ocr(data, "Extract ALL visible text from this screenshot exactly as shown.")


async def extract_registration(url: str) -> dict[str, Any]:
    """
    Parse a pilot registration screenshot.
    Expected fields: pilot_name, corporation, alliance (optional).
    """
    data = await _fetch_image_bytes(url)
    prompt = (
        "This is a screenshot from Eve Echoes. "
        "Extract the pilot name, corporation name, and alliance name (if shown). "
        "Reply ONLY with valid JSON like: "
        '{"pilot_name": "...", "corporation": "...", "alliance": "..."}'
    )
    raw = await _run_ocr(data, prompt)
    return _parse_json_safe(raw, {"pilot_name": "", "corporation": "", "alliance": ""})


async def extract_isk(url: str) -> dict[str, Any]:
    """
    Parse a wallet / ISK screenshot.
    Returns: {"isk_amount": int, "description": str}
    """
    data = await _fetch_image_bytes(url)
    prompt = (
        "This is a wallet or transaction screenshot from Eve Echoes (mobile). "
        "Extract the total ISK amount and a short description of the transaction. "
        "Reply ONLY with valid JSON like: "
        '{"isk_amount": 12345678, "description": "Mining reward"}'
    )
    raw = await _run_ocr(data, prompt)
    result = _parse_json_safe(raw, {"isk_amount": 0, "description": ""})
    result["isk_amount"] = _safe_int(result.get("isk_amount", 0))
    return result


async def extract_kill(url: str) -> dict[str, Any]:
    """
    Parse a kill-mail or battle-report screenshot.
    Returns: {"pilot_name", "ship_name", "victim_name", "victim_ship",
               "system", "isk_value", "kill_type"}
    """
    data = await _fetch_image_bytes(url)
    prompt = (
        "This is a kill-mail or combat log screenshot from Eve Echoes. "
        "Extract: attacking pilot name, attacker's ship, victim pilot name, victim's ship, "
        "solar system, ISK value destroyed, and whether this was a PvP kill or PvE kill. "
        "Reply ONLY with valid JSON: "
        '{"pilot_name":"...","ship_name":"...","victim_name":"...","victim_ship":"...",'
        '"system":"...","isk_value":0,"kill_type":"pvp"}'
    )
    raw = await _run_ocr(data, prompt)
    result = _parse_json_safe(raw, {
        "pilot_name": "", "ship_name": "", "victim_name": "", "victim_ship": "",
        "system": "", "isk_value": 0, "kill_type": "pvp",
    })
    result["isk_value"] = _safe_int(result.get("isk_value", 0))
    return result


async def extract_ship_loss(url: str) -> dict[str, Any]:
    """
    Parse a ship-loss / destruction screenshot for compensation.
    Returns: {"pilot_name", "ship_name", "isk_value", "system"}
    """
    data = await _fetch_image_bytes(url)
    prompt = (
        "This is a ship destruction / loss notification from Eve Echoes. "
        "Extract: pilot name, destroyed ship name, estimated ISK value, solar system. "
        "Reply ONLY with valid JSON: "
        '{"pilot_name":"...","ship_name":"...","isk_value":0,"system":"..."}'
    )
    raw = await _run_ocr(data, prompt)
    result = _parse_json_safe(raw, {"pilot_name": "", "ship_name": "", "isk_value": 0, "system": ""})
    result["isk_value"] = _safe_int(result.get("isk_value", 0))
    return result


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_json_safe(text: str, default: dict) -> dict:
    import json
    # strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    # find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return default


def _safe_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    s = str(value).replace(",", "").replace(".", "").replace(" ", "")
    m = re.search(r"\d+", s)
    return int(m.group()) if m else 0
