import re

WHITESPACE_RE = re.compile(r"\s+")

# Strip wrapping punctuation/noise at token boundaries,
# but preserve identity-critical characters when they are part of the token.
#
# Examples preserved:
#   c++
#   c#
#   .net
#   next.js
#
# Examples cleaned:
#   python -
#   next.js...
#   (react)
#   "node js"
LEADING_PUNCT_RE = re.compile(r"^[^\w\+\#\.]+")
TRAILING_PUNCT_RE = re.compile(r"[^\w\+\#]+$")

# Remove unwanted punctuation inside, but keep meaningful ones
INNER_CLEAN_RE = re.compile(r"[^\w\s\+\#\.\-/]")

def normalize_token(s: str) -> str:
    if not s:
        return ""

    s = s.lower().strip()
    s = LEADING_PUNCT_RE.sub("", s)
    s = TRAILING_PUNCT_RE.sub("", s)
    s = INNER_CLEAN_RE.sub(" ", s)
    s = WHITESPACE_RE.sub(" ", s).strip()

    return s


def normalize_key(s: str) -> str:
    return normalize_token(s).replace(" ", "")
