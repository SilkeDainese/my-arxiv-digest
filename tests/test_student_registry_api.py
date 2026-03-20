"""
tests/test_student_registry_api.py — Passwordless subscription lifecycle tests.

Covers the relay /api/students endpoint with token-based confirmation flow:
  subscribe request → confirmation email → token confirm → active subscription.
"""

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "relay" / "api" / "students.py"
SPEC = importlib.util.spec_from_file_location("student_registry_api_test", MODULE_PATH)
students_api = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(students_api)


TOKEN_SECRET = "test-token-secret"


def test_passwordless_lifecycle(monkeypatch):
    """Full subscribe → confirm → admin_list → unsubscribe → confirm lifecycle."""
    state = {"students": {}, "pending_tokens": {}}
    saved = {}
    email_calls = []

    def load_registry():
        return copy.deepcopy(state), "sha-1"

    def save_registry(registry, sha, message):
        state.update(copy.deepcopy(registry))
        saved["sha"] = sha
        saved["message"] = message

    monkeypatch.setattr(students_api, "_load_registry", load_registry)
    monkeypatch.setattr(students_api, "_save_registry", save_registry)
    monkeypatch.setattr(students_api, "STUDENT_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(students_api, "STUDENT_TOKEN_SECRET", TOKEN_SECRET)
    monkeypatch.setattr(
        students_api,
        "_send_subscribe_confirmation",
        lambda email, token, package_ids: email_calls.append(("subscribe", email)) or (True, None),
    )
    monkeypatch.setattr(
        students_api,
        "_send_unsubscribe_confirmation",
        lambda email, token: email_calls.append(("unsubscribe", email)) or (True, None),
    )

    # Step 1: Request subscribe
    status, payload = students_api._dispatch({
        "action": "request_subscribe",
        "email": "AU612345@UNI.AU.DK",
        "package_ids": ["exoplanets"],
        "max_papers_per_week": 4,
    })

    assert status == 200
    assert payload["ok"] is True
    assert payload["confirmation_sent"] is True
    assert email_calls == [("subscribe", "au612345@uni.au.dk")]
    # Student NOT yet in registry
    assert "au612345@uni.au.dk" not in state["students"]
    # Pending token stored
    assert "au612345@uni.au.dk:subscribe" in state["pending_tokens"]

    # Step 2: Simulate clicking the confirmation link
    pending_entry = state["pending_tokens"]["au612345@uni.au.dk:subscribe"]
    token = pending_entry["token"]
    page_html, _ = students_api._handle_confirm(token)

    assert "You're subscribed!" in page_html
    assert "au612345@uni.au.dk" in state["students"]
    assert state["students"]["au612345@uni.au.dk"]["active"] is True
    assert state["students"]["au612345@uni.au.dk"]["package_ids"] == ["exoplanets"]
    assert state["students"]["au612345@uni.au.dk"]["max_papers_per_week"] == 4

    # Step 3: Admin list shows active student
    status, payload = students_api._dispatch({
        "action": "admin_list",
        "admin_token": "admin-secret",
    })
    assert status == 200
    assert len(payload["subscriptions"]) == 1
    assert payload["subscriptions"][0]["email"] == "au612345@uni.au.dk"

    # Step 4: Request unsubscribe
    # Reset rate limit for unsubscribe (separate action, shouldn't be limited)
    status, payload = students_api._dispatch({
        "action": "request_unsubscribe",
        "email": "au612345@uni.au.dk",
    })
    assert status == 200
    assert payload["confirmation_sent"] is True
    assert email_calls[-1] == ("unsubscribe", "au612345@uni.au.dk")

    # Step 5: Confirm unsubscribe
    unsub_entry = state["pending_tokens"]["au612345@uni.au.dk:unsubscribe"]
    page_html, _ = students_api._handle_confirm(unsub_entry["token"])

    assert "You've been unsubscribed" in page_html
    assert state["students"]["au612345@uni.au.dk"]["active"] is False

    # Step 6: Admin list (active only) is now empty
    status, payload = students_api._dispatch({
        "action": "admin_list",
        "admin_token": "admin-secret",
    })
    assert status == 200
    assert payload["subscriptions"] == []


def test_manage_page_has_no_password_fields():
    """Passwordless settings page must not have password inputs."""
    page = students_api._manage_page(
        "au612345@uni.au.dk",
        "",
        ["stars", "galaxies"],
        4,
    )

    # Has AU ID input
    assert "612345" in page
    assert "@uni.au.dk" in page
    # Has package checkboxes
    assert "Stars" in page
    assert "Galaxies" in page
    # Has subscribe button
    assert "Subscribe" in page
    # Has confirmation note
    assert "confirmation link" in page.lower() or "confirmation" in page.lower()
    # Has unsubscribe link
    assert "Unsubscribe" in page
    # NO password fields
    assert 'type="password"' not in page
    assert "New password" not in page
    # Has correct initial values
    assert 'const initialPackages = ["stars", "galaxies"]' in page


def test_manage_page_uses_brand_fonts():
    """Settings page uses DM Serif Display for headings and IBM Plex Sans for body."""
    page = students_api._manage_page("", "", [], 6)
    assert "DM Serif Display" in page
    assert "IBM Plex Sans" in page


def test_manage_page_has_stepper():
    """Max papers uses a stepper control, not a plain number input."""
    page = students_api._manage_page("", "", [], 8)
    assert "stepper" in page.lower()
    assert "adjustMax" in page


def test_manage_page_single_column_packages():
    """Package checkboxes are in a single column (flex-direction: column)."""
    page = students_api._manage_page("", "", [], 6)
    assert "flex-direction: column" in page


def test_expired_token_shows_error_page(monkeypatch):
    """Clicking an expired confirmation link shows a helpful error page."""
    monkeypatch.setattr(students_api, "STUDENT_TOKEN_SECRET", TOKEN_SECRET)
    import relay.api._registry as reg
    token = reg.generate_confirmation_token(
        "au612345@uni.au.dk", "subscribe", {}, TOKEN_SECRET, ttl_seconds=0,
    )
    import time
    time.sleep(0.1)

    state = {"students": {}, "pending_tokens": {}}
    monkeypatch.setattr(students_api, "_load_registry", lambda: (copy.deepcopy(state), "sha"))
    monkeypatch.setattr(students_api, "_save_registry", lambda *a: None)

    page_html, _ = students_api._handle_confirm(token)
    assert "expired" in page_html.lower() or "went wrong" in page_html.lower()
    assert "settings" in page_html.lower()


def test_rate_limit_rejects_rapid_requests(monkeypatch):
    """Second subscribe request within 15 min is rejected."""
    state = {"students": {}, "pending_tokens": {}}
    monkeypatch.setattr(students_api, "_load_registry", lambda: (copy.deepcopy(state), "sha"))
    monkeypatch.setattr(students_api, "_save_registry", lambda reg, sha, msg: state.update(copy.deepcopy(reg)))
    monkeypatch.setattr(students_api, "STUDENT_TOKEN_SECRET", TOKEN_SECRET)
    monkeypatch.setattr(students_api, "_send_subscribe_confirmation", lambda *a: (True, None))

    # First request succeeds
    status, _ = students_api._dispatch({
        "action": "request_subscribe",
        "email": "au612345@uni.au.dk",
        "package_ids": ["stars"],
    })
    assert status == 200

    # Second request within 15 min rejected (ValueError → 400)
    with pytest.raises(ValueError, match="[Rr]ecent"):
        students_api._dispatch({
            "action": "request_subscribe",
            "email": "au612345@uni.au.dk",
            "package_ids": ["galaxies"],
        })


# ─────── Email validation tests ──────────────────────────────

class TestNormaliseEmail:
    """normalise_email now validates format."""

    def test_valid_email_is_normalised(self):
        assert students_api.normalise_email("AU612345@UNI.AU.DK") == "au612345@uni.au.dk"

    def test_email_without_at_raises(self):
        with pytest.raises(ValueError, match="Invalid email"):
            students_api.normalise_email("notanemail")

    def test_email_without_domain_tld_raises(self):
        with pytest.raises(ValueError, match="Invalid email"):
            students_api.normalise_email("user@nodot")

    def test_empty_string_returns_empty(self):
        assert students_api.normalise_email("") == ""

    def test_request_subscribe_with_invalid_email_raises(self, monkeypatch):
        monkeypatch.setattr(students_api, "_load_registry", lambda: ({"students": {}, "pending_tokens": {}}, None))
        monkeypatch.setattr(students_api, "_save_registry", lambda *a: None)
        monkeypatch.setattr(students_api, "STUDENT_TOKEN_SECRET", TOKEN_SECRET)
        monkeypatch.setattr(students_api, "_send_subscribe_confirmation", lambda *a: (False, None))
        with pytest.raises(ValueError, match="Invalid email"):
            students_api._dispatch({
                "action": "request_subscribe",
                "email": "notanemail",
                "package_ids": ["stars"],
            })
