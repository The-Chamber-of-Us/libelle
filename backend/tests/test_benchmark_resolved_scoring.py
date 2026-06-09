import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from resolver.normalize import normalize_key
from benchmark import score_skills_resolved

ALIASES = {
    normalize_key("react"): "react",
    normalize_key("react.js"): "react",
    normalize_key("reactjs"): "react",
    normalize_key("python"): "python",
    normalize_key("python3"): "python",
    normalize_key("chash"): "c#",
    normalize_key("c#"): "c#",
}


def test_reactjs_resolves_to_react():
    result = score_skills_resolved(["React.js"], ["React"], ALIASES)
    assert result["tp_count"] == 1
    assert result["fp_count"] == 0
    assert result["fn_count"] == 0


def test_python3_resolves_to_python():
    result = score_skills_resolved(["python3"], ["Python"], ALIASES)
    assert result["tp_count"] == 1
    assert result["fp_count"] == 0
    assert result["fn_count"] == 0


def test_unresolved_skills_do_not_match():
    result = score_skills_resolved(["database systems"], ["PostgreSQL"], ALIASES)
    assert result["tp_count"] == 0
    assert result["fn_count"] == 1