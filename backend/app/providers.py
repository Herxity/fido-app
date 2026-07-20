import uuid
from typing import Any, Protocol

import httpx

from .config import Settings


class PersonaProvider(Protocol):
    async def create_inquiry(self, reference_id: uuid.UUID) -> dict[str, Any]: ...

    async def consolidate(self, source_account_id: str, target_account_id: str) -> None: ...


class LivePersonaProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_inquiry(self, reference_id: uuid.UUID) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.persona_api_key}",
            "Persona-Version": self.settings.persona_version,
        }
        body = {
            "data": {
                "attributes": {
                    "inquiry-template-id": self.settings.persona_template_id,
                    "reference-id": str(reference_id),
                }
            }
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.settings.persona_api_base}/inquiries", headers=headers, json=body
            )
            response.raise_for_status()
            payload = response.json()
            data = payload["data"]
            return {
                "id": data["id"],
                "session_token": payload.get("meta", {}).get("session-token"),
            }

    async def consolidate(self, source_account_id: str, target_account_id: str) -> None:
        headers = {
            "Authorization": f"Bearer {self.settings.persona_api_key}",
            "Persona-Version": self.settings.persona_version,
        }
        body = {"meta": {"source-account-ids": [source_account_id]}}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.settings.persona_api_base}/accounts/{target_account_id}/consolidate",
                headers=headers,
                json=body,
            )
            response.raise_for_status()


class FakePersonaProvider:
    async def create_inquiry(self, reference_id: uuid.UUID) -> dict[str, Any]:
        return {"id": f"inq_test_{reference_id.hex}", "session_token": f"test_{reference_id.hex}"}

    async def consolidate(self, source_account_id: str, target_account_id: str) -> None:
        return None


def persona_provider(settings: Settings) -> PersonaProvider:
    if settings.provider_mode in {"development", "test"}:
        return FakePersonaProvider()
    return LivePersonaProvider(settings)
