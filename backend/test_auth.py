import importlib
import json
import logging
import os
import time
from typing import Any
from unittest.mock import MagicMock

from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
import jwt
from jwt import PyJWK, PyJWKSet
from jwt.algorithms import ECAlgorithm
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
import pytest

# Keep auth tests independent of the real Supabase project configuration.
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_JWKS_URL"] = (
    "https://test.supabase.co/auth/v1/.well-known/jwks.json"
)
os.environ["SUPABASE_JWT_ISSUER"] = "https://test.supabase.co/auth/v1"
os.environ["SUPABASE_JWT_AUDIENCE"] = "authenticated"

from auth import (
    ALLOWED_ALGORITHMS,
    SUPABASE_JWT_AUDIENCE,
    SUPABASE_JWT_ISSUER,
    set_jwks_client,
    get_jwks_client,
    load_supabase_settings,
)
import main as main_module
from main import (
    app,
    DEFAULT_CORS_ALLOWED_ORIGINS,
    load_cors_allowed_origins,
)

client = TestClient(app)

# Generate controlled EC (P-256) keypair for ES256 tests matching Supabase configuration
TEST_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key()
TEST_KID = "test-ec-signing-key-1"

# Generate secondary keypair for invalid signature tests
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())

# Generate RSA keypair for unsupported-algorithm tests
RSA_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# Build matching JWK
jwk_dict = json.loads(ECAlgorithm.to_jwk(TEST_PUBLIC_KEY))
jwk_dict["kid"] = TEST_KID
jwk_dict["use"] = "sig"
jwk_dict["alg"] = "ES256"

TEST_JWK = PyJWK(jwk_dict)


class MockJWKClient:
    """Mock PyJWKClient that serves controlled signing keys."""
    def __init__(self, jwks: list[PyJWK] | None = None, raise_error: Exception | None = None):
        self.jwks = jwks or [TEST_JWK]
        self.raise_error = raise_error

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        if self.raise_error:
            raise self.raise_error
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        for key in self.jwks:
            if key.key_id == kid:
                return key
        raise PyJWKClientError(f"Unable to find signing key with kid '{kid}'")


def create_test_token(
    claims: dict[str, Any] | None = None,
    private_key=TEST_PRIVATE_KEY,
    kid: str | None = TEST_KID,
    algorithm: str = "ES256",
    headers: dict[str, Any] | None = None,
) -> str:
    """Helper to generate JWT tokens with specific headers and claims."""
    now = int(time.time())
    default_claims = {
        "sub": "7e923bb6-2eb8-4234-934c-6878b66ef4b1",
        "email": "innovator@hackpreneur.dev",
        "role": "authenticated",
        "iss": SUPABASE_JWT_ISSUER,
        "aud": SUPABASE_JWT_AUDIENCE,
        "exp": now + 3600,
        "iat": now,
        "app_metadata": {"provider": "email"},
        "user_metadata": {"full_name": "Test Innovator"},
    }
    if claims:
        default_claims.update(claims)

    token_headers = {"kid": kid, "typ": "JWT"} if kid else {"typ": "JWT"}
    if headers:
        token_headers.update(headers)

    return jwt.encode(
        default_claims,
        private_key,
        algorithm=algorithm,
        headers=token_headers,
    )


@pytest.fixture(autouse=True)
def setup_mock_jwks():
    """Install mock JWKS client for each test, restoring default afterward."""
    original = get_jwks_client()
    mock_client = MockJWKClient()
    set_jwks_client(mock_client)
    yield mock_client
    set_jwks_client(original)


def test_missing_authorization_header():
    """Missing Authorization header must return 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json() == {"detail": "Authentication required"}


def test_malformed_bearer_token():
    """Malformed bearer tokens must return 401."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"}
    )
    assert response.status_code == 401
    assert "Bearer error=" in response.headers.get("WWW-Authenticate", "")
    assert response.json() == {"detail": "Invalid authentication token"}


def test_invalid_signature():
    """Token signed by an unverified key must be rejected with 401."""
    # Signed with OTHER_PRIVATE_KEY but with TEST_KID in header
    tampered_token = create_test_token(private_key=OTHER_PRIVATE_KEY, kid=TEST_KID)
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_expired_token():
    """Expired tokens must be rejected with 401 and specific expiration notice."""
    expired_token = create_test_token(claims={"exp": int(time.time()) - 3600})
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "The token has expired" in response.headers.get("WWW-Authenticate", "")
    assert response.json() == {"detail": "Token has expired"}


