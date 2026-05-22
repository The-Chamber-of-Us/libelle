""" 
Generic low-level text cleanup: Unicode ligatures, smart quotes, em/en dashes,
accented characters, repeated whitespace, and casing normalization.
 
Scope boundary:
This module owns cleanup only.
Resolver-specific canonical/alias normalization (e.g. "Postgres" -> "PostgreSQL",
"React.js" -> canonical alias) lives in backend/resolver/normalize.py and must
NOT be combined with the responsibilities here.
"""
 
import re
import unicodedata
 
# Ligature expansion table
# Covers the most common Unicode ligatures that appear in PDF-extracted text
_LIGATURE_MAP: dict[str, str] = {
    "\uFB00": "ff",   # ﬀ
    "\uFB01": "fi",   # ﬁ
    "\uFB02": "fl",   # ﬂ
    "\uFB03": "ffi",  # ﬃ
    "\uFB04": "ffl",  # ﬄ
    "\uFB05": "st",   # ﬅ
    "\uFB06": "st",   # ﬆ
    "\u00E6": "ae",   # æ
    "\u0153": "oe",   # œ
    "\u00C6": "AE",   # Æ
    "\u0152": "OE",   # Œ
}
 
_LIGATURE_RE = re.compile("|".join(re.escape(k) for k in _LIGATURE_MAP))
 
# Smart/curly quote normalization
_QUOTE_MAP: dict[str, str] = {
    "\u2018": "'",   # left single quotation mark
    "\u2019": "'",   # right single quotation mark  (also apostrophe replacement)
    "\u201A": "'",   # single low-9 quotation mark
    "\u201B": "'",   # single high-reversed-9 quotation mark
    "\u201C": '"',   # left double quotation mark
    "\u201D": '"',   # right double quotation mark
    "\u201E": '"',   # double low-9 quotation mark
    "\u201F": '"',   # double high-reversed-9 quotation mark
    "\u2039": "'",   # single left-pointing angle quotation mark
    "\u203A": "'",   # single right-pointing angle quotation mark
    "\u00AB": '"',   # left-pointing double angle quotation mark
    "\u00BB": '"',   # right-pointing double angle quotation mark
}
 
_QUOTE_RE = re.compile("|".join(re.escape(k) for k in _QUOTE_MAP))
 
# Dash normalization  (em dash, en dash, horizontal bar -> hyphen-minus)
_DASH_MAP: dict[str, str] = {
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u2015": "-",   # horizontal bar
    "\u2212": "-",   # minus sign
    "\uFE58": "-",   # small em dash
    "\uFE63": "-",   # small hyphen-minus
    "\uFF0D": "-",   # fullwidth hyphen-minus
}
 
_DASH_RE = re.compile("|".join(re.escape(k) for k in _DASH_MAP))

# Whitespace normalization
# Collapses runs of spaces/tabs; strips leading/trailing whitespace per line
# Does NOT collapse newlines (callers that want single-line output should do that themselves)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
 
 
def expand_ligatures(text: str) -> str:
    """Replace Unicode ligatures with their ASCII equivalents."""
    return _LIGATURE_RE.sub(lambda m: _LIGATURE_MAP[m.group()], text)
 
 
def normalize_quotes(text: str) -> str:
    """Replace curly/smart quotes with straight ASCII equivalents."""
    return _QUOTE_RE.sub(lambda m: _QUOTE_MAP[m.group()], text)
 
 
def normalize_dashes(text: str) -> str:
    """Replace em/en dashes and similar Unicode dashes with a hyphen-minus."""
    return _DASH_RE.sub(lambda m: _DASH_MAP[m.group()], text)
 
 
def strip_accents(text: str) -> str:
    """
    Decompose accented characters and drop the combining accent marks,
    leaving the base ASCII letter.
 
    e.g. "café" -> "cafe", "naïve" -> "naive"
 
    Characters that do not decompose to an ASCII base (e.g. Chinese,
    Arabic) are left unchanged.
    """
    # NFD decomposes é -> e + combining acute accent
    decomposed = unicodedata.normalize("NFD", text)
    # Keep only characters that are not combining marks
    return "".join(
        ch for ch in decomposed
        if unicodedata.category(ch) != "Mn"
    )
 
 
def normalize_whitespace(text: str) -> str:
    """
    Collapse runs of spaces and tabs to a single space.
    Strips leading/trailing whitespace from each line.
    """
    lines = text.split("\n")
    cleaned = [_MULTI_SPACE_RE.sub(" ", line).strip() for line in lines]
    return "\n".join(cleaned)
 
 
def normalize_casing(text: str) -> str:
    """
    Lowercase the text for comparison purposes.
 
    This is intentionally a separate step so callers that need to
    preserve display casing can skip it.
    """
    return text.lower()
 
 
def normalize_text(text: str, *, lowercase: bool = False) -> str:
    """
    Apply the full generic cleanup pipeline in a consistent order:
 
        1. Expand ligatures
        2. Normalize smart quotes
        3. Normalize dashes
        4. Strip accents
        5. Normalize whitespace
        6. Lowercase  (only if lowercase=True)
 
    Parameters
    ----------
    text:
        Raw input string, typically from PDF extraction or benchmark data.
    lowercase:
        If True, the result is lowercased.  Pass True when the output is
        used for comparison/matching; leave False when preserving display
        casing matters (e.g. writing back to a structured JSON field).
 
    Returns
    -------
    Cleaned string.
    """
    text = unicodedata.normalize("NFKC", text)
    text = expand_ligatures(text)
    text = normalize_quotes(text)
    text = normalize_dashes(text)
    text = strip_accents(text)
    text = normalize_whitespace(text)
    if lowercase:
        text = normalize_casing(text)
    return text