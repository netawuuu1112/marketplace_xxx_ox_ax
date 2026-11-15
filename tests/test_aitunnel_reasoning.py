"""Reasoning models need room to emit JSON after their internal reasoning."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from llm.providers import OpenAICompatProvider
from models import SearchConstraints


class ReasoningCompletions:
    async def create(self, **request):
        enough_room = request.get("reasoning_effort") == "low" and request["max_tokens"] >= 4096
        content = json.dumps({"query": "SSD 1 ТБ", "max_price": 6000}) if enough_room else ""
        choice = SimpleNamespace(
            finish_reason="stop" if enough_room else "length",
            message=SimpleNamespace(content=content),
        )
        return SimpleNamespace(choices=[choice])


def test_aitunnel_deepseek_returns_structured_answer_after_reasoning():
    provider = object.__new__(OpenAICompatProvider)
    provider.name = "aitunnel"
    provider._timeout = 5
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=ReasoningCompletions()))

    result = asyncio.run(provider.complete(
        model="deepseek-v4-pro", kind="constraints",
        prompt="ПОЛЬЗОВАТЕЛЬ: SSD 1 ТБ до 6000 рублей", schema=SearchConstraints,
    ))

    assert result.query == "SSD 1 ТБ"
    assert result.max_price == 6000
