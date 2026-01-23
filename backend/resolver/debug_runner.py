import json
import sys
from pathlib import Path

# NOTE: Run this as a module from the root:
# python -m backend.resolver.debug_runner backend/resolver/tests/fixtures/extracted_profile_001.json

from .schemas import ExtractedProfileV1
from .resolver import resolve_extracted_profile

# Define path to the brain (relative to this script)
ALIASES_PATH = Path(__file__).parent / "knowledge" / "aliases_v1.json"

def main():
    # 1. Check Arguments
    if len(sys.argv) != 2:
        print("Usage: python -m backend.resolver.debug_runner <path_to_extracted.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # 2. Load the "Brain" (Aliases)
    print(f"Loading knowledge from {ALIASES_PATH.name}...")
    try:
        with open(ALIASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Handle if the JSON is wrapped in {"aliases": ...} or is flat
            aliases_map = data.get("aliases", data)
    except Exception as e:
        print(f"CRITICAL: Could not load aliases! {e}")
        sys.exit(1)

    # 3. Load the Input Data
    print(f"Loading input {input_path.name}...")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"Error reading input JSON: {e}")
        sys.exit(1)

    # 4. Run the Machine
    try:
        # Validate Input against strict Contract
        extracted = ExtractedProfileV1(**payload)

        # EXECUTE: Pass the brain + input to the pure function
        resolved = resolve_extracted_profile(
            extracted,
            aliases=aliases_map,
            resolver_version="v1-debug",
            aliases_version="v1-local"
        )

        # 5. Print Success
        print("\n--- RESOLUTION SUCCESS ---")
        if hasattr(resolved, "model_dump_json"):
            print(resolved.model_dump_json(indent=2))
        else:
            print(resolved.json(indent=2))

    except NotImplementedError:
        print("\n⚠️  Resolver logic not implemented yet.")
        print(f"To test, fix resolver.py and run:")
        print(f"python -m backend.resolver.debug_runner {sys.argv[1]}")
    except Exception as e:
        print(f"\n❌ CRASH: {e}")

if __name__ == "__main__":
    main()
