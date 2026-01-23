from .schemas import (
    ExtractedProfileV1, 
    ResolvedProfileV1, 
    ResolvedFieldsV1, 
    UnknownsV1,
    ResolverStatsV1
)

def resolve_extracted_profile(extracted: ExtractedProfileV1) -> ResolvedProfileV1:
    """
    TODO: Chechu, this is your mission!
    
    Goal: Transform raw extracted data into the strict ResolvedProfileV1 schema.
    
    Steps:
    1. Load aliases_v1.json.
    2. Normalize and map skills.
    3. Populate the 'ResolvedFieldsV1' object (canonical data).
    4. Populate the 'UnknownsV1' object (unmapped data).
    5. Calculate 'ResolverStatsV1' (coverage %).
    
    Returns:
        A fully populated ResolvedProfileV1 object.
    """
    # Placeholder to make the linter happy until you build it
    raise NotImplementedError("Chechu: Implement the resolution logic here.")
