from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class CalderaSettings(BaseModel):
    """Configuration block for MITRE Caldera integration."""

    enabled: bool = Field(default=False, description='Toggle Caldera integration on/off')
    base_url: HttpUrl | str = Field(
        default='http://127.0.0.1:8888',
        description='Base URL for the Caldera server (API root)'
    )
    api_key: Optional[str] = Field(default=None, description='API key for authenticated requests')
    verify_ssl: bool = Field(default=False, description='Verify TLS certificates when using HTTPS')

    healthcheck_timeout_seconds: float = Field(default=5.0, ge=1.0)
    healthcheck_interval_seconds: float = Field(default=60.0, ge=5.0)
    operation_poll_interval_seconds: float = Field(default=5.0, ge=1.0)
    operation_poll_timeout_seconds: float = Field(default=900.0, ge=30.0)

    max_retry_attempts: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=2.0, ge=0.1)

    class Config:
        frozen = True

    @validator('base_url')
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip('/')

    @classmethod
    def from_env(cls) -> 'CalderaSettings':
        """Construct settings from CALDERA_* environment variables."""
        def _get(name: str, default: Optional[str] = None) -> Optional[str]:
            return os.getenv(name, default)

        enabled = _get('CALDERA_ENABLED', 'false').lower() in {'1', 'true', 'yes', 'on'}
        base_url = _get('CALDERA_BASE_URL', 'http://127.0.0.1:8888')
        api_key = _get('CALDERA_API_KEY') or None
        verify_ssl = _get('CALDERA_VERIFY_SSL', 'false').lower() in {'1', 'true', 'yes', 'on'}

        def _float(name: str, default: float) -> float:
            try:
                return float(_get(name, str(default)))
            except (TypeError, ValueError):
                return default

        def _int(name: str, default: int) -> int:
            try:
                return int(_get(name, str(default)))
            except (TypeError, ValueError):
                return default

        return cls(
            enabled=enabled,
            base_url=base_url,
            api_key=api_key,
            verify_ssl=verify_ssl,
            healthcheck_timeout_seconds=_float('CALDERA_HEALTHCHECK_TIMEOUT', 5.0),
            healthcheck_interval_seconds=_float('CALDERA_HEALTHCHECK_INTERVAL', 60.0),
            operation_poll_interval_seconds=_float('CALDERA_OPERATION_POLL_INTERVAL', 5.0),
            operation_poll_timeout_seconds=_float('CALDERA_OPERATION_POLL_TIMEOUT', 900.0),
            max_retry_attempts=_int('CALDERA_MAX_RETRY_ATTEMPTS', 3),
            retry_backoff_seconds=_float('CALDERA_RETRY_BACKOFF', 2.0),
        )

    @property
    def is_configured(self) -> bool:
        """Return True when Caldera should be considered usable."""
        return self.enabled and bool(self.api_key or 'localhost' in str(self.base_url))
