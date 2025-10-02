from __future__ import annotations

import asyncio
import logging

import httpx

from .config import CalderaSettings
from .exceptions import CalderaUnavailableError

logger = logging.getLogger(__name__)


def _default_headers(settings: CalderaSettings) -> dict[str, str]:
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if settings.api_key:
        headers['KEY'] = settings.api_key
        headers['Authorization'] = f'Bearer {settings.api_key}'
    return headers


async def check_caldera_health(settings: CalderaSettings) -> tuple[bool, str]:
    """Probe Caldera and return (healthy, reason)."""
    if not settings.enabled:
        return False, 'disabled'

    if not settings.is_configured:
        return False, 'missing api key or base url'

    try:
        async with httpx.AsyncClient(
            base_url=str(settings.base_url),
            headers=_default_headers(settings),
            verify=settings.verify_ssl,
            timeout=httpx.Timeout(settings.healthcheck_timeout_seconds, connect=settings.healthcheck_timeout_seconds),
        ) as client:
            response = await client.get('/api/v2/agents')
            response.raise_for_status()
    except httpx.TimeoutException:
        logger.warning('Caldera health check timed out')
        return False, 'timeout'
    except httpx.HTTPStatusError as exc:
        logger.warning('Caldera health check failed: %s', exc)
        return False, f'http {exc.response.status_code}'
    except Exception as exc:  # noqa: BLE001
        logger.warning('Caldera health check error: %s', exc)
        return False, 'unreachable'

    return True, 'ok'


async def ensure_caldera_available(settings: CalderaSettings) -> None:
    healthy, reason = await check_caldera_health(settings)
    if not healthy:
        raise CalderaUnavailableError(f'Caldera is not available: {reason}')


def ensure_caldera_available_sync(settings: CalderaSettings) -> None:
    """Synchronous helper for startup hooks."""
    try:
        import anyio

        anyio.run(ensure_caldera_available, settings)
    except ModuleNotFoundError:
        asyncio.run(ensure_caldera_available(settings))
