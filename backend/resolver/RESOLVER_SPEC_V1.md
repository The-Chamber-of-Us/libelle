# Libelle Resolver V1 - Implementation Spec

**Status:** Draft
**Owner:** Chechu
**Reviewers:** Kevin, Riya
**Goal:** Map raw extracted resume data (messy strings) to canonical values (clean IDs).

---

## 1. The Mission
The "Resolver" is a **pure function** that takes messy input from the Parser/Extractor and returns clean, structured data for the database.

It is **Pure Logic**:
* It takes **Validated Input** + an **Alias Map Dictionary** (provided by the caller).
* It returns **Validated Output**.
* It must **not** read/write files, call network services, or touch Sheets/Drive/DB.

### Core Responsibilities
1.  **Normalize:** Transform input strings (e.g., "React.js") into strict lookup keys using `normalize_key` (removes spaces/punctuation).
2.  **Resolve:** Map that key to a canonical ID (e.g., `react`) using the provided Alias Map.
    * *Note: Alias Map keys must be normalized keys. Values are canonical IDs.*
3.  **Segregate:**
    * **Resolved:** Skills we recognize (e.g., `python`, `sql`).
    * **Unknowns:** Skills we don't recognize yet. **Store the original raw string here** (not the normalized key).
4.  **Report:** Calculate **Concept Coverage** (unique keys), not raw string coverage.
    * Formula: `coverage = (count of unique input keys that found a match) / (total unique input keys)`
5.  **Determinism: Output ordering must be stable. Preserve "first-seen" order. Do not use list(set(...)) or sorted(set(...)) as they destroy insertion order.**

---

## 2. The Contract (Schemas)
See `backend/resolver/schemas.py` for the strict Pydantic definitions.

* **Input:** `ExtractedProfileV1` (Raw strings from PDF)
* **Output:** `ResolvedProfileV1` (Strictly typed, segregated data)

---

## 3. The Logic Flow (Pseudocode)

```python
from .normalize import normalize_key

def resolve_extracted_profile(extracted, aliases):
    # 1. Setup
    resolved_skills = []
    # We store tuples of (key, raw) for unknowns initially to help dedup later
    unknown_candidates = [] 
    unique_input_keys = set()
    
    # 2. Loop through every raw skill
    for raw_skill in extracted.skills:
        # A. Normalize using the strict key function
        clean_key = normalize_key(raw_skill)
        
        # Guard: If empty, use a sentinel so we can dedup "garbage" cleanly.
        if not clean_key:
            # We use "<empty>" as the key so all empty strings dedup to one entry.
            unknown_candidates.append( ("<empty>", raw_skill) )
            continue
            
        unique_input_keys.add(clean_key)
        
        # B. Lookup in Alias Map
        if clean_key in aliases:
            resolved_skills.append(aliases[clean_key])
        else:
            # Store (key, raw) so we can dedup by key but keep raw text
            unknown_candidates.append( (clean_key, raw_skill) )
            
    # 3. Deduplicate Resolved Skills (Preserve First-Seen Order)
    final_resolved = []
    seen = set()
    for skill_id in resolved_skills:
        if skill_id not in seen:
            seen.add(skill_id)
            final_resolved.append(skill_id)
            
    # 4. Deduplicate Unknowns (Preserve First-Seen Order by KEY)
    # If we see "Next.js" and later "next js", we only keep the first one.
    # If we see 50 empty strings, we only keep the first one.
    final_unknowns = []
    seen_unknown_keys = set()
    for key, raw in unknown_candidates:
        if key not in seen_unknown_keys:
            seen_unknown_keys.add(key)
            final_unknowns.append(raw)
            
    # 5. Calculate Stats
   # Denominator is unique INPUT concepts (keys).
    # Numerator is how many of those keys we recognized.
    # We use set intersection for speed and clarity.
    matched_keys = unique_input_keys.intersection(aliases.keys())
    denominator = len(unique_input_keys)
    coverage = len(matched_keys) / denominator if denominator > 0 else 0.0

    # 6. Handle Location (Pass-through only)
    # v1: set resolved.location.raw = extracted.location_raw 
    # Leave city/state/country = None unless state can be extracted cheaply.
    
    # 7. Return Final Object
    return ResolvedProfileV1(..., stats={"coverage": coverage})
```
## 4. Developer Guide

### How to Start
1.  Check out the `backend/resolver` folder.
2.  Review `normalize.py` -> This is your tool belt.
3.  Review `resolver.py` -> This is where you write the logic.

*Tip: If you use regex in `normalize_key`, compile your patterns at the module scope so they aren't re-compiled on every function call.*

### How to Test (The Loop)
We have built a local runner so you don't need the full backend running.

**Run this command:**
`python -m backend.resolver.debug_runner backend/resolver/tests/fixtures/extracted_profile_001.json`

**Success Criteria:**
* [ ] The script prints "RESOLUTION SUCCESS".
* [ ] `resolved.skills` includes canonical IDs like `react` and `python` (not display labels).
* [ ] The output is deterministic (running it twice produces the exact same JSON).
* [ ] `stats.coverage` matches the manual calculation (100% if all unique normalized input keys exist in the alias map).

---

## 5. Non-Goals (V1)
* **No Fuzzy Matching:** Exact alias lookups only.
* **No Complex Location Resolution:** Pass through `location.raw` only; leave structured country/city fields null for now.
* **No Database Connections:** Everything is in memory.
