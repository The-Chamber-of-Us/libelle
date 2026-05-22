"""
tests/test_text_normalization.py

Focused unit tests for backend/utils/text_normalization.py.
Each test targets a specific cleanup operation so failures are easy to diagnose.

Run with:
    pytest tests/test_text_normalization.py -v
"""

import sys
import os

# allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.utils.text_normalization import (
    expand_ligatures,
    normalize_quotes,
    normalize_dashes,
    strip_accents,
    normalize_whitespace,
    normalize_casing,
    normalize_text,
)


# Ligatures

class TestExpandLigatures:
    def test_fl_ligature(self):
        assert expand_ligatures("work\uFB02ows") == "workflows"

    def test_fi_ligature(self):
        assert expand_ligatures("pro\uFB01le") == "profile"

    def test_ff_ligature(self):
        assert expand_ligatures("o\uFB00ice") == "office"

    def test_ffi_ligature(self):
        assert expand_ligatures("e\uFB03cient") == "efficient"

    def test_ffl_ligature(self):
        assert expand_ligatures("a\uFB04uent") == "affluent"

    def test_ae_ligature(self):
        assert expand_ligatures("\u00E6") == "ae"

    def test_oe_ligature(self):
        assert expand_ligatures("\u0153uvre") == "oeuvre"

    def test_uppercase_AE_ligature(self):
        assert expand_ligatures("\u00C6") == "AE"

    def test_no_ligatures_unchanged(self):
        assert expand_ligatures("Python 3.11") == "Python 3.11"

    def test_multiple_ligatures_in_one_string(self):
        # "efficient workflows"
        assert expand_ligatures("e\uFB03cient work\uFB02ows") == "efficient workflows"


# Smart quotes

class TestNormalizeQuotes:
    def test_left_double_quote(self):
        assert normalize_quotes("\u201Chello\u201D") == '"hello"'

    def test_right_single_quote_apostrophe(self):
        assert normalize_quotes("don\u2019t") == "don't"

    def test_left_single_quote(self):
        assert normalize_quotes("\u2018hi\u2019") == "'hi'"

    def test_angle_quotes(self):
        assert normalize_quotes("\u00ABtest\u00BB") == '"test"'

    def test_low_9_double_quote(self):
        assert normalize_quotes("\u201Etest\u201D") == '"test"'

    def test_plain_quotes_unchanged(self):
        assert normalize_quotes('"hello"') == '"hello"'

    def test_mixed_smart_and_plain(self):
        result = normalize_quotes('\u201Csmart\u201D and "plain"')
        assert result == '"smart" and "plain"'


# Dashes

class TestNormalizeDashes:
    def test_em_dash(self):
        assert normalize_dashes("foo\u2014bar") == "foo-bar"

    def test_en_dash(self):
        assert normalize_dashes("2020\u20132021") == "2020-2021"

    def test_horizontal_bar(self):
        assert normalize_dashes("foo\u2015bar") == "foo-bar"

    def test_minus_sign(self):
        assert normalize_dashes("x\u2212y") == "x-y"

    def test_plain_hyphen_unchanged(self):
        assert normalize_dashes("foo-bar") == "foo-bar"

    def test_multiple_dashes(self):
        assert normalize_dashes("a\u2014b\u2013c") == "a-b-c"


# Accented characters (eg café)

class TestStripAccents:
    def test_e_acute(self):
        assert strip_accents("caf\u00E9") == "cafe"

    def test_naive(self):
        assert strip_accents("na\u00EFve") == "naive"

    def test_resume(self):
        assert strip_accents("r\u00E9sum\u00E9") == "resume"

    def test_multiple_accents(self):
        assert strip_accents("\u00E9\u00E0\u00FC") == "eau"

    def test_plain_ascii_unchanged(self):
        assert strip_accents("hello world") == "hello world"

    def test_uppercase_accented(self):
        assert strip_accents("\u00C9l\u00E8ve") == "Eleve"

    def test_non_latin_characters_preserved(self):
        # chinese characters should pass through unchanged
        result = strip_accents("\u4E2D\u6587")
        assert result == "\u4E2D\u6587"


