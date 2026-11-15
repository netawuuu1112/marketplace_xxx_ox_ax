import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import config
from core.orchestrator import Orchestrator
from llm.gateway import LLMGateway
from llm.providers import ProviderError
from models import SearchConstraints, SessionState


def test_live_mode_without_llm_uses_query_fallback(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    gateway = LLMGateway(db=object(), api_key="", mistral_api_key="", local_llm=False)

    async def check():
        with pytest.raises(ProviderError):
            await gateway.structured(kind="constraints", prompt="ssd 1 tb", schema=SearchConstraints)
        orchestrator = Orchestrator(db=object(), llm=gateway, adapters=[])
        result = await orchestrator._extract_constraints("SSD 1 ТБ до 6000 рублей", SessionState())
        assert result.query
        assert result.max_price == 6000

    asyncio.run(check())
