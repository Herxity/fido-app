import base64
import json
import os
import time
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

os.environ.update(
    {
        "FIDO_ENVIRONMENT": "test",
        "FIDO_PROVIDER_MODE": "test",
        "FIDO_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FIDO_LOOKUP_HASH_KEY": "test-lookup-hash-key-at-least-32-bytes",
        "FIDO_FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "FIDO_IDENTITY_HASH_KEY": "identity-test-hmac-key-at-least-32-bytes",
        "FIDO_CLERK_WEBHOOK_SECRET": "whsec_"
        + base64.b64encode(b"clerk-test-secret-at-least-32-bytes").decode(),
    }
)

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


def token(
    sub: str,
    role: str = "owner",
    org_id: str | None = None,
    *,
    expired: bool = False,
    pending: bool = False,
) -> str:
    claims: dict[str, object] = {
        "sub": sub,
        "role": role,
        "exp": int(time.time()) + (-10 if expired else 3600),
    }
    if org_id:
        claims["o"] = {"id": org_id, "rol": role}
    if pending:
        claims["sts"] = "pending"
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"dev.{encoded}"


@pytest_asyncio.fixture(autouse=True)
async def database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as instance:
        yield instance


@pytest.fixture
def auth():  # type: ignore[no-untyped-def]
    return lambda sub="owner_1", role="owner", org_id=None, **kw: {
        "Authorization": f"Bearer {token(sub, role, org_id, **kw)}"
    }
