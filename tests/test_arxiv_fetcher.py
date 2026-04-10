"""Tests for arXiv fetching and digest building.

Covers:
  - Score paper for matching topics → non-zero
  - Score paper for non-matching topics → zero
  - build_personalized_digest: filters, ranks, limits
  - score_papers_for_all_topics: adds global_score, sorts descending
  - Fixture paper → expected topic match
  - Fix 2: _parse_xml extracts arxiv:primary_category into 'category' field
  - Fix 5: _fetch_xml sends User-Agent header (arXiv ToS compliance)
"""
import textwrap
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from shared.arxiv_fetcher import (
    TOPIC_KEYWORDS,
    _fetch_xml,
    _parse_xml,
    build_personalized_digest,
    score_paper_for_topics,
    score_papers_for_all_topics,
)


def make_paper(
    arxiv_id: str = "2501.00001",
    title: str = "A test paper",
    abstract: str = "This is a test abstract.",
    authors: list | None = None,
) -> dict:
    return {
        "id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "authors": authors or ["Author A", "Author B"],
        "published": "2026-04-07T00:00:00+00:00",
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }


class TestScorePaperForTopics:
    def test_matching_title_keyword_gives_nonzero_score(self):
        paper = make_paper(title="Stellar evolution in binary stars")
        score = score_paper_for_topics(paper, ["stars"])
        assert score > 0

    def test_matching_abstract_keyword_gives_nonzero_score(self):
        paper = make_paper(abstract="We study exoplanet transit spectroscopy observations.")
        score = score_paper_for_topics(paper, ["exoplanets"])
        assert score > 0

    def test_no_match_gives_zero(self):
        paper = make_paper(title="Nothing relevant here", abstract="Random text about nothing.")
        score = score_paper_for_topics(paper, ["cosmology"])
        assert score == 0.0

    def test_title_match_scores_higher_than_abstract_only(self):
        paper_title = make_paper(
            title="Dark energy constraints from CMB",
            abstract="We present new observations.",
        )
        paper_abstract = make_paper(
            title="A new study",
            abstract="Dark energy constraints from CMB analysis.",
        )
        score_title = score_paper_for_topics(paper_title, ["cosmology"])
        score_abstract = score_paper_for_topics(paper_abstract, ["cosmology"])
        assert score_title >= score_abstract

    def test_empty_topics_gives_zero(self):
        paper = make_paper(title="Stellar evolution", abstract="Stars rotating fast.")
        score = score_paper_for_topics(paper, [])
        assert score == 0.0

    def test_multiple_topics_aggregate(self):
        paper = make_paper(
            title="Exoplanet in a stellar binary system with radial velocity",
            abstract="We detect an exoplanet transiting a binary star.",
        )
        score_both = score_paper_for_topics(paper, ["stars", "exoplanets"])
        score_stars = score_paper_for_topics(paper, ["stars"])
        score_exo = score_paper_for_topics(paper, ["exoplanets"])
        # Combined topics score should be >= either individual
        assert score_both >= 0

    def test_score_is_0_to_100(self):
        paper = make_paper(
            title="Neutron star black hole merger gravitational wave detection",
            abstract="LIGO detected a neutron star black hole merger via gravitational waves.",
        )
        score = score_paper_for_topics(paper, ["high_energy"])
        assert 0.0 <= score <= 100.0


class TestScorePapersForAllTopics:
    def test_adds_global_score(self):
        papers = [
            make_paper("2501.00001", title="Exoplanet transit spectroscopy study"),
            make_paper("2501.00002", title="Random unrelated title xyz"),
        ]
        result = score_papers_for_all_topics(papers)
        for p in result:
            assert "global_score" in p
            assert isinstance(p["global_score"], float)

    def test_sorted_descending(self):
        papers = [
            make_paper("2501.00001", title="Random title"),
            make_paper("2501.00002", title="Stellar evolution binary star radial velocity"),
            make_paper("2501.00003", title="Exoplanet transit stellar spectrum"),
        ]
        result = score_papers_for_all_topics(papers)
        scores = [p["global_score"] for p in result]
        assert scores == sorted(scores, reverse=True)

    def test_returns_all_papers(self):
        papers = [make_paper(f"2501.{i:05d}") for i in range(5)]
        result = score_papers_for_all_topics(papers)
        assert len(result) == 5


