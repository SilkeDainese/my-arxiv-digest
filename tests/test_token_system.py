"""
tests/test_token_system.py — Token generation, validation, and rate limiting.

Covers the HMAC-signed confirmation token system that replaces passwords
for all state-changing student subscription actions.
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

import relay.api._registry as registry


SECRET = "test-secret-key-for-tokens"


class TestTokenGeneration:
    """generate_confirmation_token returns a URL-safe signed string."""

    def test_returns_url_safe_string(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {"package_ids": ["stars"]}, SECRET,
        )
        assert isinstance(token, str)
        assert len(token) > 0
        # URL-safe: no +, /, or = padding issues that break query strings
        assert " " not in token

    def test_token_contains_action_and_email(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {"package_ids": ["stars"]}, SECRET,
        )
        data = registry.validate_confirmation_token(token, SECRET)
        assert data["email"] == "au612345@uni.au.dk"
        assert data["action"] == "subscribe"
        assert data["payload"]["package_ids"] == ["stars"]

    def test_token_has_expiry(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        data = registry.validate_confirmation_token(token, SECRET)
        assert "expires_at" in data
        # Default expiry should be in the future
        assert data["expires_at"] > time.time()


class TestTokenValidation:
    """validate_confirmation_token verifies HMAC and expiry."""

    def test_valid_token_passes(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {"max_papers": 6}, SECRET,
        )
        data = registry.validate_confirmation_token(token, SECRET)
        assert data["email"] == "au612345@uni.au.dk"
        assert data["action"] == "subscribe"

    def test_expired_token_rejected(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET, ttl_seconds=0,
        )
        # Token created with 0 TTL is already expired
        time.sleep(0.1)
        with pytest.raises(ValueError, match="expired"):
            registry.validate_confirmation_token(token, SECRET)

    def test_tampered_token_rejected(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        # Flip a character in the token
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            registry.validate_confirmation_token(tampered, SECRET)

    def test_wrong_secret_rejected(self):
        token = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            registry.validate_confirmation_token(token, "wrong-secret")

    def test_garbage_token_rejected(self):
        with pytest.raises(ValueError):
            registry.validate_confirmation_token("not-a-valid-token", SECRET)


class TestTokenRateLimit:
    """Rate limiting: second request within 15 min rejected."""

    def test_second_request_within_15_min_rejected(self):
        pending = {}
        # First request succeeds
        token1 = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        registry.store_pending_token(pending, "au612345@uni.au.dk", "subscribe", token1)

        # Second request within 15 min is rejected
        with pytest.raises(ValueError, match="[Rr]ecent.*confirmation"):
            registry.check_rate_limit(pending, "au612345@uni.au.dk", "subscribe")

    def test_request_after_15_min_allowed(self):
        pending = {}
        token1 = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        registry.store_pending_token(pending, "au612345@uni.au.dk", "subscribe", token1)

        # Simulate 16 minutes passing
        key = "au612345@uni.au.dk:subscribe"
        pending[key]["created_at"] = time.time() - 16 * 60

        # Now should not raise
        registry.check_rate_limit(pending, "au612345@uni.au.dk", "subscribe")

    def test_different_action_not_rate_limited(self):
        pending = {}
        token1 = registry.generate_confirmation_token(
            "au612345@uni.au.dk", "subscribe", {}, SECRET,
        )
        registry.store_pending_token(pending, "au612345@uni.au.dk", "subscribe", token1)

        # Different action should not be rate limited
        registry.check_rate_limit(pending, "au612345@uni.au.dk", "unsubscribe")


class TestBuildStudentRecordPasswordless:
    """build_student_record no longer requires or stores password fields."""

    def test_no_password_fields_in_new_record(self):
        record = registry.build_student_record(
            email="au612345@uni.au.dk",
            package_ids=["stars", "galaxies"],
            max_papers_per_week=6,
        )
        assert record["email"] == "au612345@uni.au.dk"
        assert record["package_ids"] == ["stars", "galaxies"]
        assert record["max_papers_per_week"] == 6
        assert record["active"] is True
        assert "password_salt" not in record
        assert "password_hash" not in record

    def test_old_records_with_password_fields_load_gracefully(self):
        """Old records with password fields are loaded without error."""
        old_record = {
            "email": "au612345@uni.au.dk",
            "package_ids": ["stars"],
            "max_papers_per_week": 6,
            "active": True,
            "password_salt": "aabb",
            "password_hash": "scrypt$n=65536,r=8,p=1$deadbeef",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        public = registry.public_record(old_record)
        assert public["email"] == "au612345@uni.au.dk"
        assert "password_salt" not in public
        assert "password_hash" not in public

    def test_update_existing_preserves_created_at(self):
        record = registry.build_student_record(
            email="au612345@uni.au.dk",
            package_ids=["stars"],
            max_papers_per_week=6,
            existing={
                "email": "au612345@uni.au.dk",
                "package_ids": ["galaxies"],
                "max_papers_per_week": 4,
                "active": True,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        assert record["created_at"] == "2026-01-01T00:00:00+00:00"
        assert record["package_ids"] == ["stars"]


class TestTokenCleanup:
    """Expired tokens are cleaned up."""

    def test_cleanup_removes_expired_tokens(self):
        pending = {
            "old@uni.au.dk:subscribe": {
                "token": "old-token",
                "created_at": time.time() - 7200,  # 2 hours ago
                "expires_at": time.time() - 3600,   # expired 1 hour ago
            },
            "fresh@uni.au.dk:subscribe": {
                "token": "fresh-token",
                "created_at": time.time(),
                "expires_at": time.time() + 3600,
            },
        }
        registry.cleanup_expired_tokens(pending)
        assert "old@uni.au.dk:subscribe" not in pending
        assert "fresh@uni.au.dk:subscribe" in pending
