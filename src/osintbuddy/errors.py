"""Error types and codes for OSINTBuddy.

This module provides structured error handling with error codes
for programmatic error handling in the CLI and UI.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standard error codes for OSINTBuddy operations."""

    # Plugin errors
    PLUGIN_NOT_FOUND = "PLUGIN_NOT_FOUND"
    PLUGIN_LOAD_ERROR = "PLUGIN_LOAD_ERROR"
    PLUGIN_INVALID = "PLUGIN_INVALID"

    # Transform errors
    TRANSFORM_NOT_FOUND = "TRANSFORM_NOT_FOUND"
    TRANSFORM_FAILED = "TRANSFORM_FAILED"
    TRANSFORM_TIMEOUT = "TRANSFORM_TIMEOUT"
    TRANSFORM_COLLISION = "TRANSFORM_COLLISION"

    # Dependency errors
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DEPENDENCY_INSTALL_FAILED = "DEPENDENCY_INSTALL_FAILED"

    # Configuration errors
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"
    SETTING_REQUIRED = "SETTING_REQUIRED"

    # Input/validation errors
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_VERSION = "INVALID_VERSION"
    INVALID_ENTITY = "INVALID_ENTITY"

    # Network errors
    NETWORK_ERROR = "NETWORK_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"

    # System errors
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    IO_ERROR = "IO_ERROR"

    # Generic
    UNKNOWN = "UNKNOWN"


class PluginError(Exception):
    """Base exception for plugin-related errors.

    Attributes:
        message: Human-readable error message
        code: ErrorCode for programmatic handling
        details: Additional error context
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code if isinstance(code, ErrorCode) else ErrorCode.UNKNOWN
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error": self.message,
            "code": self.code.value if isinstance(self.code, ErrorCode) else str(self.code),
            "details": self.details,
        }


class PluginWarn(PluginError):
    """Warning-level plugin error (non-fatal)."""
    pass


class PluginNotFoundError(PluginError):
    """Raised when a plugin cannot be found."""

    def __init__(self, plugin_name: str, details: dict[str, Any] | None = None):
        super().__init__(
            f"Plugin '{plugin_name}' not found. Make sure it's loaded.",
            ErrorCode.PLUGIN_NOT_FOUND,
            details or {"plugin": plugin_name}
        )


class TransformNotFoundError(PluginError):
    """Raised when a transform cannot be found."""

    def __init__(
        self,
        transform_name: str,
        entity_id: str,
        version: str,
        details: dict[str, Any] | None = None
    ):
        super().__init__(
            f"Transform '{transform_name}' not found for {entity_id}@{version}",
            ErrorCode.TRANSFORM_NOT_FOUND,
            details or {
                "transform": transform_name,
                "entity_id": entity_id,
                "version": version
            }
        )


class TransformCollisionError(PluginError):
    """Raised when transform registration would cause a collision."""

    def __init__(
        self,
        transform_name: str,
        entity_id: str,
        existing_spec: str,
        new_spec: str
    ):
        super().__init__(
            f"Transform collision: '{transform_name}' already registered for "
            f"{entity_id} with overlapping version spec '{existing_spec}'",
            ErrorCode.TRANSFORM_COLLISION,
            {
                "transform": transform_name,
                "entity_id": entity_id,
                "existing_spec": existing_spec,
                "new_spec": new_spec
            }
        )


class DependencyError(PluginError):
    """Raised when a dependency cannot be satisfied."""

    def __init__(self, deps: list[str], reason: str = ""):
        message = f"Missing dependencies: {deps}"
        if reason:
            message += f". {reason}"
        super().__init__(
            message,
            ErrorCode.DEPENDENCY_MISSING,
            {"dependencies": deps, "reason": reason}
        )


class ConfigError(PluginError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, setting_name: str | None = None):
        code = ErrorCode.SETTING_REQUIRED if setting_name else ErrorCode.CONFIG_INVALID
        details = {"setting": setting_name} if setting_name else {}
        super().__init__(message, code, details)


class TransformTimeoutError(PluginError):
    """Raised when a transform times out."""

    def __init__(self, transform_name: str, timeout_seconds: int):
        super().__init__(
            f"Transform '{transform_name}' timed out after {timeout_seconds}s",
            ErrorCode.TRANSFORM_TIMEOUT,
            {"transform": transform_name, "timeout": timeout_seconds}
        )


class NetworkError(PluginError):
    """Raised for network-related errors."""

    def __init__(self, message: str, url: str | None = None):
        details = {"url": url} if url else {}
        super().__init__(message, ErrorCode.NETWORK_ERROR, details)


class RateLimitError(PluginError):
    """Raised when rate limited by an external service."""

    def __init__(self, service: str, retry_after: int | None = None):
        message = f"Rate limited by {service}"
        if retry_after:
            message += f". Retry after {retry_after}s"
        super().__init__(
            message,
            ErrorCode.RATE_LIMITED,
            {"service": service, "retry_after": retry_after}
        )


class AuthError(PluginError):
    """Raised when authentication fails."""

    def __init__(self, service: str, reason: str = ""):
        message = f"Authentication failed for {service}"
        if reason:
            message += f": {reason}"
        super().__init__(
            message,
            ErrorCode.AUTH_FAILED,
            {"service": service, "reason": reason}
        )
