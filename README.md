## Introducing OSINTBuddy: Reloaded

<p>
  <a href="https://github.com/osintbuddy/osintbuddy">
    <img src="./watermark.svg" height="130px" alt="Logo">
  </a>

> _I have no data yet. It is a capital mistake to theorize before one has data. Insensibly
> one begins to twist facts to suit theories, instead of theories to suit facts._

---

# The OSINTBuddy Plugins Framework

[![PyPI version](https://badge.fury.io/py/osintbuddy.svg)](https://pypi.org/project/osintbuddy/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The plugin framework for [OSINTBuddy](https://github.com/osintbuddy/osintbuddy), a graph-based OSINT platform for recon, OSINT investigations, link analysis, and more. Offline. Local-first workflows. No cloud dependency.

## Overview

OSINTBuddy's plugin system enables you to define **entities** (_nodes in the graph_) and **transforms** (_operations that create new entities from existing ones_). The framework provides:

- **Entity definitions** with rich metadata, icons, colors, and form elements
- **Transform decorators** with dependency management and version targeting
- **Result types** for subgraphs, custom edges, and file attachments
- **Field types** for semantic type-based transform matching
- **Settings framework** for persistent configuration
- **CLI tools** for development and integration

## Installation

```bash
pip install osintbuddy[all]
```

For development:

```bash
git clone https://github.com/osintbuddy/plugins.git
cd plugins/
pip install -e ".[dev]"
```

## Quick Start

### Define an Entity

```python
from osintbuddy import Plugin
from osintbuddy.elements import TextInput, CopyText
from osintbuddy.types import FieldType

class EmailEntity(Plugin):
    version = "1.0.0"
    label = "Email"
    icon = "mail"
    color = "#3B82F6"
    category = "Identity"

    elements = [
        TextInput(label="Email", icon="mail", field_type=FieldType.EMAIL),
        CopyText(label="Domain"),
    ]
```

### Create a Transform

```python
from osintbuddy import transform, Entity, Edge

@transform(
    target="email@>=1.0.0",
    label="Extract Domain",
    icon="world",
)
async def extract_domain(entity):
    email = entity.email
    domain = email.split("@")[1] if "@" in email else None

    if domain:
        return Entity(
            data=DomainEntity.blueprint(domain=domain),
            edge=Edge(label="has domain"),
        )
```

### Run a Transform

```bash
ob run -T '{"label": "email", "version": "1.0.0", "transform": "extract_domain", "data": {"email": "user@example.com"}}'
```

## Documentation

| Guide                                      | Description                                         |
| ------------------------------------------ | --------------------------------------------------- |
| [Getting Started](docs/getting-started.md) | Installation, project setup, and first plugin       |
| [Plugins & Entities](docs/plugins.md)      | Defining entities with the Plugin class             |
| [Transforms](docs/transforms.md)           | Creating transforms with the `@transform` decorator |
| [Elements](docs/elements.md)               | Input and display elements for entity forms         |
| [Field Types](docs/types.md)               | Semantic types for fields and type-based matching   |
| [Settings](docs/settings.md)               | Transform configuration and persistence             |
| [CLI Reference](docs/cli.md)               | Command-line interface documentation                |
| [API Reference](docs/api-reference.md)     | Complete API documentation                          |

## Key Concepts

### Plugins & Entities

Every node type in the graph is defined as a `Plugin` subclass. Plugins are automatically registered when defined:

```python
class IPAddress(Plugin):
    version = "1.0.0"
    label = "IP Address"
    elements = [TextInput(label="IP", field_type=FieldType.IP_ADDRESS)]
```

### Transforms

Transforms operate on entities to produce new entities. They target specific entity versions:

```python
@transform(target="ip_address@>=1.0.0", label="GeoIP Lookup", deps=["geoip2"])
async def geoip_lookup(entity):
    # Transform logic
    return Entity(data=Location.blueprint(city="..."))
```

### Result Types

Transforms return `Entity`, `Edge`, `File`, or `Subgraph` objects:

```python
return Entity(
    data=TargetEntity.blueprint(field="value"),
    edge=Edge(label="discovered", color="#22C55E"),
    files=[File(path="/tmp/report.pdf")],
)
```

## Project Structure

For plugin development and registry submissions, organize your code as:

```
my-plugins-repo/
├── entities/
│   ├── email.py
│   ├── domain.py
│   └── ip_address.py
└── transforms/
    ├── email_transforms.py
    ├── domain_transforms.py
    ├── network_traceroute_transform.py
    └── network_transforms.py
```

Load plugins via:

```python
from osintbuddy import load_plugins_fs
load_plugins_fs("/path/to/my-plugins", "my_plugins")
```

## CLI Commands

```bash
# List entities and transforms
ob ls entities
ob ls transforms -L email

# Run a transform
ob transform '{"label": "email", "version": "1.0.0", "transform": "to_domain", "data": {...}}'

# Get entity blueprints
ob blueprints -L email

# Compile JSON entity to Python
ob compile entity.json -O entity.py
```

## Requirements

- Python 3.12+

## License

MIT License, see [LICENSE](LICENSE) for details.

## Links

<!-- - [Documentation](https://docs.osintbuddy.com/) -->

- [OSINTBuddy Application](https://github.com/osintbuddy/osintbuddy)
- [Issue Tracker](https://github.com/osintbuddy/osintbuddy/issues)
