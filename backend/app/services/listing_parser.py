"""
Turns a pasted e-commerce listing into plain text for the rule engine.

Handles copied page HTML without pulling in a parser dependency: strips script and
style blocks, converts block-level tags to newlines, unescapes entities, and
collapses the whitespace soup that marketplace markup produces.
"""

import html
import re
from typing import List

_SCRIPT_STYLE = re.compile(r"<(script|style|noscript|svg)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK_TAGS = re.compile(
    r"</?(p|div|br|li|tr|td|th|h[1-6]|section|article|ul|ol|table|span|dt|dd)\b[^>]*>",
    re.IGNORECASE,
)
_ANY_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")

#: Marketplace chrome that carries no statutory declaration. Dropping it stops the
#: engine reading navigation text as label content.
_NOISE_LINES = {
    "add to cart", "buy now", "wishlist", "share", "compare", "sign in", "login",
    "free delivery", "returns policy", "add to wish list", "see all details",
    "back to results", "report incorrect product information", "have a question?",
}


def html_to_text(markup: str) -> str:
    if not markup:
        return ""
    text = _SCRIPT_STYLE.sub(" ", markup)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text)
    text = text.replace(" ", " ")

    lines: List[str] = []
    for raw in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if not line:
            continue
        if line.lower() in _NOISE_LINES:
            continue
        lines.append(line)

    return _BLANK_RUN.sub("\n\n", "\n".join(lines)).strip()


def parse_listing(listing_text: str = "", listing_html: str = "") -> str:
    """
    Returns the text to audit. Pasted plain text wins when both are supplied - it is
    what the officer actually chose to submit.
    """
    if listing_text and listing_text.strip():
        return listing_text.strip()
    return html_to_text(listing_html)
