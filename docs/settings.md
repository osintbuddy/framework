# Settings

The settings framework provides persistent configuration for transforms. Settings are stored locally and can be global (shared across transforms) or transform-specific.

## Overview

Transforms can declare configuration requirements using `TransformSetting`. Settings are:

- Persisted to `~/.osintbuddy/`
- Merged from multiple sources (defaults, global, transform-specific, runtime)
- Validated before transform execution
- Displayed in the UI for user configuration

## Defining Settings

```python
from osintbuddy import transform, TransformSetting
from osintbuddy.settings import SettingType


@transform(
    target="domain@>=1.0.0",
    label="WHOIS Lookup",
    settings=[
        TransformSetting(
            name="api_key",
            display_name="API Key",
            setting_type=SettingType.PASSWORD,
            required=True,
            global_setting=True,
            description="Your WHOIS API key",
        ),
        TransformSetting(
            name="timeout",
            display_name="Timeout (seconds)",
            setting_type=SettingType.INT,
            default_value="30",
        ),
        TransformSetting(
            name="include_raw",
            display_name="Include Raw Response",
            setting_type=SettingType.BOOL,
            default_value="false",
        ),
    ],
)
async def whois_lookup(entity, cfg=None):
    api_key = cfg.get("api_key")
    timeout = int(cfg.get("timeout", 30))
    include_raw = cfg.get("include_raw") == "true"

    # Use settings...
```

## TransformSetting Attributes

| Attribute        | Type          | Default  | Description                  |
| ---------------- | ------------- | -------- | ---------------------------- |
| `name`           | `str`         | Required | Config key (used in code)    |
| `display_name`   | `str`         | Required | UI label                     |
| `setting_type`   | `SettingType` | Required | Validation type              |
| `default_value`  | `str`         | `""`     | Default value                |
| `required`       | `bool`        | `False`  | Whether setting is required  |
| `global_setting` | `bool`        | `False`  | Shared across all transforms |
| `description`    | `str`         | `""`     | Help text for users          |
| `popup`          | `bool`        | `False`  | Show in popup dialog         |

## Setting Types

| Type       | Description               | Example                   |
| ---------- | ------------------------- | ------------------------- |
| `STRING`   | Text string               | "value"                   |
| `INT`      | Integer number            | "42"                      |
| `FLOAT`    | Decimal number            | "3.14"                    |
| `BOOL`     | Boolean                   | "true" or "false"         |
| `URL`      | URL string                | "https://api.example.com" |
| `PASSWORD` | Sensitive string (masked) | "secret123"               |
| `DATE`     | Date                      | "2024-01-15"              |
| `DATETIME` | Date and time             | "2024-01-15T10:30:00"     |

## Storage Location

Settings are stored in `~/.osintbuddy/`:

```
~/.osintbuddy/
├── settings.json              # Global settings
└── transforms/
    ├── whois_lookup.json      # Transform-specific settings
    ├── dns_lookup.json
    └── screenshot.json
```

### Global Settings File

```json
{
  "api_key": "sk-abc123...",
  "default_timeout": "30"
}
```

### Transform Settings File

```json
{
  "include_raw": "true",
  "custom_server": "whois.example.com"
}
```

## Settings Resolution Order

Settings are merged in this order (later sources override earlier):

1. **Default values** - From `TransformSetting.default_value`
2. **Global settings** - From `~/.osintbuddy/settings.json` (if `global_setting=True`)
3. **Transform settings** - From `~/.osintbuddy/transforms/{name}.json`
4. **Runtime config** - Passed via `cfg` parameter or CLI `-C` flag

```python
@transform(target="domain@>=1.0.0", label="Lookup")
async def lookup(entity, cfg=None):
    # cfg contains merged settings from all sources
    value = cfg.get("key")
```

## SettingsManager

The `SettingsManager` class handles persistence and validation:

```python
from osintbuddy import get_settings_manager

manager = get_settings_manager()

# Load/save global settings
global_settings = manager.load_global_settings()
manager.save_global_settings({"api_key": "new-key"})

# Load/save transform settings
transform_settings = manager.load_transform_settings("whois_lookup")
manager.save_transform_settings("whois_lookup", {"timeout": "60"})

# Get/set individual settings
api_key = manager.get_setting("api_key", global_setting=True)
manager.set_setting("timeout", "60", transform_name="whois_lookup")
```

### Building Config

Build the merged config for a transform:

