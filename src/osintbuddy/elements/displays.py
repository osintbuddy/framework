"""Display elements for OSINTBuddy plugins.

Display elements render read-only content in entity views.
"""
from __future__ import annotations

from typing import Any
from osintbuddy.elements.base import BaseDisplay


class Title(BaseDisplay):
    """Title/heading display element.

    Example:
        Title(label="Results", value="Search Results")
    """
    element_type: str = 'title'

    def __init__(self, value: str = '', **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class Text(BaseDisplay):
    """Text section display element.

    Example:
        Text(label="Description", value="Some text content", icon="info")
    """
    element_type: str = 'section'

    def __init__(self, value: str = '', icon: str = "123", **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value,
            "icon": icon
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class Empty(BaseDisplay):
    """Empty spacer element.

    Example:
        Empty(width=6)  # Half-width spacer
    """
    element_type: str = 'empty'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class CopyText(BaseDisplay):
    """Copyable text display element.

    Example:
        CopyText(label="API Key", value="abc123...")
    """
    element_type: str = 'copy-text'

    def __init__(self, value: str = '', **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class CopyCode(BaseDisplay):
    """Copyable code block display element.

    Example:
        CopyCode(label="Response", value='{"status": "ok"}')
    """
    element_type: str = 'copy-code'

    def __init__(self, value: str = '', **kwargs):
        super().__init__(**kwargs)
        self.element = {
            "value": value
        }

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element(**self.element)


class Json(BaseDisplay):
    """JSON viewer display element.

    Example:
        Json(label="Data")
    """
    element_type: str = 'json'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class Image(BaseDisplay):
    """Image display element.

    Example:
        Image(label="Screenshot")
    """
    element_type: str = 'img'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class Pdf(BaseDisplay):
    """PDF viewer display element.

    Example:
        Pdf(label="Document")
    """
    element_type: str = 'pdf'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class Video(BaseDisplay):
    """Video player display element.

    Example:
        Video(label="Recording")
    """
    element_type: str = 'video'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class List(BaseDisplay):
    """List display element.

    Example:
        List(label="Items")
    """
    element_type: str = 'list'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()


class Table(BaseDisplay):
    """Table display element.

    Example:
        Table(label="Results")
    """
    element_type: str = 'table'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return self._base_entity_element()
