"""Transform settings framework for OSINTBuddy.

This module provides a settings system for transforms, allowing them to
declare required configuration parameters with types, defaults, and
validation.

Example usage:
    @transform(
        target="website@1.0.0",
        label="Screenshot with API",
        settings=[
            TransformSetting(
                name="api_key",
                display_name="Screenshot API Key",
                setting_type="password",
                required=True,
                global_setting=True
            ),
            TransformSetting(
                name="timeout",
                display_name="Timeout (seconds)",
                setting_type="int",
                default_value="30"
            )
        ]
    )
    async def screenshot(entity, cfg):
        api_key = cfg["api_key"]
        timeout = int(cfg.get("timeout", 30))
        ...
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal


SettingType = Literal["string", "int", "bool", "url", "password", "date", "datetime", "float"]


@dataclass(frozen=True)
class TransformSetting:
    """A configuration setting for a transform.

    Attributes:
        name: Internal name used as the key in cfg dict
        display_name: Human-readable label shown in UI
        setting_type: Data type for validation and UI rendering
        default_value: Default value as string (converted based on setting_type)
        required: Whether the setting must be provided
        global_setting: If True, setting is shared across all transforms
        description: Help text for the setting
        popup: If True, show in a popup dialog instead of inline
    """
    name: str
    display_name: str
    setting_type: SettingType = "string"
    default_value: str = ""
    required: bool = False
    global_setting: bool = False
    description: str = ""
    popup: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate a value against this setting's type.

        Args:
            value: The value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None or value == "":
            if self.required:
                return False, f"{self.display_name} is required"
            return True, ""

        try:
            if self.setting_type == "int":
                int(value)
            elif self.setting_type == "float":
                float(value)
            elif self.setting_type == "bool":
                if str(value).lower() not in ("true", "false", "1", "0", "yes", "no"):
                    return False, f"{self.display_name} must be a boolean"
            elif self.setting_type == "url":
                if not str(value).startswith(("http://", "https://")):
                    return False, f"{self.display_name} must be a valid URL"
        except (ValueError, TypeError):
            return False, f"{self.display_name} must be a valid {self.setting_type}"

        return True, ""

    def convert(self, value: str) -> Any:
        """Convert a string value to the appropriate type.

        Args:
            value: String value to convert

        Returns:
            Converted value
        """
        if value is None or value == "":
            value = self.default_value

        if self.setting_type == "int":
            return int(value) if value else 0
        elif self.setting_type == "float":
            return float(value) if value else 0.0
        elif self.setting_type == "bool":
            return str(value).lower() in ("true", "1", "yes")
        return value


@dataclass
class SettingsManager:
    """Manages transform settings storage and retrieval.

    Settings are stored in the user's config directory:
        ~/.osintbuddy/
            settings.json          # Global settings
            transforms/
                <transform_name>.json  # Per-transform settings
    """
    config_dir: Path = field(default_factory=lambda: Path.home() / ".osintbuddy")

    def __post_init__(self):
        self.config_dir = Path(self.config_dir)
        self.transforms_dir = self.config_dir / "transforms"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create config directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.transforms_dir.mkdir(parents=True, exist_ok=True)

    @property
    def global_settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    def get_transform_settings_path(self, transform_name: str) -> Path:
        # Sanitize transform name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in transform_name)
        return self.transforms_dir / f"{safe_name}.json"

    def load_global_settings(self) -> dict[str, Any]:
        """Load global settings from disk."""
        if self.global_settings_path.exists():
            try:
                with open(self.global_settings_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save_global_settings(self, settings: dict[str, Any]) -> None:
        """Save global settings to disk."""
        with open(self.global_settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_transform_settings(self, transform_name: str) -> dict[str, Any]:
        """Load settings for a specific transform."""
        path = self.get_transform_settings_path(transform_name)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save_transform_settings(self, transform_name: str, settings: dict[str, Any]) -> None:
        """Save settings for a specific transform."""
        path = self.get_transform_settings_path(transform_name)
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)

    def get_setting(self, name: str, transform_name: str | None = None) -> Any:
        """Get a setting value, checking transform-specific then global.

        Args:
            name: Setting name
            transform_name: Optional transform name for transform-specific settings

        Returns:
            Setting value or None if not found
        """
        # Check transform-specific first
        if transform_name:
            transform_settings = self.load_transform_settings(transform_name)
            if name in transform_settings:
                return transform_settings[name]

        # Fall back to global
        global_settings = self.load_global_settings()
        return global_settings.get(name)

    def set_setting(
        self,
        name: str,
        value: Any,
        transform_name: str | None = None,
        global_setting: bool = False
    ) -> None:
        """Set a setting value.

        Args:
            name: Setting name
            value: Setting value
            transform_name: Transform name for transform-specific settings
            global_setting: If True, save to global settings
        """
        if global_setting:
            settings = self.load_global_settings()
            settings[name] = value
            self.save_global_settings(settings)
        elif transform_name:
            settings = self.load_transform_settings(transform_name)
            settings[name] = value
            self.save_transform_settings(transform_name, settings)

    def build_config(
        self,
        transform_name: str,
        declared_settings: list[TransformSetting],
        provided_config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build a complete config dict for a transform.

        Merges:
        1. Default values from declared settings
        2. Stored global settings (for global_setting=True)
        3. Stored transform-specific settings
        4. Provided config (runtime overrides)

        Args:
            transform_name: Name of the transform
            declared_settings: List of TransformSetting declarations
            provided_config: Runtime config overrides

        Returns:
            Complete config dict ready for transform execution
        """
        config: dict[str, Any] = {}

        # Start with defaults
        for setting in declared_settings:
            if setting.default_value:
                config[setting.name] = setting.convert(setting.default_value)

        # Load stored settings
        global_settings = self.load_global_settings()
        transform_settings = self.load_transform_settings(transform_name)

        for setting in declared_settings:
            # Global settings
            if setting.global_setting and setting.name in global_settings:
                config[setting.name] = setting.convert(str(global_settings[setting.name]))
            # Transform-specific settings
            if setting.name in transform_settings:
                config[setting.name] = setting.convert(str(transform_settings[setting.name]))

        # Runtime overrides
        if provided_config:
            for setting in declared_settings:
                if setting.name in provided_config:
                    config[setting.name] = setting.convert(str(provided_config[setting.name]))

        return config

    def validate_config(
        self,
        declared_settings: list[TransformSetting],
        config: dict[str, Any]
    ) -> list[str]:
        """Validate a config dict against declared settings.

        Args:
            declared_settings: List of TransformSetting declarations
            config: Config dict to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for setting in declared_settings:
            value = config.get(setting.name)
            is_valid, error = setting.validate(value)
            if not is_valid:
                errors.append(error)
        return errors


# Global settings manager instance
_settings_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
