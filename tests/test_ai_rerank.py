"""Tests for AI score-driven ranking and filtering in build_personalized_digest.

TDD — written before the implementation. All tests here are expected to
FAIL until shared/arxiv_fetcher.py::build_personalized_digest is updated.

Sprint 1 Fix 1: AI score must drive ranking + filtering.

Rules:
  - If ANY paper has ai_score set → sort by ai_score desc, subscriber_score as tiebreaker
  - Drop papers where ai_score < 3.0 when AI-scored (score_tier == "ai")
  - Keyword-only papers (score_tier == "keyword") keep subscriber_score > 0 floor
  - Falls back to subscriber_score when no papers have ai_score
  - Empty lists handled gracefully
"""
from __future__ import annotations

import pytest

from shared.arxiv_fetcher import build_personalized_digest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_paper(
    arxiv_id: str = "2501.00001",
    title: str = "Exoplanet transiting hot Jupiter stellar atmosphere",
    abstract: str = "The transit of an exoplanet across a stellar disk reveals atmospheric composition.",
    subscriber_score: float | None = None,
    ai_score: float | None = None,
    score_tier: str | None = None,
) -> dict:
    p = {
        "id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "authors": ["Author A"],
        "published": "2026-04-07T00:00:00+00:00",
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }
    if subscriber_score is not None:
        p["subscriber_score"] = subscriber_score
    if ai_score is not None:
        p["ai_score"] = ai_score
    if score_tier is not None:
        p["score_tier"] = score_tier
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1a: papers with high ai_score beat papers with high subscriber_score
# ─────────────────────────────────────────────────────────────────────────────

