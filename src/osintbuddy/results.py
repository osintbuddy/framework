"""Transform result types for OSINTBuddy plugins.

This module provides structured types for transform returns, enabling:
- Custom edge properties (labels, colors, styles)
- File attachments on entities
- Subgraph structures (nested entity relationships)
- Backwards compatibility with plain dict returns

Example usage:
    from osintbuddy.results import Entity, Edge, File, Subgraph

    # Simple return (backwards compatible)
    return [SomePlugin.blueprint(field="value")]

    # With custom edge
    return [Entity(
        data=SomePlugin.blueprint(field="value"),
        edge=Edge(label="discovered via", color="#22C55E")
    )]

    # With file attachment
    return [Entity(
        data=SomePlugin.blueprint(field="value"),
        files=[File(path="/tmp/screenshot.png", label="Screenshot")]
    )]

    # Subgraph: A -> B -> C
    return [Entity(
        data=PluginB.blueprint(field="value"),
        children=[
            Entity(data=PluginC.blueprint(other="data"))
        ]
    )]
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Edge:
    """Customizable edge properties for entity connections.

    Attributes:
        label: Text label displayed on the edge
        color: Hex color code (e.g., "#22C55E")
        style: Line style - "solid", "dashed", or "dotted"
        width: Line width in pixels
        animated: Whether the edge should be animated
        properties: Additional custom properties
    """
    label: str = ""
    color: str | None = None
    style: str | None = None
    width: int | None = None
    animated: bool = False
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"label": self.label}
        if self.color is not None:
            result["color"] = self.color
        if self.style is not None:
            result["style"] = self.style
        if self.width is not None:
            result["width"] = self.width
        if self.animated:
            result["animated"] = self.animated
        if self.properties:
            result["properties"] = self.properties
        return result


@dataclass
class File:
    """File attachment for an entity.

    Attributes:
        path: Absolute path to the file
        label: Display label for the file
        mime_type: MIME type (auto-detected if not provided)
        description: Optional description
    """
    path: str
    label: str | None = None
    mime_type: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"path": self.path}
        if self.label is not None:
            result["label"] = self.label
        if self.mime_type is not None:
            result["mime_type"] = self.mime_type
        if self.description is not None:
            result["description"] = self.description
        return result


@dataclass
class Entity:
    """Result entity from a transform with optional enhancements.

    Wraps entity data (typically from Plugin.blueprint()) with:
    - Custom edge properties
    - File attachments
    - Child entities for subgraph structures

    Attributes:
        data: Entity data dict (from Plugin.blueprint())
        edge: Custom edge properties (overrides transform default)
        files: List of file attachments
        children: Child entities forming a subgraph
    """
    data: dict[str, Any]
    edge: Edge | None = None
    files: list[File] = field(default_factory=list)
    children: list[Entity] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        The result merges entity data with transform metadata:
        - Edge info is stored under "_edge" key
        - Files under "_files" key
        - Children under "_children" key
        """
        result = dict(self.data)

        if self.edge is not None:
            result["_edge"] = self.edge.to_dict()
            # Also set edge_label for backwards compatibility
            result["edge_label"] = self.edge.label

        if self.files:
            result["_files"] = [f.to_dict() for f in self.files]

        if self.children:
            result["_children"] = [c.to_dict() for c in self.children]

        return result


@dataclass
class Subgraph:
    """A complete subgraph structure returned from a transform.

    Use this when you need to return a complex graph structure
    with multiple root entities and explicit edge definitions.

    Attributes:
        entities: Root entities connected to the source node
        edges: Explicit edges between entities [(source_id, target_id, Edge)]
    """
    entities: list[Entity] = field(default_factory=list)
    edges: list[tuple[str, str, Edge]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "_type": "subgraph",
            "entities": [e.to_dict() for e in self.entities],
            "edges": [
                {
                    "source": src,
                    "target": tgt,
                    **edge.to_dict()
                }
                for src, tgt, edge in self.edges
            ]
        }


def normalize_result(result: Any, default_edge_label: str = "") -> list[dict[str, Any]]:
    """Normalize transform result to a list of dicts.

    Handles:
    - Plain dicts (legacy format)
    - Entity instances
    - Subgraph instances
    - Lists of any of the above

    Args:
        result: The raw transform result
        default_edge_label: Default edge label from transform decorator

    Returns:
        List of normalized entity dicts ready for JSON serialization
    """
    if result is None:
        return []

    # Handle Subgraph specially
    if isinstance(result, Subgraph):
        return [result.to_dict()]

    # Normalize to list
    if not isinstance(result, list):
        result = [result]

    normalized = []
    for item in result:
        if isinstance(item, Entity):
            entity_dict = item.to_dict()
            # Apply default edge label if not overridden
            if "edge_label" not in entity_dict:
                entity_dict["edge_label"] = default_edge_label
            normalized.append(entity_dict)
        elif isinstance(item, Subgraph):
            normalized.append(item.to_dict())
        elif isinstance(item, dict):
            # Legacy dict format - ensure edge_label exists
            if "edge_label" not in item:
                item["edge_label"] = default_edge_label
            normalized.append(item)
        else:
            # Try to convert to dict
            try:
                normalized.append(dict(item))
            except (TypeError, ValueError):
                # Skip unconvertible items
                pass

    return normalized
