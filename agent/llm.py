from __future__ import annotations

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .config import AgentConfig


def build_llm(config: AgentConfig, *, temperature: float = 0.1) -> BaseChatModel:
    return ChatOpenAI(model=config.model, temperature=temperature, streaming=config.streaming)
