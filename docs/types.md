# Field Types

Field types provide semantic meaning to entity fields, enabling type inference and laying the groundwork for future type-based transform matching.

## Status

> **Note:** The field_type system is currently **infrastructure for future functionality**. While you can assign field types to elements and transforms can declare `accepts`/`produces`, automatic type-based transform matching is not yet implemented. Transforms are currently matched by `entity_id` and `version` only.
>
> **What works now:**
> - Assigning `field_type` to elements (serialized to blueprints)
> - `get_field_type()` for inferring types from string values
> - `are_types_compatible()` for checking type relationships
> - `accepts`/`produces` stored on transforms (for future use)
>
> **Coming in future releases:**
> - `entity.get_typed_field()` to retrieve fields by type
> - Automatic transform matching based on field types
> - Cross-entity transforms with `target="*"`
>
> Plugin developers are encouraged to add field_types for forward compatibility.

## Overview

Field types allow transforms to work with any entity that contains a matching field type, rather than being tied to specific entity definitions.

```python
from osintbuddy.types import FieldType
from osintbuddy.elements import TextInput

# Define an entity with typed fields
elements = [
    TextInput(label="Email", field_type=FieldType.EMAIL),
    TextInput(label="Phone", field_type=FieldType.PHONE),
]

# Future: Transform will target field types
@transform(
    target="email@>=1.0.0",  # Currently required
    label="Validate Email",
    accepts=["email"],  # Stored for future matching
)
async def validate_email(entity):
    # Currently: access by attribute name
    email = entity.email
    # Future: email = entity.get_typed_field("email")
```

## Available Field Types

### Identity

| Type | Description | Example |
|------|-------------|---------|
| `EMAIL` | Email address | user@example.com |
| `PHONE` | Phone number | +1-555-123-4567 |
| `USERNAME` | Username/handle | johndoe |
| `PERSON_NAME` | Full person name | John Doe |
| `ORGANIZATION` | Organization name | Acme Corporation |
| `ALIAS` | Alternative name/alias | JD |

### Network

| Type | Description | Example |
|------|-------------|---------|
| `IP_ADDRESS` | IPv4 or IPv6 address | 192.168.1.1 |
| `IPV4` | IPv4 address | 192.168.1.1 |
| `IPV6` | IPv6 address | 2001:db8::1 |
| `MAC_ADDRESS` | MAC address | 00:1A:2B:3C:4D:5E |
| `DOMAIN` | Domain name | example.com |
| `SUBDOMAIN` | Subdomain | api.example.com |
| `URL` | Full URL | https://example.com/path |
| `PORT` | Port number | 443 |

### Location

| Type | Description | Example |
|------|-------------|---------|
| `ADDRESS` | Physical address | 123 Main St |
| `CITY` | City name | New York |
| `COUNTRY` | Country name/code | United States |
| `COORDINATES` | Lat/long pair | 40.7128,-74.0060 |
| `LATITUDE` | Latitude | 40.7128 |
| `LONGITUDE` | Longitude | -74.0060 |

### Social Media

| Type | Description | Example |
|------|-------------|---------|
| `SOCIAL_PROFILE` | Profile URL | https://twitter.com/user |
| `SOCIAL_HANDLE` | Social handle | @username |
| `SOCIAL_PLATFORM` | Platform name | Twitter |

### Documents & Files

| Type | Description | Example |
|------|-------------|---------|
| `HASH_MD5` | MD5 hash | d41d8cd98f00b204... |
| `HASH_SHA1` | SHA-1 hash | da39a3ee5e6b4b0d... |
| `HASH_SHA256` | SHA-256 hash | e3b0c44298fc1c14... |
| `FILE_PATH` | File path | /home/user/doc.pdf |
| `FILE_NAME` | File name | document.pdf |

### Financial

| Type | Description | Example |
|------|-------------|---------|
| `BITCOIN_ADDRESS` | Bitcoin address | 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa |
| `ETHEREUM_ADDRESS` | Ethereum address | 0x742d35Cc6634C0532925a3b844Bc9e7595f... |
| `CRYPTO_ADDRESS` | Any crypto address | (various formats) |
| `CREDIT_CARD` | Credit card number | 4111111111111111 |
| `IBAN` | IBAN number | DE89370400440532013000 |

### Technical

| Type | Description | Example |
|------|-------------|---------|
| `CVE` | CVE identifier | CVE-2021-44228 |
| `ASN` | AS number | AS15169 |
| `CIDR` | CIDR notation | 192.168.0.0/24 |
| `SSL_CERT` | SSL certificate | (PEM format) |
| `API_KEY` | API key | sk-abc123... |

### Generic

| Type | Description | Example |
|------|-------------|---------|
| `TEXT` | Generic text | Any text |
| `NUMBER` | Numeric value | 42 |
| `DATE` | Date | 2024-01-15 |
| `DATETIME` | Date and time | 2024-01-15T10:30:00Z |
| `JSON` | JSON data | {"key": "value"} |
| `NOTES` | Notes/comments | Free-form text |
| `CUSTOM` | Custom type | User-defined |

## Using Field Types

### In Entity Definitions

```python
from osintbuddy import Plugin
from osintbuddy.elements import TextInput
from osintbuddy.types import FieldType


class NetworkAsset(Plugin):
    version = "1.0.0"
    label = "Network Asset"

    elements = [
        TextInput(label="Hostname", field_type=FieldType.DOMAIN),
        TextInput(label="IP Address", field_type=FieldType.IP_ADDRESS),
        TextInput(label="MAC", field_type=FieldType.MAC_ADDRESS),
        TextInput(label="Port", field_type=FieldType.PORT),
    ]
```

