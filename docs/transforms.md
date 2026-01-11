# Transforms

Transforms are async functions that operate on entities to produce new entities, files, or subgraphs. They appear in the context menu when you right-click a node in OSINTBuddy.

## Basic Transform

```python
from osintbuddy import transform, Entity, Edge


@transform(
    target="email@>=1.0.0",
    label="Extract Domain",
)
async def extract_domain(entity):
    """Extract the domain portion of an email address."""
    email = entity.email

    if not email or "@" not in email:
        return None

    domain = email.split("@")[1]

    return Entity(
        data=DomainEntity.blueprint(domain=domain),
        edge=Edge(label="has domain"),
    )
```

## Decorator Parameters

| Parameter       | Type                     | Required | Description                          |
| --------------- | ------------------------ | -------- | ------------------------------------ |
| `target`        | `str`                    | Yes      | Entity ID with optional version spec |
| `label`         | `str`                    | Yes      | Display name in context menu         |
| `icon`          | `str`                    | No       | Icon identifier                      |
| `edge_label`    | `str`                    | No       | Default edge label for results       |
| `deps`          | `list[str]`              | No       | Python package dependencies          |
| `settings`      | `list[TransformSetting]` | No       | Configuration options                |
| `transform_set` | `TransformSet`           | No       | Grouping for organization            |
| `accepts`       | `list[str]`              | No       | Field types this transform accepts   |
| `produces`      | `list[str]`              | No       | Field types this transform produces  |

## Version Targeting

The `target` parameter uses semantic versioning with specifiers:

```python
# Exact version
@transform(target="email@1.0.0", label="V1 Only")

# Minimum version
@transform(target="email@>=1.0.0", label="V1 and above")

# Version range
@transform(target="email@>=1.0.0,<2.0.0", label="V1.x only")

# Any version (no specifier)
@transform(target="email", label="All versions")
```

