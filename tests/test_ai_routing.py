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
