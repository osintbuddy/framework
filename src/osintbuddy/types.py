"""Standard field types for OSINTBuddy entities.

Field types enable type-based transform matching, allowing transforms to
declare what types of data they accept and produce rather than being
tightly coupled to specific entity implementations.

.. note:: Type-Based Matching Status

    The field_type system provides infrastructure for future type-based
    transform matching. Currently, transforms are matched by entity_id
    and version only. The `accepts` and `produces` parameters are stored
    but not yet used for automatic matching.

    **Current functionality:**
    - field_type values are serialized to entity blueprints
    - get_field_type() can infer types from string values
    - are_types_compatible() checks type compatibility

    **Future functionality (planned):**
    - Automatic transform matching based on field types
    - entity.get_typed_field() to retrieve fields by type
    - Cross-entity transforms that work with any compatible entity

    Plugin developers are encouraged to add field_types for future
    compatibility but should not rely on type-based matching yet.

Example usage in entity definition:
    class EmailEntity(ob.Plugin):
        elements = [
            TextInput(label="Email", field_type=FieldType.EMAIL),
            TextInput(label="Name", field_type=FieldType.PERSON_NAME),
        ]

Example usage in transform (future):
    @transform(
        target="*",  # Match any entity (future)
        accepts=[FieldType.EMAIL],
        produces=[FieldType.SOCIAL_PROFILE, FieldType.WEBSITE],
        label="Find Social Profiles"
    )
    async def find_social(entity):
        email = entity.get_typed_field(FieldType.EMAIL)
        ...
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class FieldType(str, Enum):
    """Standard field types for OSINT data.

    These types enable semantic matching between entities and transforms,
    allowing transforms to work with any entity that has compatible fields.
    """

    # Identity types
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    PERSON_NAME = "person_name"
    ORGANIZATION = "organization"
    ALIAS = "alias"

    # Network types
    IP_ADDRESS = "ip_address"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    MAC_ADDRESS = "mac_address"
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    URL = "url"
    PORT = "port"

    # Location types
    ADDRESS = "address"
    CITY = "city"
    COUNTRY = "country"
    COORDINATES = "coordinates"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

    # Social types
    SOCIAL_PROFILE = "social_profile"
    SOCIAL_HANDLE = "social_handle"
    SOCIAL_PLATFORM = "social_platform"

    # Document types
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    FILE_PATH = "file_path"
    FILE_NAME = "file_name"

    # Financial types
    BITCOIN_ADDRESS = "bitcoin_address"
    ETHEREUM_ADDRESS = "ethereum_address"
    CRYPTO_ADDRESS = "crypto_address"
    CREDIT_CARD = "credit_card"
    IBAN = "iban"

    # Technical types
    CVE = "cve"
    ASN = "asn"
    CIDR = "cidr"
    SSL_CERT = "ssl_cert"
    API_KEY = "api_key"

    # Generic types
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"
    NOTES = "notes"

    # Custom/unknown
    CUSTOM = "custom"


# Type compatibility groups - types that can be used interchangeably
TYPE_COMPATIBILITY = {
    FieldType.IP_ADDRESS: {FieldType.IPV4, FieldType.IPV6},
    FieldType.HASH_SHA256: {FieldType.HASH_MD5, FieldType.HASH_SHA1},
}


def are_types_compatible(source: FieldType, target: FieldType) -> bool:
    """Check if two field types are compatible.

    A source type is compatible with a target if:
    - They are the same type
    - Source is in target's compatibility group
    - Target is a generic type that accepts source

    Args:
        source: The field type being provided
        target: The field type being requested

    Returns:
        True if compatible, False otherwise
    """
    if source == target:
        return True

    # Check compatibility groups
    if target in TYPE_COMPATIBILITY:
        if source in TYPE_COMPATIBILITY[target]:
            return True

    # Generic TEXT accepts most string-based types
    if target == FieldType.TEXT:
        return source not in {FieldType.NUMBER, FieldType.JSON, FieldType.COORDINATES}

    return False


def get_field_type(value: str) -> FieldType:
    """Attempt to infer field type from a string value.

    Args:
        value: The string value to analyze

    Returns:
        Best-guess FieldType for the value
    """
    import re

    value = value.strip()

    # Email pattern
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
        return FieldType.EMAIL

    # IPv4 pattern
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', value):
        return FieldType.IPV4

    # IPv6 pattern (simplified)
    if re.match(r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$', value):
        return FieldType.IPV6

    # Domain pattern
    if re.match(r'^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$', value):
        return FieldType.DOMAIN

    # URL pattern
    if re.match(r'^https?://', value):
        return FieldType.URL

    # Phone pattern (basic)
    if re.match(r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3,}[-\s\.]?[0-9]{4,}$', value):
        return FieldType.PHONE

    # Hash patterns
    if re.match(r'^[a-fA-F0-9]{32}$', value):
        return FieldType.HASH_MD5
    if re.match(r'^[a-fA-F0-9]{40}$', value):
        return FieldType.HASH_SHA1
    if re.match(r'^[a-fA-F0-9]{64}$', value):
        return FieldType.HASH_SHA256

    # Bitcoin address pattern
    if re.match(r'^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$', value):
        return FieldType.BITCOIN_ADDRESS

    # CVE pattern
    if re.match(r'^CVE-\d{4}-\d{4,}$', value, re.IGNORECASE):
        return FieldType.CVE

    # Default to text
    return FieldType.TEXT


class TypedValue:
    """A value with an associated field type.

    Used for type-safe field access in transforms.
    """

    def __init__(self, value: Any, field_type: FieldType, label: str = ""):
        self.value = value
        self.field_type = field_type
        self.label = label

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"TypedValue({self.value!r}, {self.field_type})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "field_type": self.field_type.value,
            "label": self.label,
        }