def test_wrong_issuer():
    """Tokens with an unexpected issuer must be rejected with 401."""
    bad_iss_token = create_test_token(claims={"iss": "https://malicious-issuer.com/auth/v1"})
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {bad_iss_token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_wrong_audience():
    """Tokens with an unexpected audience must be rejected with 401."""
    bad_aud_token = create_test_token(claims={"aud": "unauthorized-audience"})
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {bad_aud_token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_missing_subject():
    """Tokens missing a subject ('sub') claim must be rejected with 401."""
    now = int(time.time())
    no_sub_claims = {
        "email": "nosub@hackpreneur.dev",
        "iss": SUPABASE_JWT_ISSUER,
        "aud": SUPABASE_JWT_AUDIENCE,
        "exp": now + 3600,
    }
    # Encode claims directly without 'sub'
    no_sub_token = jwt.encode(
        no_sub_claims,
        TEST_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {no_sub_token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_valid_supabase_signed_token():
    """Valid ES256 Supabase token returns 200 with verified user claims and no secrets."""
    valid_token = create_test_token(
        claims={
            "sub": "a2c3d4e5-1111-2222-3333-444455556666",
            "email": "founder@hackpreneur.dev",
            "role": "authenticated",
            "app_metadata": {"role": "hacker"},
            "user_metadata": {"team": "Alpha"},
        }
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "a2c3d4e5-1111-2222-3333-444455556666"
    assert data["email"] == "founder@hackpreneur.dev"
    assert data["role"] == "authenticated"
    assert data["app_metadata"] == {"role": "hacker"}
    assert data["user_metadata"] == {"team": "Alpha"}

    # Ensure sensitive credentials and raw tokens are NOT in response
    assert "access_token" not in data
    assert "token" not in data
    assert "password" not in data
    assert "database_url" not in data


def test_untrusted_algorithm_rejected():
    """Tokens using unsupported algorithms (e.g. HS256, none) must be rejected with 401."""
    # Attempt symmetric HS256 token
    hs_token = jwt.encode(
        {
            "sub": "attacker-id",
            "iss": SUPABASE_JWT_ISSUER,
            "aud": SUPABASE_JWT_AUDIENCE,
            "exp": int(time.time()) + 3600,
        },
        "attacker-secret-key",
        algorithm="HS256",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {hs_token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_jwks_network_failure_fails_closed():
    """JWKS network connectivity failure must fail closed with 401, never accepting tokens."""
    failing_client = MockJWKClient(raise_error=PyJWKClientConnectionError("Network unreachable"))
    set_jwks_client(failing_client)

    token = create_test_token()
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_missing_supabase_url_fails_closed(monkeypatch):
    """Missing SUPABASE_URL must raise a configuration error."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        load_supabase_settings()


def test_blank_supabase_url_fails_closed(monkeypatch):
    """Blank SUPABASE_URL must raise a configuration error."""
    monkeypatch.setenv("SUPABASE_URL", "   ")

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        load_supabase_settings()


def test_supabase_settings_are_derived_from_url(monkeypatch):
    """Issuer and JWKS URL must derive from the configured Supabase URL."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co/")
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_ISSUER", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_AUDIENCE", raising=False)

    url, jwks, issuer, audience = load_supabase_settings()

    assert url == "https://test.supabase.co"
    assert jwks == "https://test.supabase.co/auth/v1/.well-known/jwks.json"
    assert issuer == "https://test.supabase.co/auth/v1"
    assert audience == "authenticated"


def test_algorithm_allowlist_is_es256_only():
    """JWT verification must only allow the project's ES256 signing algorithm."""
    assert ALLOWED_ALGORITHMS == ["ES256"]


def test_rs256_token_rejected():
    """RS256 tokens must be rejected when the project only supports ES256."""
    token = create_test_token(
        private_key=RSA_PRIVATE_KEY,
        algorithm="RS256",
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_alg_none_token_rejected():
    """Unsigned 'none' algorithm tokens must be rejected."""
    token = jwt.encode(
        {
            "sub": "7e923bb6-2eb8-4234-934c-6878b66ef4b1",
            "iss": SUPABASE_JWT_ISSUER,
            "aud": SUPABASE_JWT_AUDIENCE,
            "exp": int(time.time()) + 3600,
        },
        key=None,
        algorithm="none",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


@pytest.mark.parametrize(
    "sub",
    [
        "attacker-id",
        "12345",
        "   ",
        12345,
        ["not", "a", "uuid"],
    ],
)
def test_invalid_subject_rejected(sub):
    """Non-UUID, blank and non-string subjects must be rejected."""
    token = create_test_token(claims={"sub": sub})
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_valid_uuid_subject_still_accepted():
    """A valid UUID subject must still authenticate successfully."""
    subject = "a2c3d4e5-1111-2222-3333-444455556666"
    token = create_test_token(claims={"sub": subject})
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == subject


@pytest.mark.parametrize("claim", ["exp", "iss", "aud"])
def test_missing_required_claim_rejected(claim):
    """Tokens missing exp, iss or aud must be rejected."""
    now = int(time.time())
    claims = {
        "sub": "7e923bb6-2eb8-4234-934c-6878b66ef4b1",
        "iss": SUPABASE_JWT_ISSUER,
        "aud": SUPABASE_JWT_AUDIENCE,
        "exp": now + 3600,
    }
    claims.pop(claim)

    token = jwt.encode(
        claims,
        TEST_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_jwks_client_error_fails_closed():
    """Non-network JWKS lookup errors must also fail closed with 401."""
    set_jwks_client(
        MockJWKClient(raise_error=PyJWKClientError("lookup failed"))
    )
    token = create_test_token()
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_unknown_kid_rejected():
    """Tokens with an unknown key ID must be rejected."""
    token = create_test_token(kid="unknown-kid")
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_missing_kid_rejected():
    """Tokens without a key ID must be rejected."""
    token = create_test_token(kid=None)
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


def test_jwks_error_does_not_leak_details(caplog):
    """JWKS failure details and raw tokens must not appear in logs."""
    caplog.set_level(logging.DEBUG)
    sentinel = "sensitive-jwks-detail"
    set_jwks_client(
        MockJWKClient(
            raise_error=PyJWKClientConnectionError(sentinel)
        )
    )

    token = create_test_token()
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert sentinel not in caplog.text
    assert token not in caplog.text


CORS_PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "authorization",
}


def create_cors_test_client(monkeypatch, configured_origins):
    """Build a test client with the requested CORS configuration."""
    if configured_origins is None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", configured_origins)

    importlib.reload(main_module)
    return TestClient(main_module.app)


def cors_preflight(cors_client, origin):
    """Send a CORS preflight request for the given origin."""
    return cors_client.options(
        "/api/auth/me",
        headers={"Origin": origin, **CORS_PREFLIGHT_HEADERS},
    )


def test_cors_default_origins_are_used_when_unset(monkeypatch):
    """Unset CORS configuration must use the local development defaults."""
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert load_cors_allowed_origins() == list(DEFAULT_CORS_ALLOWED_ORIGINS)


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
def test_cors_default_origin_is_allowed(monkeypatch, origin):
    """Both local development origins must be allowed by default."""
    cors_client = create_cors_test_client(monkeypatch, None)

    response = cors_preflight(cors_client, origin)

    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_allows_authorization_header(monkeypatch):
    """CORS preflight must permit the Authorization request header."""
    cors_client = create_cors_test_client(monkeypatch, None)

    response = cors_preflight(cors_client, "http://localhost:5173")

    assert response.status_code == 200
    assert "authorization" in response.headers.get(
        "access-control-allow-headers", ""
    ).lower()
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_explicitly_configured_origin_is_allowed(monkeypatch):
    """Explicitly configured origins must be trimmed and allowed."""
    cors_client = create_cors_test_client(
        monkeypatch,
        " https://app.example.com , , https://admin.example.com ",
    )

    assert load_cors_allowed_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]

    response = cors_preflight(cors_client, "https://app.example.com")

    assert response.headers.get("access-control-allow-origin") == (
        "https://app.example.com"
    )


def test_cors_unlisted_origin_is_not_allowed(monkeypatch):
    """Unlisted origins must not receive an Access-Control-Allow-Origin header."""
    cors_client = create_cors_test_client(
        monkeypatch,
        "https://app.example.com",
    )

    response = cors_preflight(cors_client, "https://evil.example.com")

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("configured_origins", ["", "   ", " , , "])
def test_cors_empty_configuration_uses_defaults_without_wildcard(
    monkeypatch,
    configured_origins,
):
    """Empty configuration must fall back to defaults, never wildcard access."""
    cors_client = create_cors_test_client(monkeypatch, configured_origins)

    allowed = cors_preflight(cors_client, "http://localhost:5173")
    assert allowed.headers.get("access-control-allow-origin") == (
        "http://localhost:5173"
    )

    blocked = cors_preflight(cors_client, "https://evil.example.com")
    assert "access-control-allow-origin" not in blocked.headers


def test_cors_wildcard_configuration_is_rejected(monkeypatch):
    """Wildcard origins must be rejected rather than granting broad access."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValueError, match="wildcard"):
        load_cors_allowed_origins()
