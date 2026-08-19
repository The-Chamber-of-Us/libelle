import sys
from pathlib import Path

GENERATOR_DIR = Path(__file__).parent.parent / "benchmarks" / "synthetic" / "generator"
if str(GENERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_DIR))

from schema import (  # noqa: E402
    EducationEntry,
    ExperienceEntry,
    Location,
    Profile,
    ScenarioMeta,
    derive_gold,
    derive_gold_v1,
    derive_gold_v2,
)

from benchmarks.v2_evaluation.validate_v2_goldens import validate_v2_golden  # noqa: E402


def _profile(**overrides) -> Profile:
    defaults = dict(
        case_id="syn_000_known",
        name="Jordan Lee",
        email="jordan.lee@example.com",
        phone="(555) 123-4567",
        location=Location(city="Denver", country="United States", raw="Denver, CO"),
        skills=("Python", "SQL"),
        tools=("Docker",),
        experience=(
            ExperienceEntry(
                title="Software Engineer",
                company="Acme Corp",
                location_raw="Denver, CO",
                dates="Jan 2023-Present",
                bullets=("Shipped a thing.", "Fixed a bug."),
            ),
        ),
        education=(
            EducationEntry(
                degree="B.S. Computer Science",
                institution="State University",
                location_raw="Denver, CO",
                dates="May 2022",
            ),
        ),
        meta=ScenarioMeta(
            case_id="syn_000_known",
            category="known",
            template="known_a",
            seed=42,
            boundary_probes=("ambiguous city",),
        ),
    )
    defaults.update(overrides)
    return Profile(**defaults)


def test_derive_gold_v1_unchanged():
    profile = _profile()
    gold = derive_gold_v1(profile)

    assert gold == {
        "submission_id": "syn_000_known",
        "skills": ["python", "sql", "docker"],
        "location": {"city": "Denver", "country": "United States", "raw": "Denver, CO"},
        "notes": {"ambiguities": ["ambiguous city"]},
    }


def test_derive_gold_defaults_to_v1():
    profile = _profile()
    assert derive_gold(profile) == derive_gold_v1(profile)


def test_derive_gold_v2_top_level_fields():
    profile = _profile()
    gold = derive_gold(profile, version="v2")

    assert gold["resume_id"] == "syn_000_known"
    assert gold["name"] == "Jordan Lee"
    assert gold["email"] == "jordan.lee@example.com"
    assert gold["phone"] == "(555) 123-4567"
    assert gold["location"] == {"city": "Denver", "country": "United States", "raw": "Denver, CO"}
    assert gold["links"] == []
    assert gold["skills"] == ["python", "sql", "docker"]
    assert gold["notes"] == {"ambiguities": ["ambiguous city"]}


def test_derive_gold_v2_sections():
    profile = _profile()
    gold = derive_gold_v2(profile)

    headings = [s["heading"] for s in gold["sections"]]
    assert headings == ["SKILLS", "EXPERIENCE", "EDUCATION"]

    skills_section = gold["sections"][0]
    assert skills_section["items"] == ["Python, SQL, Docker"]

    experience_item = gold["sections"][1]["items"][0]
    assert experience_item["title"] == "Software Engineer, Acme Corp"
    assert experience_item["meta"] == "Jan 2023-Present"
    assert experience_item["subtitle"] == "Denver, CO"
    assert experience_item["bullets"] == ["Shipped a thing.", "Fixed a bug."]

    education_item = gold["sections"][2]["items"][0]
    assert education_item["title"] == "State University"
    assert education_item["meta"] == "May 2022"
    assert education_item["subtitle"] == "B.S. Computer Science"
    assert education_item["bullets"] == []


def test_derive_gold_v2_omits_empty_sections():
    profile = _profile(experience=(), education=())
    gold = derive_gold_v2(profile)

    headings = [s["heading"] for s in gold["sections"]]
    assert headings == ["SKILLS"]


def test_derive_gold_v2_passes_canonical_validator():
    profile = _profile()
    gold = derive_gold_v2(profile)

    issues = validate_v2_golden(gold, fixture_key=profile.case_id, golden_path=Path(f"{profile.case_id}.json"))

    assert issues == []


def test_derive_gold_unsupported_version_raises():
    profile = _profile()
    try:
        derive_gold(profile, version="v3")
    except ValueError as exc:
        assert "v3" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported version")
