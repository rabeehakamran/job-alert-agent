"""
Extracts readable text from a Gmail message payload.

Gmail's payload structure is a recursive tree (parts can contain parts),
and not every sender includes a plain-text part -- some newer platforms
(JobRight, for example) send HTML-only emails. So we walk the tree for
plain text first, and fall back to stripping the HTML part if needed.
"""

import base64

from bs4 import BeautifulSoup


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def _find_part_by_mimetype(payload: dict, mimetype: str) -> str:
    if payload.get("mimeType") == mimetype:
        data = payload.get("body", {}).get("data")
        return _decode(data) if data else ""

    for part in payload.get("parts", []):
        result = _find_part_by_mimetype(part, mimetype)
        if result:
            return result

    return ""


def clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def extract_email_text(payload: dict) -> str:
    """Returns the best available plain-text representation of an email body."""
    plain = _find_part_by_mimetype(payload, "text/plain")
    if plain.strip():
        return plain.strip()

    html = _find_part_by_mimetype(payload, "text/html")
    if html.strip():
        return clean_html_text(html)

    return ""


def get_header(payload: dict, name: str) -> str:
    """Convenience helper to pull a header value (e.g. 'From', 'Subject')."""
    for header in payload.get("headers", []):
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""
