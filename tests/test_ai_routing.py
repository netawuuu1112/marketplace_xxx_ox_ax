import asyncio
import sys
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from llm.gateway import LLMGateway
from storage.postgres import PostgresDatabase


class FakePool:
    def __init__(self, encrypted):
        self.encrypted = encrypted

    async def fetch(self, sql):
        if "ai_providers" in sql:
            return [{"name": "aitunnel", "base_url": "https://api.aitunnel.ru/v1",
                     "model_id": "example-model", "api_key_ciphertext": self.encrypted,
                     "enabled": True}]
        return [{"kind": "constraints", "provider_name": "aitunnel",
                 "model_id": "example-model"}]


def test_database_routes_are_loaded_without_exposing_key(monkeypatch):
    secret = Fernet.generate_key().decode()
    monkeypatch.setenv("LLM_ENCRYPTION_KEY", secret)
    encrypted = Fernet(secret.encode()).encrypt(b"test-api-key").decode()
    db = PostgresDatabase("unused")
    db._pool = FakePool(encrypted)
    gateway = LLMGateway(db, api_key="", mistral_api_key="", local_llm=False)

    async def check():
        await gateway.refresh_from_db()
        provider, model = gateway._resolve_provider(gateway._routes["constraints"])
        assert provider.name == "aitunnel"
        assert model == "example-model"
        await gateway.aclose()

    asyncio.run(check())


def test_aitunnel_only_configuration_can_route_vision_without_openrouter(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from pydantic import BaseModel
    import config
    monkeypatch.setattr(config,'DEMO_MODE',False)
    class Output(BaseModel):
        item: str
    async def scenario():
        database=SimpleNamespace(budget_used=AsyncMock(return_value=0),budget_increment=AsyncMock())
        gateway=LLMGateway(database,api_key='',mistral_api_key='',local_llm=False)
        provider=SimpleNamespace(name='aitunnel',complete=AsyncMock(return_value=Output(item='SSD')),aclose=AsyncMock())
        gateway._providers=[provider];gateway._provider=provider
        gateway._routes={}
        result=await gateway.structured(kind='vision',prompt='Identify',schema=Output,images=['data:image/png;base64,fixture'])
        assert result.item=='SSD'
        assert provider.complete.call_args.kwargs['model']=='gpt-4o-mini'
        await gateway.aclose()
    asyncio.run(scenario())
