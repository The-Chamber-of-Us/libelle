# backend/resolver/normalize.py
import re

def normalize_token(s: str) -> str:
    """
    Examples (Desired Behavior):
      - "React.js" -> "reactjs" (remove dots, lowercase)
      - "  Python  " -> "python" (strip whitespace)
      - "Node.JS" -> "nodejs"
    """
    # Normalization chain v1 (intended):
    # lowercase -> trim -> strip punctuation -> collapse whitespace
    
    if not s:
        return ""
        
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)   # remove punctuation
    s = re.sub(r"\s+", " ", s)       # collapse whitespace
    
    return s
    

def normalize_key(s: str) -> str:
    """
    Strict normalization for dictionary keys (e.g. for alias map lookups).
    """
    return normalize_token(s).replace(" ", "")
