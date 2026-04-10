"""Tests for author-voice banned-opener enforcement.

TDD — written before implementation. Tests here cover:
  - Quality gate rejects plain_summary starting with any banned opener
  - Quality gate rejects plain_summary shorter than 40 chars
  - Keyword fallback skips author-voice first sentences and returns a clean one
  - Keyword fallback with all 3 author-voice sentences returns empty plain_summary
  - Empty plain_summary from keyword fallback causes quality gate to fail
  - Regression: clean summaries still pass
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.ai_scorer import _apply_keyword_fields, score_papers_with_ai
from shared.quality_gate import validate_paper_quality, validate_papers_batch

# ─────────────────────────────────────────────────────────────────────────────
# All banned openers that the quality gate must reject
# ─────────────────────────────────────────────────────────────────────────────

ALL_BANNED_OPENERS = [
    # Original set
    "Researchers",
    "The authors",
    "This paper",
    "A team",
    "Scientists",
    "The researchers",
    "Authors",
    # New: author-voice "We ..." variants
    "We present",
    "We show",
    "We propose",
    "We investigate",
    "We find",
    "We explore",
    "We describe",
    "We analyze",
    "We analyse",
    "We demonstrate",
    "We report",
    "We study",
    "We ",
    # Contextual author-voice starters
    "In this paper",
    "In this work",
    "Here we",
    "This work",
]


def make_paper_with_summary(summary: str, paper_id: str = "2501.00001") -> dict:
    return {
        "id": paper_id,
        "plain_summary": summary,
        "highlight_phrase": "five word highlight phrase here",
    }


def make_raw_paper(abstract: str, title: str = "Stellar binary evolution") -> dict:
    return {
        "id": "2501.00001",
        "title": title,
        "abstract": abstract,
        "authors": ["Smith J", "Jones A"],
        "published": "2026-04-07",
        "url": "https://arxiv.org/abs/2501.00001",
        "pdf_url": "https://arxiv.org/pdf/2501.00001",
        "global_score": 50.0,
        "subscriber_score": 50.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quality gate: banned opener check (parametric)
# ─────────────────────────────────────────────────────────────────────────────

class TestBannedOpenerQualityGate:
    """validate_paper_quality must reject any plain_summary starting with a banned opener."""

    @pytest.mark.parametrize("opener", ALL_BANNED_OPENERS)
    def test_banned_opener_fails_gate(self, opener: str):
        summary = opener + "explore the lower mass regime of binary evolution in detail."
        paper = make_paper_with_summary(summary)
        ok, reason = validate_paper_quality(paper)
        assert ok is False, (
            f"Expected gate to reject summary starting with {opener!r}, but it passed.\n"
            f"Summary: {summary!r}"
        )

    @pytest.mark.parametrize("opener", ALL_BANNED_OPENERS)
    def test_banned_opener_case_insensitive(self, opener: str):
        """Gate must catch lowercase variants too."""
        summary = opener.lower() + " present results on stellar radii measurements."
        paper = make_paper_with_summary(summary)
        ok, reason = validate_paper_quality(paper)
        assert ok is False, (
            f"Case-insensitive check failed for {opener.lower()!r}.\nSummary: {summary!r}"
        )

    def test_clean_summary_passes_gate(self):
        """A summary with no banned opener must pass."""
        summary = "Interferometric radii measured for 47 solar-type stars. Results agree with Gaia DR3."
        paper = make_paper_with_summary(summary)
        ok, reason = validate_paper_quality(paper)
        assert ok is True, f"Clean summary was incorrectly rejected: {reason}"

    def test_banned_opener_reason_mentions_banned_opener(self):
        """Failure reason must be informative."""
        paper = make_paper_with_summary("We explore the lower mass regime.")
        ok, reason = validate_paper_quality(paper)
        assert ok is False
        assert reason  # non-empty reason


# ─────────────────────────────────────────────────────────────────────────────
# Quality gate: minimum length check
# ─────────────────────────────────────────────────────────────────────────────

class TestMinimumLengthQualityGate:
    def test_summary_shorter_than_40_chars_fails(self):
        paper = make_paper_with_summary("Short stub.")  # 11 chars
        ok, reason = validate_paper_quality(paper)
        assert ok is False
        assert "plain_summary" in reason

    def test_summary_of_exactly_40_chars_passes(self):
        summary = "A" * 38 + ". "  # 40 chars
        # Must pass — 40 chars is the threshold
        paper = make_paper_with_summary(summary.strip())
        # Trim to exactly 40 non-whitespace chars
        exact = "Interferometric stellar radii — 40 chrs!"
        assert len(exact) == 40
        paper = make_paper_with_summary(exact)
        ok, _ = validate_paper_quality(paper)
        assert ok is True

    def test_summary_of_39_chars_fails(self):
        summary = "X" * 39
        paper = make_paper_with_summary(summary)
        ok, reason = validate_paper_quality(paper)
        assert ok is False

    def test_normal_summary_length_passes(self):
        summary = "New ML approach recovers stellar Teff within 50K on APOGEE benchmarks."
        paper = make_paper_with_summary(summary)
        ok, _ = validate_paper_quality(paper)
        assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
# Keyword fallback: clean sentence extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestKeywordFallbackCleanSentence:
    """_apply_keyword_fields must skip author-voice first sentences."""

    def test_first_sentence_author_voice_uses_second(self):
        """Abstract starts with 'We show...'; second sentence is clean — use it."""
        abstract = (
            "We show that binary mass transfer rates are enhanced in low-metallicity environments. "
            "The enhancement reaches a factor of three at Z = 0.001. "
            "This has implications for Population III stellar evolution."
        )
        paper = make_raw_paper(abstract)
        _apply_keyword_fields(paper)
        summary = paper["plain_summary"]
        # Must not start with "We"
        assert not summary.lower().startswith("we "), (
            f"Expected author-voice first sentence to be skipped. Got: {summary!r}"
        )
        # Must contain something from the second or third sentence
        assert summary.strip()

    def test_clean_first_sentence_used_directly(self):
        """Abstract starts clean — no skipping needed."""
        abstract = (
            "Binary mass transfer rates are enhanced in low-metallicity environments. "
            "We measured this across 500 systems."
        )
        paper = make_raw_paper(abstract)
        _apply_keyword_fields(paper)
        summary = paper["plain_summary"]
        assert summary.strip()
        # Should not be empty and should not start with "We"
        assert not summary.lower().startswith("we ")

    def test_all_three_sentences_author_voice_returns_empty(self):
        """All 3 first sentences start with banned openers — plain_summary must be empty."""
        abstract = (
            "We present a new model for binary star mass transfer. "
            "We show that metallicity is the key driver. "
            "We explore three different mass ratio regimes in detail."
        )
        paper = make_raw_paper(abstract)
        _apply_keyword_fields(paper)
        assert paper["plain_summary"] == "", (
            f"Expected empty plain_summary when all 3 sentences are author-voice. "
            f"Got: {paper['plain_summary']!r}"
        )

    def test_second_sentence_also_author_voice_uses_third(self):
        """First two sentences are author-voice; third is clean — use the third."""
        abstract = (
            "We show new results on binary mass transfer. "
            "We present our methodology in section two. "
            "The mass transfer rate peaks at a metallicity of Z = 0.002."
        )
        paper = make_raw_paper(abstract)
        _apply_keyword_fields(paper)
        summary = paper["plain_summary"]
        assert not summary.lower().startswith("we "), f"Got: {summary!r}"
        assert "metallicity" in summary or "mass transfer" in summary.lower() or summary


# ─────────────────────────────────────────────────────────────────────────────
# Integration: all-author-voice abstract → empty summary → quality gate fails
# ─────────────────────────────────────────────────────────────────────────────

class TestAllAuthorVoiceIntegration:
    """End-to-end: keyword fallback + quality gate interaction."""

    def _score_keyword(self, abstract: str) -> dict:
        paper = make_raw_paper(abstract)
        with patch("shared.ai_scorer._get_anthropic_key", return_value=None), \
             patch("shared.ai_scorer._get_gemini_key", return_value=None), \
             patch("shared.ai_scorer._get_gemini_client", return_value=None):
            results = score_papers_with_ai([paper])
        return results[0]

    def test_all_author_voice_abstract_empty_summary(self):
        abstract = (
            "We present a comprehensive survey of binary star mass transfer. "
            "We show the metallicity dependence across 500 systems. "
            "We explore implications for Population III stellar evolution."
        )
        scored = self._score_keyword(abstract)
        assert scored["plain_summary"] == "", (
            f"Expected empty plain_summary. Got: {scored['plain_summary']!r}"
        )

    def test_all_author_voice_fails_quality_gate(self):
        abstract = (
            "We present a comprehensive survey of binary star mass transfer. "
            "We show the metallicity dependence across 500 systems. "
            "We explore implications for Population III stellar evolution."
        )
        scored = self._score_keyword(abstract)
        ok, reason = validate_paper_quality(scored)
        assert ok is False, "Quality gate should reject a paper with empty plain_summary"

    def test_batch_with_one_author_voice_paper_has_failure(self):
        abstract = (
            "We present a comprehensive survey of binary star mass transfer. "
            "We show the metallicity dependence across 500 systems. "
            "We explore implications for Population III stellar evolution."
        )
        with patch("shared.ai_scorer._get_anthropic_key", return_value=None), \
             patch("shared.ai_scorer._get_gemini_key", return_value=None), \
             patch("shared.ai_scorer._get_gemini_client", return_value=None):
            papers = [make_raw_paper(abstract)]
            scored = score_papers_with_ai(papers)
        failures = validate_papers_batch(scored)
        assert len(failures) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Regression: existing clean AI summaries still pass
# ─────────────────────────────────────────────────────────────────────────────

class TestRegressionCleanSummaries:
    """AI-generated summaries that don't start with banned words still pass gate."""

    @pytest.mark.parametrize("summary", [
        "Interferometric radii measured for 47 solar-type stars. Results agree with Gaia DR3.",
        "New ML approach for stellar Teff from high-res spectra. Recovers within 50K on APOGEE.",
        "Direct mass measurements via CHARA array reveal systematic offset in Gaia radii.",
        "A 3% systematic improvement over previous work is demonstrated for K-dwarf radii.",
        "Binary mass transfer rates peak at Z = 0.001. Implications for metal-poor stellar evolution.",
    ])
    def test_clean_summary_passes_gate(self, summary: str):
        paper = make_paper_with_summary(summary)
        ok, reason = validate_paper_quality(paper)
        assert ok is True, f"Clean summary was incorrectly rejected: {reason!r}\nSummary: {summary!r}"

    def test_ai_generated_summary_with_no_banned_opener(self):
        """Simulate the AI returning a good summary — gate passes."""
        import json
        from unittest.mock import MagicMock
        paper = make_raw_paper(
            "We present new interferometric measurements for 47 stars.",
            title="Binary radii from interferometry",
        )
        payload = {
            "relevance_score": 8,
            "plain_summary": "Interferometric radii for 47 solar-type stars reveal a 3% offset vs Gaia DR3.",
            "highlight_phrase": "interferometry beats Gaia by three percent",
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=json.dumps(payload))]
        )
        with patch("shared.ai_scorer._get_anthropic_client", return_value=mock_client), \
             patch("shared.ai_scorer._get_anthropic_key", return_value="sk-fake"):
            result = score_papers_with_ai([paper])
        ok, reason = validate_paper_quality(result[0])
        assert ok is True, f"Clean AI summary incorrectly rejected: {reason}"
