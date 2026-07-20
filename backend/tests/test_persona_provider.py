import uuid

import httpx
import pytest

from app.config import Settings
from app.providers import LivePersonaProvider


@pytest.mark.asyncio
async def test_live_persona_request_contracts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/inquiries"):
            return httpx.Response(
                201,
                json={"data": {"id": "inq_1"}, "meta": {"session-token": "session_1"}},
            )
        return httpx.Response(202, json={})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.providers.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    settings = Settings(
        environment="development",
        provider_mode="live",
        persona_api_key="persona-key",
        persona_template_id="itmpl_1",
    )
    provider = LivePersonaProvider(settings)
    reference_id = uuid.uuid4()

    created = await provider.create_inquiry(reference_id)
    await provider.consolidate("act_source", "act_destination")

    assert created == {"id": "inq_1", "session_token": "session_1"}
    assert str(requests[0].url) == "https://api.withpersona.com/api/v1/inquiries"
    assert requests[0].headers["Persona-Version"] == "2025-10-27"
    assert __import__("json").loads(requests[0].content) == {
        "data": {
            "attributes": {
                "inquiry-template-id": "itmpl_1",
                "reference-id": str(reference_id),
            }
        }
    }
    assert str(requests[1].url) == (
        "https://api.withpersona.com/api/v1/accounts/act_destination/consolidate"
    )
    assert __import__("json").loads(requests[1].content) == {
        "meta": {"source-account-ids": ["act_source"]}
    }