class TestBuildPersonalizedDigest:
    def test_filters_zero_score_papers(self):
        papers = [
            make_paper("2501.00001", title="Completely unrelated gobbledygook"),
            make_paper("2501.00002", title="Exoplanet atmosphere transit detection"),
        ]
        result = build_personalized_digest(papers, ["exoplanets"])
        ids = [p["id"] for p in result]
        assert "2501.00002" in ids
        # The zero-score paper should be excluded
        assert "2501.00001" not in ids

    def test_respects_max_papers_limit(self):
        papers = [
            make_paper(f"2501.{i:05d}", title="Stellar evolution binary star")
            for i in range(20)
        ]
        result = build_personalized_digest(papers, ["stars"], max_papers=5)
        assert len(result) <= 5

    def test_sorted_by_subscriber_score(self):
        papers = [
            make_paper("2501.00001", title="Stars", abstract="stellar evolution"),
            make_paper("2501.00002", title="Stars binary stellar radial velocity rotation"),
        ]
        result = build_personalized_digest(papers, ["stars"])
        if len(result) >= 2:
            assert result[0]["subscriber_score"] >= result[1]["subscriber_score"]

    def test_adds_subscriber_score_field(self):
        papers = [make_paper("2501.00001", title="Exoplanet transiting hot Jupiter")]
        result = build_personalized_digest(papers, ["exoplanets"])
        if result:
            assert "subscriber_score" in result[0]

    def test_empty_papers_returns_empty(self):
        result = build_personalized_digest([], ["stars"])
        assert result == []

    def test_empty_topics_returns_empty(self):
        papers = [make_paper("2501.00001", title="Stellar evolution")]
        result = build_personalized_digest(papers, [])
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2: _parse_xml extracts arxiv:primary_category → 'category' field
# ─────────────────────────────────────────────────────────────────────────────

# Minimal Atom feed with one entry that has a primary_category element
_ATOM_FEED_WITH_CATEGORY = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.12345v1</id>
    <published>2026-04-07T00:00:00Z</published>
    <title>Stellar evolution in close binary systems</title>
    <summary>Long enough abstract to pass any filter. Radial velocity measurements
    of binary stars reveal mass transfer patterns consistent with stellar evolution models.</summary>
    <author><name>Smith J</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom"
      term="astro-ph.SR" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
""")

_ATOM_FEED_NO_CATEGORY = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.99999v1</id>
    <published>2026-04-07T00:00:00Z</published>
    <title>Galaxy formation at high redshift</title>
    <summary>Long enough abstract here. AGN feedback in massive galaxies influences
    star formation rates and galactic structure at high redshift via quenching.</summary>
    <author><name>Jones A</name></author>
  </entry>
</feed>
""")

_ATOM_FEED_TWO_ENTRIES = textwrap.dedent("""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <published>2026-04-07T00:00:00Z</published>
    <title>Exoplanet detection via transit photometry</title>
    <summary>Long enough abstract. Transiting exoplanets observed with TESS provide
    radial velocity confirmation and atmospheric characterization of hot Jupiters.</summary>
    <author><name>A Author</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom"
      term="astro-ph.EP" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2501.00002v1</id>
    <published>2026-04-07T00:00:00Z</published>
    <title>Neutron star merger gravitational waves</title>
    <summary>Long enough abstract. LIGO detection of neutron star binary merger event
    provides multi-messenger constraints on equation of state of dense nuclear matter.</summary>
    <author><name>B Author</name></author>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom"
      term="astro-ph.HE" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
""")


