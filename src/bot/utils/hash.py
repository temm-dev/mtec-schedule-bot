import hashlib
import re
import unicodedata
import html

async def generate_hash(schedule: list[list[str]], remove_accents: bool = True) -> str:
    """Generate a SHA-256 hash for the given schedule."""

    def normalize_text(s: str) -> str:
        s = html.unescape(s or "")
        s = unicodedata.normalize("NFKC", s)

        s = re.sub(r'[\u200B-\u200F\uFEFF]', ' ', s)
        if remove_accents:
            s = unicodedata.normalize("NFD", s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            s = unicodedata.normalize("NFC", s)
        s = s.casefold()
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    sep = '\x1f'
    parts = []
    for row in schedule:
        normalized_cells = [normalize_text(cell) for cell in row]
        parts.append(sep.join(normalized_cells))
    canonical = sep.join(parts)

    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
