from __future__ import annotations

from typing import Optional


class CalderaError(Exception):
    """Base class for Caldera-related exceptions."""


class CalderaAPIError(CalderaError):
    """Raised when Caldera returns a non-successful HTTP response."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, payload: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class CalderaAuthenticationError(CalderaAPIError):
    """Raised when authentication with Caldera fails."""


class CalderaUnavailableError(CalderaError):
    """Raised when Caldera cannot be reached or is disabled."""


class CalderaOperationTimeout(CalderaError):
    """Raised when polling an operation exceeds the configured timeout."""