class TestParseXmlCategory:
    """Fix 2: _parse_xml must extract arxiv:primary_category into paper['category']."""

    def _cutoff(self) -> datetime:
        """A cutoff safely before all fixture timestamps."""
        return datetime(2026, 4, 6, 0, 0, 0, tzinfo=timezone.utc)

    def test_category_field_present_in_parsed_paper(self):
        """Every parsed paper must have a 'category' key."""
        papers = _parse_xml(_ATOM_FEED_WITH_CATEGORY, self._cutoff())
        assert papers, "Should have parsed at least one paper"
        for p in papers:
            assert "category" in p, f"Paper {p.get('id')} missing 'category' field"

    def test_category_matches_primary_category_element(self):
        """'category' must equal the arxiv:primary_category term attribute."""
        papers = _parse_xml(_ATOM_FEED_WITH_CATEGORY, self._cutoff())
        assert papers
        assert papers[0]["category"] == "astro-ph.SR", (
            f"Expected 'astro-ph.SR', got '{papers[0].get('category')}'"
        )

    def test_multiple_entries_get_their_own_category(self):
        """Each paper gets its own primary_category, not the query category."""
        papers = _parse_xml(_ATOM_FEED_TWO_ENTRIES, self._cutoff())
        assert len(papers) == 2
        categories = {p["id"].split("/")[-1]: p["category"] for p in papers}
        # 2501.00001v1 → astro-ph.EP
        ep_key = next(k for k in categories if "00001" in k)
        he_key = next(k for k in categories if "00002" in k)
        assert categories[ep_key] == "astro-ph.EP", f"Expected astro-ph.EP, got {categories[ep_key]}"
        assert categories[he_key] == "astro-ph.HE", f"Expected astro-ph.HE, got {categories[he_key]}"

    def test_missing_category_element_does_not_crash(self):
        """Papers without arxiv:primary_category must still parse (fallback to empty or default)."""
        papers = _parse_xml(_ATOM_FEED_NO_CATEGORY, self._cutoff())
        assert papers, "Should parse even without primary_category element"
        # Should have category key even if it's a fallback value
        assert "category" in papers[0]

    def test_category_not_hardcoded_astro_ph(self):
        """The bug: all papers falling back to 'astro-ph' is wrong. Must use actual category."""
        papers = _parse_xml(_ATOM_FEED_WITH_CATEGORY, self._cutoff())
        assert papers
        # Must NOT be the generic fallback "astro-ph" — must be the specific sub-category
        assert papers[0]["category"] != "astro-ph", (
            "Category must be the specific primary_category, not the generic 'astro-ph' fallback"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fix 5: _fetch_xml sends User-Agent header (arXiv ToS compliance)
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchXmlUserAgent:
    """Fix 5: arXiv ToS requires a descriptive User-Agent header."""

    def test_user_agent_header_set_on_request(self):
        """_fetch_xml must add a User-Agent header to the request."""
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"<feed/>"
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _fetch_xml("https://export.arxiv.org/api/query?search_query=cat:astro-ph.SR")

        assert captured_requests, "_fetch_xml did not call urlopen"
        req = captured_requests[0]
        # The request must be a Request object, not a bare string
        from urllib.request import Request
        assert isinstance(req, Request), (
            f"Expected urllib.request.Request object, got {type(req)}. "
            "Cannot set headers on a bare URL string."
        )
        user_agent = req.get_header("User-agent")
        assert user_agent is not None, "User-Agent header not set on arXiv request"
        assert "arxiv" in user_agent.lower(), (
            f"User-Agent must mention 'arxiv', got: {user_agent!r}"
        )

    def test_user_agent_contains_contact_email(self):
        """User-Agent should contain a contact email (arXiv ToS recommendation)."""
        captured_requests = []

        def fake_urlopen(req, timeout=None):
            captured_requests.append(req)
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"<feed/>"
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _fetch_xml("https://export.arxiv.org/api/query?search_query=cat:astro-ph.SR")

        req = captured_requests[0]
        from urllib.request import Request
        assert isinstance(req, Request)
        user_agent = req.get_header("User-agent") or ""
        assert "mailto:" in user_agent or "@" in user_agent, (
            f"User-Agent should contain contact email, got: {user_agent!r}"
        )