Version specifiers follow [PEP 440](https://peps.python.org/pep-0440/#version-specifiers):

- `>=1.0.0` - Greater than or equal
- `<=1.0.0` - Less than or equal
- `>1.0.0` - Greater than
- `<1.0.0` - Less than
- `==1.0.0` - Exact match
- `!=1.0.0` - Not equal
- `~=1.0.0` - Compatible release

## Entity Access

The `entity` parameter is a `TransformPayload` with field access:

```python
@transform(target="person@>=1.0.0", label="Search")
async def search_person(entity):
    # Access fields via snake_case attributes
    full_name = entity.full_name
    first_name = entity.first_name
    last_name = entity.last_name

    # Or use get_field() for dynamic access
    field = entity.get_field("Full Name")

    # Get by field type
    email = entity.get_typed_field("email")
```

## Returning Results

### Single Entity

```python
return Entity(
    data=TargetEntity.blueprint(field="value"),
    edge=Edge(label="discovered"),
)
```

### Multiple Entities

```python
return [
    Entity(data=Result1.blueprint(...), edge=Edge(label="result 1")),
    Entity(data=Result2.blueprint(...), edge=Edge(label="result 2")),
]
```

## Streaming Results & Progress

Long-running transforms can stream results incrementally and emit progress updates.
Use an async generator to yield results, and `emit_progress` for UI progress.

```python
from osintbuddy import transform, Entity, emit_progress

@transform(target="domain@>=1.0.0", label="Bulk Lookup")
async def bulk_lookup(entity):
    domains = entity.domains or []
    total = max(len(domains), 1)
    for idx, domain in enumerate(domains, start=1):
        emit_progress(f"Looking up {domain}", int((idx / total) * 100))
        yield Entity(data=DomainResult.blueprint(domain=domain))
```

### With Custom Edge Styling

```python
return Entity(
    data=Alert.blueprint(severity="high"),
    edge=Edge(
        label="triggered alert",
        color="#EF4444",
        style="dashed",
        width=3,
        animated=True,
        properties={"severity": "high"},
    ),
)
```

### With File Attachments

```python
from osintbuddy import File

return Entity(
    data=Report.blueprint(title="Analysis Report"),
    files=[
        File(path="/tmp/report.pdf", label="PDF Report", mime_type="application/pdf"),
        File(path="/tmp/data.json", label="Raw Data"),
    ],
)
```

### Complex Subgraphs

```python
from osintbuddy import Subgraph

# Create a connected graph structure
entity1 = Entity(data=Server.blueprint(ip="192.168.1.1"))
entity2 = Entity(data=Domain.blueprint(domain="example.com"))
entity3 = Entity(data=Certificate.blueprint(issuer="Let's Encrypt"))

return Subgraph(
    entities=[entity1, entity2, entity3],
    edges=[
        ("entity1_id", "entity2_id", Edge(label="hosts")),
        ("entity2_id", "entity3_id", Edge(label="has certificate")),
    ],
)
```

### Nested Entities (Children)

```python
# Entities can have children for hierarchical data
return Entity(
    data=Organization.blueprint(name="Acme Corp"),
    children=[
        Entity(data=Person.blueprint(name="CEO")),
        Entity(data=Person.blueprint(name="CTO")),
    ],
)
```

### Legacy Dict Format

Plain dictionaries still work for backwards compatibility:

```python
# Simple return
return TargetEntity.blueprint(field="value")

# Multiple results
return [
    TargetEntity.create(field="value1"),
    TargetEntity.create(field="value2"),
]
```

## Dependencies

Specify required packages that will be auto-installed:

```python
@transform(
    target="domain@>=1.0.0",
    label="WHOIS Lookup",
    deps=["python-whois>=0.8.0"],
)
async def whois_lookup(entity):
    import whois  # Safely import after deps are installed

    result = whois.whois(entity.domain)
    return Entity(data=WhoisRecord.blueprint(**result))
```

## Configuration with Settings

Define configurable settings for your transform:

```python
from osintbuddy import TransformSetting
from osintbuddy.settings import SettingType


@transform(
    target="domain@>=1.0.0",
    label="Screenshot Website",
    settings=[
        TransformSetting(
            name="resolution",
            display_name="Screenshot Resolution",
            setting_type=SettingType.STRING,
            default_value="1920x1080",
            description="Width x Height in pixels",
        ),
        TransformSetting(
            name="api_key",
            display_name="API Key",
            setting_type=SettingType.PASSWORD,
            required=True,
            global_setting=True,  # Shared across transforms
        ),
        TransformSetting(
            name="timeout",
            display_name="Timeout (seconds)",
            setting_type=SettingType.INT,
            default_value="30",
        ),
    ],
)
async def screenshot_website(entity, cfg=None):
    resolution = cfg.get("resolution", "1920x1080")
    api_key = cfg.get("api_key")
    timeout = int(cfg.get("timeout", 30))

    # Use settings...
```

Settings are persisted in `~/.osintbuddy/transforms/`.

## Transform Sets

Group related transforms for organization:

```python
from osintbuddy.sets import TransformSet, NETWORK, SOCIAL_MEDIA

# Use built-in sets
@transform(
    target="ip_address@>=1.0.0",
    label="Reverse DNS",
    transform_set=NETWORK,
)
async def reverse_dns(entity):
    ...

# Or create custom sets
MY_CUSTOM_SET = TransformSet(
    name="custom_recon",
    description="Custom reconnaissance transforms",
    icon="radar",
)

@transform(
    target="domain@>=1.0.0",
    label="Custom Recon",
    transform_set=MY_CUSTOM_SET,
)
async def custom_recon(entity):
    ...
```

Built-in sets:

- `OSINT_CORE` - Core reconnaissance
- `SOCIAL_MEDIA` - Social platforms
- `NETWORK` - Infrastructure
- `IDENTITY` - Person/org related
- `THREAT_INTEL` - Security
- `DOCUMENTS` - File analysis
- `GEOLOCATION` - Location/mapping
- `CRYPTOCURRENCY` - Blockchain

## Type-Based Matching

Transforms can declare which field types they accept:

```python
@transform(
    target="*",  # Match any entity
    label="Validate Email",
    accepts=["email"],  # Only show for entities with email fields
    produces=["email"],
)
async def validate_email(entity):
    email = entity.get_typed_field("email")
    # Validate and return...
```

## Error Handling

Use structured exceptions for proper error reporting:

```python
from osintbuddy import (
    PluginError,
    NetworkError,
    RateLimitError,
    AuthError,
    ConfigError,
)


@transform(target="domain@>=1.0.0", label="API Lookup")
async def api_lookup(entity, cfg=None):
    api_key = cfg.get("api_key") if cfg else None

    if not api_key:
        raise ConfigError("API key is required", details={"setting": "api_key"})

    try:
        result = await call_api(entity.domain, api_key)
    except httpx.ConnectError:
        raise NetworkError(f"Failed to connect to API for {entity.domain}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise RateLimitError("API rate limit exceeded")
        elif e.response.status_code == 401:
            raise AuthError("Invalid API key")
        raise PluginError(f"API error: {e.response.status_code}")

    return Entity(data=Result.blueprint(**result))
```

## UI Messages

Send feedback to the user during transform execution:

```python
from osintbuddy import TransformResponse, UIMessage, MessageType


@transform(target="domain@>=1.0.0", label="Deep Scan")
async def deep_scan(entity):
    response = TransformResponse()

    response.info("Starting deep scan...")

    results = await perform_scan(entity.domain)

    if not results:
        response.warning("No results found for this domain")
        return response

    for result in results:
        response.add_entity(Entity(data=Result.blueprint(**result)))

    response.success(f"Found {len(results)} results")

    return response
```

## Progress Reporting

For long-running transforms:

```python
from osintbuddy import emit_progress, ProgressEmitter


@transform(target="domain@>=1.0.0", label="Full Enumeration")
async def full_enumeration(entity):
    results = []

    with ProgressEmitter("Enumeration") as progress:
        progress.update("Checking DNS...", 0)
        dns_results = await check_dns(entity.domain)
        results.extend(dns_results)

        progress.update("Scanning ports...", 33)
        port_results = await scan_ports(entity.domain)
        results.extend(port_results)

        progress.update("Checking certificates...", 66)
        cert_results = await check_certs(entity.domain)
        results.extend(cert_results)

        progress.complete()

    return [Entity(data=r) for r in results]
```

## Collision Detection

The registry prevents duplicate transforms for the same target:

```python
# First registration works
@transform(target="email@>=1.0.0", label="Lookup")
async def email_lookup(entity):
    ...

# This raises TransformCollisionError
@transform(target="email@>=1.0.0", label="Lookup")  # Same label!
async def email_lookup_v2(entity):
    ...
```

Use different labels or version specs to avoid collisions.

## Complete Example

```python
from osintbuddy import (
    transform,
    Entity,
    Edge,
    File,
    TransformSetting,
    TransformResponse,
    NetworkError,
)
from osintbuddy.sets import NETWORK


@transform(
    target="domain@>=1.0.0",
    label="Full Domain Report",
    icon="file-report",
    deps=["python-whois", "dnspython"],
    transform_set=NETWORK,
    settings=[
        TransformSetting(
            name="include_subdomains",
            display_name="Include Subdomains",
            setting_type="bool",
            default_value="true",
        ),
    ],
)
async def full_domain_report(entity, cfg=None):
    """Generate a comprehensive domain report."""
    import whois
    import dns.resolver

    response = TransformResponse()
    response.info(f"Analyzing {entity.domain}...")

    try:
        # WHOIS lookup
        whois_data = whois.whois(entity.domain)

        # DNS records
        dns_records = {}
        for record_type in ["A", "AAAA", "MX", "NS", "TXT"]:
            try:
                answers = dns.resolver.resolve(entity.domain, record_type)
                dns_records[record_type] = [str(r) for r in answers]
            except dns.resolver.NoAnswer:
                pass

        # Create report entity
        report_entity = Entity(
            data=DomainReport.blueprint(
                domain=entity.domain,
                registrar=whois_data.registrar,
                creation_date=str(whois_data.creation_date),
                dns_records=dns_records,
            ),
            edge=Edge(label="report for", color="#22C55E"),
        )

        # Add IP entities as children
        if "A" in dns_records:
            for ip in dns_records["A"]:
                report_entity.children.append(
                    Entity(data=IPAddress.blueprint(ip=ip))
                )

        response.add_entity(report_entity)
        response.success("Report generated successfully")

    except Exception as e:
        raise NetworkError(f"Failed to analyze domain: {e}")

    return response
```

## Next Steps

- [Elements](elements.md) - Form elements for entities
- [Field Types](types.md) - Type system for matching
- [Settings](settings.md) - Configuration framework
- [CLI Reference](cli.md) - Running transforms from command line