```python
from osintbuddy import TransformSetting, get_settings_manager
from osintbuddy.settings import SettingType

settings = [
    TransformSetting(
        name="api_key",
        display_name="API Key",
        setting_type=SettingType.PASSWORD,
        global_setting=True,
    ),
    TransformSetting(
        name="timeout",
        display_name="Timeout",
        setting_type=SettingType.INT,
        default_value="30",
    ),
]

manager = get_settings_manager()
config = manager.build_config(
    transform_name="my_transform",
    settings=settings,
    runtime_config={"timeout": "60"},  # Override from runtime
)

# config = {"api_key": "from-global", "timeout": "60"}
```

### Validating Config

Check that required settings are present:

```python
from osintbuddy import ConfigError

try:
    manager.validate_config(settings, config)
except ConfigError as e:
    print(f"Missing required setting: {e.details}")
```

## Complete Example

```python
from osintbuddy import (
    transform,
    Entity,
    Edge,
    TransformSetting,
    ConfigError,
    get_settings_manager,
)
from osintbuddy.settings import SettingType


# Define settings
SCREENSHOT_SETTINGS = [
    TransformSetting(
        name="api_key",
        display_name="Screenshot API Key",
        setting_type=SettingType.PASSWORD,
        required=True,
        global_setting=True,
        description="API key for the screenshot service",
    ),
    TransformSetting(
        name="resolution",
        display_name="Resolution",
        setting_type=SettingType.STRING,
        default_value="1920x1080",
        description="Screenshot resolution (WxH)",
    ),
    TransformSetting(
        name="full_page",
        display_name="Full Page",
        setting_type=SettingType.BOOL,
        default_value="false",
        description="Capture full scrollable page",
    ),
    TransformSetting(
        name="delay",
        display_name="Delay (ms)",
        setting_type=SettingType.INT,
        default_value="1000",
        description="Wait time before capture",
    ),
]


@transform(
    target="url@>=1.0.0",
    label="Take Screenshot",
    icon="camera",
    deps=["httpx"],
    settings=SCREENSHOT_SETTINGS,
)
async def take_screenshot(entity, cfg=None):
    """Capture a screenshot of the URL."""
    import httpx

    # Validate required settings
    if not cfg or not cfg.get("api_key"):
        raise ConfigError(
            "API key is required",
            details={"setting": "api_key"},
        )

    # Get settings with defaults
    api_key = cfg["api_key"]
    resolution = cfg.get("resolution", "1920x1080")
    full_page = cfg.get("full_page", "false") == "true"
    delay = int(cfg.get("delay", 1000))

    # Parse resolution
    width, height = resolution.split("x")

    # Call screenshot API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.screenshot.example.com/capture",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "url": entity.url,
                "width": int(width),
                "height": int(height),
                "full_page": full_page,
                "delay": delay,
            },
        )
        response.raise_for_status()
        result = response.json()

    return Entity(
        data=Screenshot.blueprint(
            url=entity.url,
            image_url=result["image_url"],
            captured_at=result["timestamp"],
        ),
        edge=Edge(label="screenshot of"),
    )


# Programmatically manage settings
def configure_screenshot_api(api_key: str):
    """Set up the screenshot API key globally."""
    manager = get_settings_manager()
    manager.set_setting("api_key", api_key, global_setting=True)
    print("API key saved to global settings")


def show_current_config():
    """Display current screenshot settings."""
    manager = get_settings_manager()
    config = manager.build_config("take_screenshot", SCREENSHOT_SETTINGS)

    print("Current configuration:")
    for key, value in config.items():
        # Mask sensitive values
        if "key" in key.lower() or "password" in key.lower():
            value = "***" if value else "(not set)"
        print(f"  {key}: {value}")
```

## CLI Usage

Pass runtime config via the `-C` flag:

```bash
ob transform '{"label": "url", "version": "1.0.0", "transform": "take_screenshot", "data": {"url": "https://example.com"}}' \
  -C '{"resolution": "1280x720", "full_page": "true"}'
```

## UI Integration

Settings with `popup=True` are displayed in a configuration popup before transform execution:

```python
TransformSetting(
    name="api_key",
    display_name="API Key",
    setting_type=SettingType.PASSWORD,
    required=True,
    popup=True,  # Show in popup dialog
    description="Enter your API key to continue",
)
```

## Next Steps

- [Transforms](transforms.md) - Using settings in transforms
- [CLI Reference](cli.md) - Passing config via command line
- [API Reference](api-reference.md) - SettingsManager API
