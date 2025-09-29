from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    neo4j_database: Optional[str] = None
    default_cypher_limit: int = 100
    allow_write_cypher: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables with GRAPH_ prefix."""
        return cls(
            neo4j_uri=os.getenv("GRAPH_NEO4J_URI"),
            neo4j_user=os.getenv("GRAPH_NEO4J_USER"),
            neo4j_password=os.getenv("GRAPH_NEO4J_PASSWORD"),
            neo4j_database=os.getenv("GRAPH_NEO4J_DATABASE"),
            default_cypher_limit=int(os.getenv("GRAPH_DEFAULT_CYPHER_LIMIT", "100")),
            allow_write_cypher=os.getenv("GRAPH_ALLOW_WRITE_CYPHER", "false").lower() == "true",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
