# backend/resolver/normalize.py

def normalize_token(s: str) -> str:
    """
    TODO (Chechu): Implement normalization logic.

    Goal: Standardize input strings before alias lookup.
    
    Examples (Desired Behavior):
      - "React.js" -> "reactjs" (remove dots, lowercase)
      - "  Python  " -> "python" (strip whitespace)
      - "Node.JS" -> "nodejs"
    """
    # Normalization chain v1 (intended):
    # lowercase -> trim -> strip punctuation -> collapse whitespace
    
    if not s:
        return ""
        
    # Placeholder: Simple lowercase + strip. 
    # You will eventually add regex here (import re first).
    return s.strip().lower()


def normalize_key(s: str) -> str:
    """
    Strict normalization for dictionary keys (e.g. for alias map lookups).
    """
    return normalize_token(s).replace(" ", "")
