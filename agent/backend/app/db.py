from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable

from .settings import Settings, get_settings


class Neo4jDriverFactory:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._driver = None

    def _create_driver(self):
        if not self._settings.neo4j_uri:
            return None
        auth = None
        if self._settings.neo4j_user and self._settings.neo4j_password:
            auth = basic_auth(self._settings.neo4j_user, self._settings.neo4j_password)
        return GraphDatabase.driver(self._settings.neo4j_uri, auth=auth)

    def get_driver(self):
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    @contextmanager
    def session(self):
        driver = self.get_driver()
        if driver is None:
            raise RuntimeError("Neo4j driver not configured")
        database = self._settings.neo4j_database
        try:
            with driver.session(database=database) as session:
                yield session
        except ServiceUnavailable as exc:
            raise RuntimeError("Neo4j unavailable") from exc

    @asynccontextmanager
    async def async_session(self) -> AsyncIterator:
        raise NotImplementedError("Async sessions not supported in this skeleton")


_driver_factory: Optional[Neo4jDriverFactory] = None


def get_driver_factory() -> Neo4jDriverFactory:
    global _driver_factory
    if _driver_factory is None:
        _driver_factory = Neo4jDriverFactory()
    return _driver_factory
