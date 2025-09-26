from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MCPToolConfig(BaseModel):
    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout_seconds: float = Field(default=30.0, ge=1.0)


class AgentConfig(BaseModel):
    model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4.1"))
    system_prompt_path: Path = Field(default=Path("agent/prompts/system.md"))
    tools: List[MCPToolConfig] = Field(default_factory=list)
    memory_max_turns: int = Field(default=12, ge=1)
    max_tool_retries: int = Field(default=2, ge=0)
    streaming: bool = True

    @classmethod
    def from_env(cls) -> "AgentConfig":
        tool_configs: List[MCPToolConfig] = []
        raw_tools = os.getenv("MCP_TOOLS")
        if raw_tools:
            for chunk in raw_tools.split(","):
                name, _, base_url = chunk.partition(":")
                name = name.strip()
                base_url = base_url.strip()
                if not name or not base_url:
                    continue
                api_key = os.getenv(f"MCP_{name.upper()}_API_KEY")
                tool_configs.append(MCPToolConfig(name=name, base_url=base_url, api_key=api_key))
        return cls(tools=tool_configs)


def load_config() -> AgentConfig:
    return AgentConfig.from_env()
