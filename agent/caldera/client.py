from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .config import CalderaSettings
from .exceptions import (
    CalderaAPIError,
    CalderaAuthenticationError,
    CalderaUnavailableError,
)

logger = logging.getLogger(__name__)

JSON = Dict[str, Any]


class CalderaClient:
    """Async REST client for the MITRE Caldera API."""

    def __init__(
        self,
        settings: CalderaSettings,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not settings.enabled:
            raise CalderaUnavailableError("Caldera integration is disabled in configuration")

        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=str(settings.base_url),
            headers=self._default_headers,
            verify=settings.verify_ssl,
            timeout=httpx.Timeout(30.0, connect=settings.healthcheck_timeout_seconds),
        )

    @property
    def _default_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if self.settings.api_key:
            headers['KEY'] = self.settings.api_key
            headers['Authorization'] = f'Bearer {self.settings.api_key}'
        return headers

    async def __aenter__(self) -> 'CalderaClient':
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = path if path.startswith('/') else f'/{path}'
        headers = self._default_headers
        try:
            response = await self._client.request(method, url, params=params, json=json, headers=headers)
            if response.status_code in {401, 403}:
                raise CalderaAuthenticationError(
                    f'Caldera authentication failed with status {response.status_code}',
                    status_code=response.status_code,
                    payload=self._safe_json(response),
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise CalderaUnavailableError(f'Caldera request timed out: {url}') from exc
        except httpx.HTTPStatusError as exc:
            data = self._safe_json(exc.response)
            raise CalderaAPIError(
                f'Caldera API error {exc.response.status_code} for {url}',
                status_code=exc.response.status_code,
                payload=data,
            ) from exc
        except httpx.TransportError as exc:
            raise CalderaUnavailableError(f'Unable to reach Caldera at {self.settings.base_url}') from exc

        if response.status_code == 204 or not response.content:
            return None
        return self._safe_json(response)

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}

    async def ping(self) -> Any:
        """Basic health probe using the agents endpoint."""
        logger.debug('Pinging Caldera API at %s', self.settings.base_url)
        return await self._request('GET', '/api/v2/agents')

    async def list_agents(self) -> Any:
        return await self._request('GET', '/api/v2/agents')

    async def get_agent(self, paw: str) -> Any:
        return await self._request('GET', f'/api/v2/agents/{paw}')

    async def list_adversaries(self) -> Any:
        payload = {'index': 'adversaries'}
        return await self._request('POST', '/api/rest', json=payload)

    async def create_operation(self, *, payload: JSON) -> JSON:
        if payload.get('index') != 'operations':
            payload = {**payload, 'index': 'operations'}
        logger.debug('Creating Caldera operation with payload: %s', payload)
        return await self._request('PUT', '/api/rest', json=payload)

    async def update_operation_state(self, operation_id: str, state: str) -> JSON:
        payload: JSON = {
            'index': 'operations',
            'id': operation_id,
            'state': state,
        }
        logger.debug('Updating Caldera operation %s to state %s', operation_id, state)
        return await self._request('POST', '/api/rest', json=payload)

    async def get_operation(self, operation_id: str) -> JSON:
        payload: JSON = {'index': 'operations', 'id': operation_id}
        return await self._request('POST', '/api/rest', json=payload)

    async def delete_operation(self, operation_id: str) -> Any:
        payload: JSON = {'index': 'operations', 'id': operation_id}
        logger.debug('Deleting Caldera operation %s', operation_id)
        return await self._request('DELETE', '/api/rest', json=payload)

    async def get_operation_links(self, operation_id: str) -> Any:
        operation = await self.get_operation(operation_id)
        return operation.get('chain', []) if isinstance(operation, dict) else operation

    async def get_link_result(self, link_id: str) -> Any:
        return await self._request('GET', f'/api/v2/links/{link_id}')

    async def view_agent_abilities(self, paw: str) -> Any:
        payload: JSON = {'paw': paw}
        return await self._request('POST', '/plugin/access/abilities', json=payload)

    async def execute_ability(
        self,
        *,
        paw: str,
        ability_id: str,
        facts: Optional[Dict[str, Any]] = None,
        obfuscator: str = 'plain-text',
    ) -> Any:
        payload: JSON = {
            'paw': paw,
            'ability_id': ability_id,
            'obfuscator': obfuscator,
        }
        if facts:
            payload['facts'] = facts
        logger.debug('Executing Caldera ability %s on agent %s', ability_id, paw)
        return await self._request('POST', '/plugin/access/exploit', json=payload)