# Whitespace

class TestNormalizeWhitespace:
    def test_multiple_spaces_collapsed(self):
        assert normalize_whitespace("hello   world") == "hello world"

    def test_tabs_collapsed(self):
        assert normalize_whitespace("hello\t\tworld") == "hello world"

    def test_mixed_space_tab(self):
        assert normalize_whitespace("hello \t world") == "hello world"

    def test_leading_trailing_stripped(self):
        assert normalize_whitespace("  hello  ") == "hello"

    def test_newlines_preserved(self):
        result = normalize_whitespace("line one\nline two")
        assert result == "line one\nline two"

    def test_multiline_each_line_cleaned(self):
        result = normalize_whitespace("  foo   bar  \n  baz  ")
        assert result == "foo bar\nbaz"

    def test_single_space_unchanged(self):
        assert normalize_whitespace("hello world") == "hello world"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""

    def test_font_encoding_artifact(self):
        # simulates "S ki ll s" spacing artifact from PDF fonts
        assert normalize_whitespace("S ki ll s") == "S ki ll s"  # spaces collapsed
        assert normalize_whitespace("S  k  i  l  l  s") == "S k i l l s"


# Casing

class TestNormalizeCasing:
    def test_uppercase_lowercased(self):
        assert normalize_casing("PYTHON") == "python"

    def test_mixed_case_lowercased(self):
        assert normalize_casing("TensorFlow") == "tensorflow"

    def test_already_lowercase_unchanged(self):
        assert normalize_casing("python") == "python"

    def test_numbers_and_symbols_unchanged(self):
        assert normalize_casing("Python3.11") == "python3.11"


# Full pipeline  (normalize_text)

class TestNormalizeText:
    def test_ligature_in_pipeline(self):
        assert normalize_text("work\uFB02ows") == "workflows"

    def test_smart_quote_in_pipeline(self):
        assert normalize_text("\u201Chello\u201D") == '"hello"'

    def test_em_dash_in_pipeline(self):
        assert normalize_text("foo\u2014bar") == "foo-bar"

    def test_accent_in_pipeline(self):
        assert normalize_text("caf\u00E9") == "cafe"

    def test_whitespace_in_pipeline(self):
        assert normalize_text("hello   world") == "hello world"

    def test_lowercase_flag_false_by_default(self):
        result = normalize_text("TensorFlow")
        assert result == "TensorFlow"

    def test_lowercase_flag_true(self):
        result = normalize_text("TensorFlow", lowercase=True)
        assert result == "tensorflow"

    def test_combined_everything(self):
        # "Résu\uFB01 \u2014 \u201Cdata\u201D   engineer"
        raw = "R\u00E9su\uFB01 \u2014 \u201Cdata\u201D   engineer"
        result = normalize_text(raw, lowercase=True)
        assert result == 'resufi - "data" engineer'

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_already_clean_string_unchanged(self):
        assert normalize_text("Python 3.11") == "Python 3.11"

    def test_pipeline_order_is_stable(self):
        # Running twice should be idempotent
        raw = "work\uFB02ows \u2014 na\u00EFve"
        once = normalize_text(raw)
        twice = normalize_text(once)
        assert once == twice


# Regression guard: resolver-specific terms must NOT be altered
# (these would be handled by backend/resolver/normalize.py, not here)

class TestResolverBoundary:
    """
    Ensure normalize_text does not canonicalize skill aliases.
    That responsibility belongs to backend/resolver/normalize.py.
    """

    def test_postgres_not_expanded(self):
        # "Postgres" should come out as "Postgres" — not "PostgreSQL"
        assert normalize_text("Postgres") == "Postgres"

    def test_reactjs_not_expanded(self):
        assert normalize_text("React.js") == "React.js"

    def test_tensorflow_not_expanded(self):
        assert normalize_text("TensorFlow") == "TensorFlow"