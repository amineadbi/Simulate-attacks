from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from .caldera.config import CalderaSettings
from .tools import MCPToolConfig


class AgentConfig(BaseModel):
    model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4o"))
    system_prompt_path: Path = Field(default=Path("agent/prompts/system.md"))
    memory_max_turns: int = Field(default=12, ge=1)
    max_tool_retries: int = Field(default=2, ge=0)
    streaming: bool = True
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=100)

    # Security and validation settings
    validate_cypher_queries: bool = Field(default=True)
    max_graph_nodes: int = Field(default=10000, ge=1)
    max_graph_edges: int = Field(default=50000, ge=1)

    # External tool configuration
    tools: List[MCPToolConfig] = Field(default_factory=list)

    # Simulation platform configuration
    caldera: CalderaSettings = Field(default_factory=CalderaSettings.from_env)

    @classmethod
    def from_env(cls, *, tools: Optional[List[MCPToolConfig]] = None) -> "AgentConfig":
        cfg = cls()
        if tools:
            cfg.tools = list(tools)
        return cfg


def load_config() -> AgentConfig:
    """Load agent configuration from environment variables."""
    return AgentConfig.from_env()