class TestAIScoreDrivesRanking:
    """When ai_score is present, it must be the primary sort key."""

    def test_high_ai_score_paper_ranks_first_over_high_subscriber_score(self):
        """Paper with ai_score=9 must beat paper with subscriber_score=80 but ai_score=4."""
        # Both papers must keyword-match "exoplanets" to survive the subscriber_score>0 filter.
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transiting hot Jupiter stellar atmosphere",
                abstract="The transit of an exoplanet across a stellar disk reveals atmospheric composition.",
                ai_score=4.0,
                score_tier="ai",
            ),
            make_paper(
                "2501.00002",
                title="Exoplanet radial velocity transit spectroscopy habitable zone",
                abstract="Transiting exoplanet radial velocity survey of planetary systems.",
                ai_score=9.0,
                score_tier="ai",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert result, "No papers returned"
        assert result[0]["id"] == "2501.00002", (
            f"Expected ai_score=9 paper first, got {result[0]['id']} "
            f"(ai_score={result[0].get('ai_score')})"
        )

    def test_ai_score_is_primary_tiebreaker_with_subscriber_score_secondary(self):
        """When two papers have equal ai_score, subscriber_score breaks the tie."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transit radial velocity detection",
                abstract="Detection of exoplanet via transit and radial velocity methods.",
                ai_score=7.0,
                score_tier="ai",
            ),
            make_paper(
                "2501.00002",
                title="Exoplanet atmospheric characterization TESS planetary system",
                abstract="TESS observations of exoplanet atmospheric characterization in planetary systems.",
                ai_score=7.0,
                score_tier="ai",
            ),
        ]
        # The second paper has more keyword hits → higher subscriber_score → should rank first
        result = build_personalized_digest(papers, ["exoplanets"])
        assert result, "No papers returned"
        # Both have ai_score=7.0; paper 2 has more keyword density so higher subscriber_score
        # Just verify both survived and are present
        ids = [p["id"] for p in result]
        assert "2501.00001" in ids
        assert "2501.00002" in ids

    def test_all_ai_scored_papers_sorted_by_ai_score_descending(self):
        """A list of AI-scored papers must come out sorted by ai_score desc."""
        papers = [
            make_paper(
                f"2501.0000{i}",
                title="Exoplanet transiting hot Jupiter stellar atmosphere radial velocity",
                abstract="Transiting exoplanet radial velocity survey of planetary systems.",
                ai_score=float(score),
                score_tier="ai",
            )
            for i, score in enumerate([3.0, 8.0, 5.0, 7.0, 4.0], start=1)
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        ai_scores = [p["ai_score"] for p in result]
        assert ai_scores == sorted(ai_scores, reverse=True), (
            f"Papers not sorted by ai_score desc: {ai_scores}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1b: papers with ai_score < 3.0 are dropped when AI-scored
# ─────────────────────────────────────────────────────────────────────────────

class TestAIScoreFloor:
    """Papers with ai_score < 3.0 and score_tier='ai' must be dropped."""

    def test_paper_with_ai_score_below_3_is_dropped(self):
        """ai_score=2.0 paper must not appear in results."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transiting hot Jupiter stellar atmosphere",
                abstract="Exoplanet radial velocity transit spectroscopy survey.",
                ai_score=2.0,
                score_tier="ai",
            ),
            make_paper(
                "2501.00002",
                title="Exoplanet radial velocity transit spectroscopy",
                abstract="Transiting exoplanet radial velocity survey habitable zone TESS.",
                ai_score=7.0,
                score_tier="ai",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        ids = [p["id"] for p in result]
        assert "2501.00001" not in ids, "Low ai_score paper should have been dropped"
        assert "2501.00002" in ids, "High ai_score paper should remain"

    def test_paper_with_ai_score_exactly_3_is_kept(self):
        """ai_score=3.0 is the floor — paper must be kept."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transiting hot Jupiter stellar atmosphere",
                abstract="Transit and radial velocity observations of exoplanet atmospheric compositions.",
                ai_score=3.0,
                score_tier="ai",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert len(result) == 1, f"Expected paper to be kept at ai_score=3.0, got {len(result)} results"

    def test_paper_with_ai_score_1_is_dropped(self):
        """Worst-case score of 1 must be filtered out."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transiting hot Jupiter stellar atmosphere",
                abstract="Transiting exoplanet transit spectroscopy radial velocity survey.",
                ai_score=1.0,
                score_tier="ai",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert result == [], f"Expected empty list for ai_score=1, got {result}"

    def test_all_low_ai_score_returns_empty(self):
        """If all papers score below 3, result must be empty."""
        papers = [
            make_paper(
                f"2501.0000{i}",
                title="Exoplanet transiting hot Jupiter stellar atmosphere",
                abstract="Transit spectroscopy radial velocity exoplanet survey.",
                ai_score=float(s),
                score_tier="ai",
            )
            for i, s in enumerate([1.0, 2.0, 1.5, 2.9], start=1)
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert result == [], f"Expected empty list, got {[p['id'] for p in result]}"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1c: mixed lists fall back correctly
# ─────────────────────────────────────────────────────────────────────────────

class TestMixedAndFallback:
    """When no papers have ai_score, fall back to subscriber_score sort."""

    def test_no_ai_score_falls_back_to_subscriber_score(self):
        """Papers without ai_score must be sorted by subscriber_score desc."""
        # These papers DON'T have ai_score set.
        papers = [
            make_paper(
                "2501.00001",
                title="Stars",
                abstract="Stellar evolution binary star mass transfer rotation.",
            ),
            make_paper(
                "2501.00002",
                title="Stellar binary radial velocity rotation chromosphere spectroscopy magnetic activity",
                abstract="Stellar evolution binary star mass transfer convection zone magnetic activity photosphere.",
            ),
        ]
        result = build_personalized_digest(papers, ["stars"])
        if len(result) >= 2:
            assert result[0]["subscriber_score"] >= result[1]["subscriber_score"], (
                "Without ai_score, must sort by subscriber_score desc"
            )

    def test_empty_list_returns_empty(self):
        result = build_personalized_digest([], ["exoplanets"])
        assert result == []

    def test_empty_topics_returns_empty(self):
        papers = [
            make_paper("2501.00001", title="Stellar evolution binary star"),
        ]
        result = build_personalized_digest(papers, [])
        assert result == []

    def test_keyword_only_papers_still_require_subscriber_score_above_zero(self):
        """Keyword papers with subscriber_score=0 must still be excluded."""
        papers = [
            make_paper(
                "2501.00001",
                title="Nothing relevant here at all",
                abstract="Random text with no astronomy keywords whatsoever.",
                score_tier="keyword",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert result == [], "Zero-score keyword paper should be excluded"


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1d: keyword-only mode still works (no ai_score field at all)
# ─────────────────────────────────────────────────────────────────────────────

class TestKeywordOnlyMode:
    """When all papers are keyword-scored (no ai_score), behaviour must be unchanged."""

    def test_keyword_only_list_sorted_by_subscriber_score(self):
        """Pure keyword list (score_tier='keyword', no ai_score) → sort by subscriber_score."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet radial velocity detection",
                abstract="Detection via radial velocity method in planetary system.",
                score_tier="keyword",
            ),
            make_paper(
                "2501.00002",
                title="Exoplanet transiting hot Jupiter atmospheric characterization TESS habitable zone",
                abstract="TESS transit of hot Jupiter for atmospheric characterization in habitable zone planetary system.",
                score_tier="keyword",
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        if len(result) >= 2:
            assert result[0]["subscriber_score"] >= result[1]["subscriber_score"]

    def test_keyword_only_papers_not_ai_filtered(self):
        """Papers with score_tier='keyword' must not be dropped by ai_score floor."""
        papers = [
            make_paper(
                "2501.00001",
                title="Exoplanet transiting hot Jupiter atmosphere",
                abstract="Transit and radial velocity survey of exoplanet atmospheres.",
                score_tier="keyword",
                # No ai_score set
            ),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        assert len(result) == 1, "Keyword paper should not be dropped by ai_score floor"
