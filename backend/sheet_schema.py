SUBMISSIONS_HEADERS = [
    "submission_id",
    "created_at",
    "full_name",
    "email",
    "location_raw",
    "timezone",
    "skills_raw",
    "interests",
    "experience_level",
    "availability",
    "motivation",
    "linkedin_url",
    "github_url",
    "consent_given",
    "resume_filename",
    "resume_status",
]

PARSER_RESULTS_HEADERS = [
    "submission_id",
    "parser_run_id",
    "created_at",
    "parser_version",
    "parsed_skills_raw",
    "parsed_location_raw",
    "parser_confidence",
    "resolver_version",
    "aliases_version",
    "resolved_skill_ids",
    "unknown_skills",
    "resolver_coverage",
]

OPS_HEADERS = [
    "submission_id",
    "status",
    "notes",
    "tags",
    "contact_tracking",
    "updated_at",
    "updated_by",
]

ERRORS_HEADERS = [
    "submission_id",
    "created_at",
    "stage",
    "error_code",
    "error_summary",
    "error_details",
]

SHEET_SCHEMA = {
    "submissions": SUBMISSIONS_HEADERS,
    "parser_results": PARSER_RESULTS_HEADERS,
    "ops": OPS_HEADERS,
    "errors": ERRORS_HEADERS,
}