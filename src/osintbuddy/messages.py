"""UI messages for OSINTBuddy transforms.

This module provides a system for transforms to send feedback messages
to the UI, similar to Maltego's addUIMessage functionality.

Example usage:
    from osintbuddy.messages import UIMessage, MessageType

    @transform(target="website@1.0.0", label="Scan")
    async def scan(entity):
        results = []
        messages = []

        try:
            # ... do work
            messages.append(UIMessage("Found 15 subdomains", MessageType.INFO))
        except RateLimitError:
            messages.append(UIMessage("Rate limited", MessageType.WARNING))

        return TransformResponse(entities=results, messages=messages)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    """Types of UI messages."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    SUCCESS = "success"


@dataclass
class UIMessage:
    """A message to display in the UI.

    Attributes:
        message: The message text
        type: Message severity/type
        title: Optional title for the message
        details: Optional additional details (shown on expand)
        duration: How long to show the message in ms (0 = persistent)
    """
    message: str
    type: MessageType = MessageType.INFO
    title: str = ""
    details: str = ""
    duration: int = 5000  # 5 seconds default

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message": self.message,
            "type": self.type.value,
            "title": self.title,
            "details": self.details,
            "duration": self.duration,
        }


@dataclass
class TransformResponse:
    """Complete response from a transform including entities and messages.

    This allows transforms to return both result entities and UI feedback
    in a structured way.

    Attributes:
        entities: List of result entities (Entity objects or blueprint dicts)
        messages: List of UI messages to display
        metadata: Optional metadata about the transform execution
    """
    entities: list[Any] = None
    messages: list[UIMessage] = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.messages is None:
            self.messages = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entities": self.entities,  # Will be normalized by normalize_result
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    def add_message(
        self,
        message: str,
        type: MessageType = MessageType.INFO,
        title: str = "",
        details: str = ""
    ) -> 'TransformResponse':
        """Add a UI message to the response.

        Args:
            message: Message text
            type: Message type
            title: Optional title
            details: Optional details

        Returns:
            Self for chaining
        """
        self.messages.append(UIMessage(
            message=message,
            type=type,
            title=title,
            details=details
        ))
        return self

    def add_entity(self, entity: Any) -> 'TransformResponse':
        """Add an entity to the response.

        Args:
            entity: Entity object or blueprint dict

        Returns:
            Self for chaining
        """
        self.entities.append(entity)
        return self

    def info(self, message: str, title: str = "") -> 'TransformResponse':
        """Add an info message."""
        return self.add_message(message, MessageType.INFO, title)

    def warning(self, message: str, title: str = "") -> 'TransformResponse':
        """Add a warning message."""
        return self.add_message(message, MessageType.WARNING, title)

    def error(self, message: str, title: str = "") -> 'TransformResponse':
        """Add an error message."""
        return self.add_message(message, MessageType.ERROR, title)

    def success(self, message: str, title: str = "") -> 'TransformResponse':
        """Add a success message."""
        return self.add_message(message, MessageType.SUCCESS, title)