### In Transforms

Access typed fields in transform functions:

```python
@transform(target="network_asset@>=1.0.0", label="Scan")
async def scan_asset(entity):
    # Get by field type (returns first matching field)
    ip = entity.get_typed_field("ip_address")
    port = entity.get_typed_field("port")

    # Or access by label (snake_case)
    hostname = entity.hostname
```

### Type-Based Transform Matching

Declare which types a transform accepts:

```python
@transform(
    target="*",  # Any entity
    label="GeoIP Lookup",
    accepts=["ip_address", "ipv4", "ipv6"],
    produces=["coordinates", "city", "country"],
)
async def geoip_lookup(entity):
    ip = entity.get_typed_field("ip_address")
    # Lookup and return location entity
```

## Type Compatibility

Some types are compatible with each other:

```python
from osintbuddy.types import are_types_compatible, TYPE_COMPATIBILITY

# IP_ADDRESS is compatible with IPV4 and IPV6
are_types_compatible(FieldType.IP_ADDRESS, FieldType.IPV4)  # True

# HASH_SHA256 is compatible with other hash types
are_types_compatible(FieldType.HASH_SHA256, FieldType.HASH_MD5)  # True
```

Compatibility rules:

| Parent Type | Compatible With |
|-------------|----------------|
| `IP_ADDRESS` | `IPV4`, `IPV6` |
| `HASH_SHA256` | `HASH_MD5`, `HASH_SHA1` |
| `CRYPTO_ADDRESS` | `BITCOIN_ADDRESS`, `ETHEREUM_ADDRESS` |

## Type Inference

The framework can automatically detect field types from values:

```python
from osintbuddy.types import get_field_type

# Automatic detection
get_field_type("user@example.com")        # FieldType.EMAIL
get_field_type("192.168.1.1")             # FieldType.IPV4
get_field_type("example.com")             # FieldType.DOMAIN
get_field_type("https://example.com")     # FieldType.URL
get_field_type("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # FieldType.BITCOIN_ADDRESS
get_field_type("CVE-2021-44228")          # FieldType.CVE
```

Detection patterns:

| Pattern | Detected Type |
|---------|--------------|
| Email regex | `EMAIL` |
| IPv4 format | `IPV4` |
| IPv6 format | `IPV6` |
| URL scheme | `URL` |
| Domain pattern | `DOMAIN` |
| MD5 (32 hex) | `HASH_MD5` |
| SHA-1 (40 hex) | `HASH_SHA1` |
| SHA-256 (64 hex) | `HASH_SHA256` |
| CVE pattern | `CVE` |
| Bitcoin address | `BITCOIN_ADDRESS` |
| Ethereum address | `ETHEREUM_ADDRESS` |

## TypedValue Wrapper

For explicit type annotation:

```python
from osintbuddy.types import TypedValue, FieldType

# Wrap a value with its type
typed_email = TypedValue(
    value="user@example.com",
    field_type=FieldType.EMAIL
)

print(typed_email.value)       # "user@example.com"
print(typed_email.field_type)  # FieldType.EMAIL
```

## Getting Field Types from Entities

Retrieve the field type mapping for a plugin:

```python
from osintbuddy import Registry

EmailEntity = Registry.get_entity("email")
field_types = EmailEntity.get_field_types()

# Returns: {"email": FieldType.EMAIL, "domain": FieldType.DOMAIN, ...}
```

## Complete Example

```python
from osintbuddy import Plugin, transform, Entity, Edge
from osintbuddy.elements import TextInput, CopyText
from osintbuddy.types import FieldType, get_field_type


class UniversalEntity(Plugin):
    """A flexible entity that can hold various data types."""
    version = "1.0.0"
    label = "Universal"
    category = "Generic"

    elements = [
        TextInput(label="Value", field_type=FieldType.TEXT),
        CopyText(label="Detected Type"),
    ]


class TypedEntity(Plugin):
    """Entity with strongly typed fields."""
    version = "1.0.0"
    label = "Typed Data"

    elements = [
        TextInput(label="Email", field_type=FieldType.EMAIL),
        TextInput(label="IP", field_type=FieldType.IP_ADDRESS),
        TextInput(label="Domain", field_type=FieldType.DOMAIN),
    ]


@transform(
    target="universal@>=1.0.0",
    label="Detect Type",
    icon="search",
)
async def detect_type(entity):
    """Detect the field type from the value."""
    value = entity.value
    detected = get_field_type(value)

    return Entity(
        data=UniversalEntity.blueprint(
            value=value,
            detected_type=detected.value if detected else "unknown",
        ),
        edge=Edge(label="analyzed"),
    )


@transform(
    target="*",
    label="Extract Emails",
    accepts=["text", "notes"],
    produces=["email"],
)
async def extract_emails(entity):
    """Extract email addresses from any text field."""
    import re

    text = entity.get_typed_field("text") or entity.get_typed_field("notes")
    if not text:
        return None

    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)

    return [
        Entity(
            data=EmailOnlyEntity.blueprint(email=email),
            edge=Edge(label="extracted from"),
        )
        for email in set(emails)
    ]
```

## Next Steps

- [Elements](elements.md) - Using field types with form elements
- [Transforms](transforms.md) - Type-based transform matching
- [Plugins](plugins.md) - Entity definitions with typed fields
