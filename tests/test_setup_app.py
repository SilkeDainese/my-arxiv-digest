import pytest

from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback for local dev
    import tomli as tomllib

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_setup_app_renders_without_streamlit_exceptions(monkeypatch):
    """Smoke-test the setup wizard with a fake server-side Gemini key."""
    monkeypatch.chdir(ROOT / "setup")
    monkeypatch.syspath_prepend(str(ROOT / "setup"))

    app = AppTest.from_file(str(ROOT / "setup" / "app.py"))
    app.secrets["GEMINI_API_KEY"] = "test-server-key"

    app.run(timeout=10)
    assert len(app.exception) == 0


def test_root_streamlit_theme_matches_setup_theme():
    """Theme config must exist at repo root for Streamlit Cloud."""
    root_theme = ROOT / ".streamlit" / "config.toml"
    setup_theme = ROOT / "setup" / ".streamlit" / "config.toml"

    assert tomllib.loads(root_theme.read_text()) == tomllib.loads(
        setup_theme.read_text()
    )
