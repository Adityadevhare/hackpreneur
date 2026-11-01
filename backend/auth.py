import logging
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
)
from pydantic import BaseModel, Field

# Load environment configuration securely
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


def load_supabase_settings() -> tuple[str, str, str, str]:
    """Load and validate Supabase JWT settings from the environment."""
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url or not supabase_url.strip():
        raise ValueError(
            "SUPABASE_URL environment variable is not set. "
            "Configure it in backend/.env."
        )
    supabase_url = supabase_url.strip().rstrip("/")

    jwks_url = (
        os.getenv("SUPABASE_JWKS_URL")
        or f"{supabase_url}/auth/v1/.well-known/jwks.json"
    )
    issuer = (
        os.getenv("SUPABASE_JWT_ISSUER")
        or f"{supabase_url}/auth/v1"
    ).rstrip("/")
    audience = os.getenv("SUPABASE_JWT_AUDIENCE") or "authenticated"

    return supabase_url, jwks_url, issuer, audience


(
    SUPABASE_URL,
    SUPABASE_JWKS_URL,
    SUPABASE_JWT_ISSUER,
    SUPABASE_JWT_AUDIENCE,
) = load_supabase_settings()

# The configured Supabase project publishes ES256 (EC P-256) signing keys.
ALLOWED_ALGORITHMS = ["ES256"]

# Global JWKS client with thread-safe caching and key rotation support
_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    """Return the active PyJWKClient instance, caching JWK sets for 5 minutes."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            SUPABASE_JWKS_URL,
            cache_jwk_set=True,
            lifespan=300,
        )
    return _jwks_client


def set_jwks_client(client: PyJWKClient | None) -> None:
    """Override the JWKS client (primarily for controlled testing/mocking)."""
    global _jwks_client
    _jwks_client = client


class AuthenticatedUser(BaseModel):
    """Typed authenticated user representation verified via Supabase JWT."""
    id: str  # Verified subject (UUID)
    email: str | None = None
    role: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    claims: dict[str, Any] = Field(default_factory=dict)


def verify_supabase_jwt(
    token: str,
    jwks_client: PyJWKClient | None = None
) -> dict[str, Any]:
    """
    Verify and decode a Supabase-issued JWT access token.
    
    Validates:
    - Signature via public JWKS key
    - Expiration (exp)
    - Issuer (iss)
    - Audience (aud)
    - Subject (sub)
    - Permitted asymmetric algorithms only (rejects unsigned / symmetric / unconfigured)
    
    Fails closed on JWKS network failure or invalid claims.
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Empty or invalid token string")

    client = jwks_client or get_jwks_client()

    try:
        # Retrieve the matching signing key from JWKS by inspecting the token's header (kid)
        signing_key = client.get_signing_key_from_jwt(token)
    except (PyJWKClientConnectionError, PyJWKClientError) as e:
        logger.warning("JWKS key retrieval failed: %s", type(e).__name__)
        raise InvalidTokenError("JWKS key lookup failed") from e
    except Exception as e:
        logger.warning("Failed to inspect token header for signing key: %s", type(e).__name__)
        raise InvalidTokenError("Unable to locate signing key for token") from e

    # Decode and verify token signature and claims
    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            issuer=SUPABASE_JWT_ISSUER,
            audience=SUPABASE_JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["exp", "iss", "aud", "sub"],
            },
        )
    except ExpiredSignatureError:
        logger.info("JWT expired")
        raise
    except (InvalidSignatureError, InvalidIssuerError, InvalidAudienceError) as e:
        logger.info("JWT validation failed: %s", type(e).__name__)
        raise
    except PyJWTError as e:
        logger.info("JWT decoding error: %s", type(e).__name__)
        raise

    # Ensure subject claim is a non-empty UUID
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise InvalidTokenError("Missing or invalid subject ('sub') claim")

    try:
        uuid.UUID(sub)
    except ValueError as e:
        raise InvalidTokenError(
            "Subject ('sub') claim must be a valid UUID"
        ) from e

    return payload


# FastAPI Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
) -> AuthenticatedUser:
    """
    FastAPI dependency to authenticate requests via Supabase Bearer token.
    
    Returns a typed AuthenticatedUser on success.
    Returns HTTP 401 with appropriate WWW-Authenticate headers on failure.
    """
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    try:
        payload = verify_supabase_jwt(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="The token has expired"'},
        )
    except Exception as e:
        # Avoid leaking internal validation details, cryptographic exceptions, or raw tokens
        logger.debug("Authentication failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    return AuthenticatedUser(
        id=payload["sub"],
        email=payload.get("email"),
        role=payload.get("role"),
        app_metadata=payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {},
        user_metadata=payload.get("user_metadata") if isinstance(payload.get("user_metadata"), dict) else {},
        claims=payload,
    )
