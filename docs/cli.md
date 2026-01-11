# CLI Reference

OSINTBuddy provides the `ob` command-line interface for managing plugins, running transforms, and integrating with the OSINTBuddy application.

## Installation

The CLI is installed automatically with the package:

```bash
pip install osintbuddy
ob --help
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `ob start` | Start the plugin microservice |
| `ob init` | Initialize default entities from GitHub |
| `ob transform` | Execute a transform |
| `ob entities` | List entities |
| `ob transforms` | List transforms for an entity |
| `ob ls plugins` | List all plugins |
| `ob entities json` | Get entity information as JSON |
| `ob blueprints` | Get entity blueprints |
| `ob compile` | Compile JSON entities to Python |

---

## ob start

Start the FastAPI microservice for the OSINTBuddy application.

```bash
ob start [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Path to plugins directory |
| `--port PORT` | Port number (default: 42562) |
| `--host HOST` | Host address (default: 127.0.0.1) |

### Examples

```bash
# Start with default settings
ob start

# Start with custom plugins directory
ob start -P /path/to/my-plugins

# Start on a different port
ob start --port 8080
```

The service exposes endpoints for:
- Listing entities
- Getting entity blueprints
- Running transforms
- Managing settings

---

## ob init

Download and initialize default entities from the OSINTBuddy GitHub repository.

```bash
ob init [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Destination path for plugins |

### Examples

```bash
# Initialize default plugins
ob init

# Initialize to a specific directory
ob init -P /path/to/plugins
```

---

## ob transform

Execute a transform on an entity.

```bash
ob transform TRANSFORM_JSON [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Plugins directory |
| `-C, --config JSON` | Runtime configuration |
| `--structured` | Use structured output with delimiters |

### Transform Payload Format

```json
{
  "label": "entity_label",
  "version": "1.0.0",
  "transform": "transform_name",
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

### Examples

```bash
# Basic transform
ob transform '{
  "label": "email",
  "version": "1.0.0",
  "transform": "extract_domain",
  "data": {"email": "user@example.com"}
}'

# With custom plugins directory
ob transform '{"label": "domain", "version": "1.0.0", "transform": "whois_lookup", "data": {"domain": "example.com"}}' \
  -P /path/to/plugins

# With runtime configuration
ob transform '{"label": "url", "version": "1.0.0", "transform": "screenshot", "data": {"url": "https://example.com"}}' \
  -C '{"resolution": "1280x720", "timeout": "60"}'

# Structured output for parsing
ob transform '...' --structured
```

### Structured Output

When using `--structured`, output is wrapped with delimiters:

**Success:**
```
---OSIB_JSON_START---
{"entities": [...], "edges": [...]}
---OSIB_JSON_END---
```

**Error:**
```
---OSIB_ERROR_START---
{"code": "TRANSFORM_FAILED", "message": "...", "details": {...}}
---OSIB_ERROR_END---
```

**Progress:**
```
---OSIB_PROGRESS---{"message": "Processing...", "percent": 50}
```

---

## ob entities

List entities (alias: `ob -e`).

```bash
ob entities [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Plugins directory |

```bash
ob entities
# Output:
# email (v1.0.0) - Email
# domain (v1.0.0) - Domain
# ip_address (v1.0.0) - IP Address
# ...
```

## ob transforms

List transforms for an entity (alias: `ob -t`).

```bash
ob transforms [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-L, --label LABEL` | Entity label to list transforms for |
| `-P, --plugins PATH` | Plugins directory |

**Note:** `-L` is required.

```bash
# List transforms for a specific entity
ob transforms -L email
# Output:
# email@>=1.0.0:
#   - extract_domain
#   - validate_email
#   - find_social_profiles
```

## ob ls plugins

```bash
ob ls plugins [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Plugins directory |

```bash
ob ls plugins
# Output:
# Loaded plugins from /path/to/plugins:
#   - email (v1.0.0)
#   - domain (v1.0.0)
#   - ip_address (v1.0.0)
```

---

## ob entities json

Get detailed entity information as JSON (for UI consumption).

```bash
ob entities json [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-P, --plugins PATH` | Plugins directory |

### Examples

```bash
ob entities json
```

Output:

```json
{
  "entities": [
    {
      "label": "Email",
      "entity_id": "email",
      "version": "1.0.0",
      "icon": "mail",
      "color": "#3B82F6",
      "category": "Identity",
      "description": "An email address",
      "tags": ["email", "identity"],
      "show_in_ui": true,
      "elements": [...]
    }
  ],
  "transforms": {
    "email": ["extract_domain", "validate_email"]
  }
}
```

---

## ob blueprints

Get entity blueprints for creating instances.

```bash
ob blueprints [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-L, --label LABEL` | Specific entity label |
| `-P, --plugins PATH` | Plugins directory |

### Examples

```bash
# Get all blueprints
ob blueprints

# Get blueprint for specific entity
ob blueprints -L email
```

Output:

```json
{
  "label": "Email",
  "entity_id": "email",
  "version": "1.0.0",
  "data": {},
  "elements": [
    {
      "type": "text",
      "label": "Email",
      "icon": "mail",
      "field_type": "email"
    }
  ]
}
```

---

## ob compile

Compile JSON entity definitions to Python code.

### Compile Single File

```bash
ob compile FILE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-O, --output PATH` | Output file path |
| `-V, --version VERSION` | Entity version (default: 1.0.0) |

```bash
# Compile to stdout
ob compile email.json

# Compile to file
ob compile email.json -O entities/email.py

# With specific version
ob compile email.json -O entities/email.py -V 2.0.0
```

### Compile Directory

```bash
ob compile dir DIRECTORY [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-O, --output PATH` | Output directory |
| `-V, --version VERSION` | Entity version (default: 1.0.0) |

```bash
# Compile all JSON files in a directory
ob compile dir json-entities/ -O entities/

# This will create:
# entities/email.py
# entities/domain.py
# entities/ip_address.py
# ...
```

### JSON Format

```json
{
  "label": "Email",
  "color": "#3B82F6",
  "icon": "mail",
  "description": "An email address",
  "category": "Identity",
  "tags": ["email", "identity"],
  "show_in_ui": true,
  "elements": [
    {
      "type": "text",
      "label": "Email",
      "icon": "mail",
      "field_type": "email"
    },
    {
      "type": "copy_text",
      "label": "Domain"
    }
  ]
}
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OSINTBUDDY_PLUGINS_PATH` | Default plugins directory |
| `OSINTBUDDY_CONFIG_DIR` | Settings directory (default: `~/.osintbuddy`) |

```bash
export OSINTBUDDY_PLUGINS_PATH=/path/to/plugins
ob entities  # Uses OSINTBUDDY_PLUGINS_PATH
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 10 | Plugin not found |
| 11 | Transform not found |
| 12 | Transform failed |
| 20 | Configuration error |
| 30 | Network error |

---

## Common Workflows

### Development Workflow

```bash
# 1. Create plugin directory
mkdir -p my-plugins/{entities,transforms}

# 2. Create entity JSON
cat > my-plugins/entities/email.json << 'EOF'
{
  "label": "Email",
  "elements": [{"type": "text", "label": "Email", "field_type": "email"}]
}
EOF

# 3. Compile to Python
ob compile my-plugins/entities/email.json -O my-plugins/entities/email.py

# 4. Create transform
cat > my-plugins/transforms/email_transforms.py << 'EOF'
from osintbuddy import transform, Entity

@transform(target="email@>=1.0.0", label="Test")
async def test_transform(entity):
    return Entity(data={"result": entity.email})
EOF

# 5. List plugins
ob entities -P my-plugins

# 6. Test transform
ob transform -P my-plugins '{"label": "email", "version": "1.0.0", "transform": "test", "data": {"email": "test@example.com"}}'
```

### Integration with Scripts

```bash
#!/bin/bash
# run_transform.sh

RESULT=$(ob transform "$1" --structured 2>&1)

if echo "$RESULT" | grep -q "OSIB_ERROR"; then
    # Handle error
    ERROR=$(echo "$RESULT" | sed -n '/OSIB_ERROR_START/,/OSIB_ERROR_END/p')
    echo "Transform failed: $ERROR"
    exit 1
fi

# Extract JSON result
JSON=$(echo "$RESULT" | sed -n '/OSIB_JSON_START/,/OSIB_JSON_END/p' | sed '1d;$d')
echo "$JSON" | jq .
```

### Batch Processing

```bash
#!/bin/bash
# batch_transforms.sh

DOMAINS=("example.com" "test.org" "sample.net")

for domain in "${DOMAINS[@]}"; do
    echo "Processing: $domain"
    ob transform "{\"label\": \"domain\", \"version\": \"1.0.0\", \"transform\": \"whois_lookup\", \"data\": {\"domain\": \"$domain\"}}" \
      --structured
done
```

---

## Troubleshooting

### Plugin Not Found

```
Error: PLUGIN_NOT_FOUND - Entity 'email' not found
```

**Solution:** Ensure the plugins directory is correct and contains the entity definition.

```bash
ob entities -P /path/to/plugins
```

### Transform Not Found

```
Error: TRANSFORM_NOT_FOUND - Transform 'unknown' not found for entity 'email@1.0.0'
```

**Solution:** List available transforms for the entity.

```bash
ob transforms -L email
```

### Dependency Missing

```
Error: DEPENDENCY_MISSING - Package 'requests' is required
```

**Solution:** The dependency should auto-install. If not, install manually:

```bash
pip install requests
```

### Configuration Error

```
Error: CONFIG_INVALID - Missing required setting 'api_key'
```

**Solution:** Provide the setting via `-C` or save it to settings:

```bash
ob transform '...' -C '{"api_key": "your-key"}'
```

## Next Steps

- [Getting Started](getting-started.md) - First steps with OSINTBuddy
- [Transforms](transforms.md) - Creating transforms
- [Settings](settings.md) - Configuration management
- [API Reference](api-reference.md) - Complete API documentation
