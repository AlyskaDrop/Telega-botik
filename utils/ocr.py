"""OCR utility: extract text from a Telegram photo using pytesseract."""

from __future__ import annotations

import io
import re

import pytesseract
from PIL import Image

import config


pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

# Keywords used to classify a screenshot ──────────────────────────────────────
_PVP_KEYWORDS = re.compile(
    r"kill|pvp|destroyed|damage|enemy|hostile|战斗|击杀|摧毁",
    re.IGNORECASE,
)
_PVE_KEYWORDS = re.compile(
    r"bounty|npc|rat|anomaly|combat|reward|星系|赏金|异常",
    re.IGNORECASE,
)
_LOOT_KEYWORDS = re.compile(
    r"loot|cargo|drop|deliver|transfer|isk|矿|货物|转账",
    re.IGNORECASE,
)


def extract_text(image_bytes: bytes) -> str:
    """Run OCR on raw image bytes and return the extracted text."""
    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang="eng+rus")


def classify_screenshot(text: str) -> str:
    """Return 'pvp', 'pve', 'loot', or 'unknown' based on OCR text."""
    if _PVP_KEYWORDS.search(text):
        return "pvp"
    if _PVE_KEYWORDS.search(text):
        return "pve"
    if _LOOT_KEYWORDS.search(text):
        return "loot"
    return "unknown"


def extract_isk_amount(text: str) -> float:
    """Try to parse an ISK/credit amount from OCR text (e.g. '1,234,567.89 ISK')."""
    # Look for patterns like 1,234,567 or 1.234.567,89
    matches = re.findall(r"[\d]{1,3}(?:[,.\s][\d]{3})*(?:[.,]\d{1,2})?", text)
    for m in matches:
        clean = re.sub(r"[,.\s]", "", m)
        try:
            value = float(clean)
            if value > 0:
                return value
        except ValueError:
            continue
    return 0.0
