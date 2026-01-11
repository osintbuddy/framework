"""Transform sets for OSINTBuddy.

Transform sets allow grouping related transforms together for
organization and bulk operations.

Example usage:
    from osintbuddy.sets import TransformSet

    RECON_SET = TransformSet(
        name="Reconnaissance",
        description="Initial reconnaissance transforms"
    )

    @transform(
        target="website@1.0.0",
        label="DNS Lookup",
        transform_set=RECON_SET
    )
    async def dns_lookup(entity):
        ...
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class TransformSet:
    """A logical grouping of related transforms.

    Attributes:
        name: Unique name for the set
        description: Human-readable description
        icon: Icon identifier for UI display
    """
    name: str
    description: str = ""
    icon: str = "folder"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


# Built-in transform sets
OSINT_CORE = TransformSet(
    name="OSINT Core",
    description="Core OSINT reconnaissance transforms",
    icon="search"
)

SOCIAL_MEDIA = TransformSet(
    name="Social Media",
    description="Social media platform transforms",
    icon="users"
)

NETWORK = TransformSet(
    name="Network",
    description="Network infrastructure transforms",
    icon="network"
)

IDENTITY = TransformSet(
    name="Identity",
    description="Identity and person-related transforms",
    icon="user"
)

THREAT_INTEL = TransformSet(
    name="Threat Intelligence",
    description="Threat intelligence and security transforms",
    icon="shield"
)

DOCUMENTS = TransformSet(
    name="Documents",
    description="Document and file analysis transforms",
    icon="file"
)

GEOLOCATION = TransformSet(
    name="Geolocation",
    description="Location and mapping transforms",
    icon="map"
)

CRYPTOCURRENCY = TransformSet(
    name="Cryptocurrency",
    description="Blockchain and cryptocurrency transforms",
    icon="currency-bitcoin"
)


# Registry of all transform sets
_transform_sets: dict[str, TransformSet] = {}


def register_set(transform_set: TransformSet) -> TransformSet:
    """Register a transform set in the global registry.

    Args:
        transform_set: The transform set to register

    Returns:
        The registered transform set
    """
    _transform_sets[transform_set.name] = transform_set
    return transform_set


def get_set(name: str) -> TransformSet | None:
    """Get a transform set by name.

    Args:
        name: Name of the transform set

    Returns:
        The transform set or None if not found
    """
    return _transform_sets.get(name)


def get_all_sets() -> list[TransformSet]:
    """Get all registered transform sets.

    Returns:
        List of all transform sets
    """
    return list(_transform_sets.values())


# Register built-in sets
for _set in [OSINT_CORE, SOCIAL_MEDIA, NETWORK, IDENTITY, THREAT_INTEL, DOCUMENTS, GEOLOCATION, CRYPTOCURRENCY]:
    register_set(_set)
